#!/usr/bin/env python3
"""Passive Windows Npcap observer. No send/install/start/configuration API."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from campus_eap.metadata import FIELDS, LIMIT, parse_frame, read_jsonl, summary, validate_row

FILTER = ("ether[12:2]=0x888e or ((ether[12:2]=0x8100 or ether[12:2]=0x88a8) and "
          "(ether[16:2]=0x888e or ((ether[16:2]=0x8100 or ether[16:2]=0x88a8) and ether[20:2]=0x888e)))")
GUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")


class Device(C.Structure):
    pass


Device._fields_ = [("next", C.POINTER(Device)), ("name", C.c_char_p),
                   ("description", C.c_char_p), ("addresses", C.c_void_p), ("flags", C.c_uint)]


class PacketHeader(C.Structure):
    _fields_ = [("seconds", C.c_long), ("microseconds", C.c_long),
                ("captured", C.c_uint32), ("wire", C.c_uint32)]


class Program(C.Structure):
    _fields_ = [("length", C.c_uint), ("instructions", C.c_void_p)]


def driver_running():
    """Query SCM only; do not request driver start/change permissions."""
    from ctypes import wintypes as W
    class Status(C.Structure):
        _fields_ = [(name, W.DWORD) for name in ("type", "state", "accepted", "exit", "service_exit", "checkpoint", "wait")]
    api = C.WinDLL("advapi32.dll", use_last_error=True)
    api.OpenSCManagerW.argtypes, api.OpenSCManagerW.restype = [W.LPCWSTR, W.LPCWSTR, W.DWORD], W.HANDLE
    api.OpenServiceW.argtypes, api.OpenServiceW.restype = [W.HANDLE, W.LPCWSTR, W.DWORD], W.HANDLE
    api.QueryServiceStatus.argtypes, api.QueryServiceStatus.restype = [W.HANDLE, C.POINTER(Status)], W.BOOL
    api.CloseServiceHandle.argtypes = [W.HANDLE]
    manager = api.OpenSCManagerW(None, None, 1)
    if not manager:
        return False
    service = None
    try:
        service = api.OpenServiceW(manager, "npcap", 4)
        if not service:
            return False
        status = Status()
        return bool(api.QueryServiceStatus(service, C.byref(status)) and status.state == 4 and status.type & 1)
    finally:
        if service:
            api.CloseServiceHandle(service)
        api.CloseServiceHandle(manager)


class Npcap:
    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("Windows Npcap capture only")
        if not driver_running():
            raise RuntimeError("the existing Npcap driver must already be running")
        kernel = C.WinDLL("kernel32.dll", use_last_error=True)
        kernel.GetWindowsDirectoryW.argtypes = [C.c_wchar_p, C.c_uint]
        kernel.GetWindowsDirectoryW.restype = C.c_uint
        buffer = C.create_unicode_buffer(32768)
        length = kernel.GetWindowsDirectoryW(buffer, len(buffer))
        system = Path(buffer.value)
        if not 0 < length < len(buffer) or not system.is_absolute():
            raise RuntimeError("invalid system directory")
        folder = "SysWOW64" if C.sizeof(C.c_void_p) == 4 and os.environ.get("PROCESSOR_ARCHITEW6432") else "System32"
        directory = system / folder / "Npcap"
        if not (directory / "wpcap.dll").is_file():
            raise RuntimeError("install matching-architecture official Npcap first")
        self.cookie = os.add_dll_directory(str(directory))
        self.dll = C.CDLL(str(directory / "wpcap.dll"), winmode=0x100 | 0x1000)
        signatures = {
            "pcap_findalldevs": ([C.POINTER(C.POINTER(Device)), C.c_char_p], C.c_int),
            "pcap_freealldevs": ([C.POINTER(Device)], None),
            "pcap_open_live": ([C.c_char_p, C.c_int, C.c_int, C.c_int, C.c_char_p], C.c_void_p),
            "pcap_datalink": ([C.c_void_p], C.c_int),
            "pcap_compile": ([C.c_void_p, C.POINTER(Program), C.c_char_p, C.c_int, C.c_uint32], C.c_int),
            "pcap_setfilter": ([C.c_void_p, C.POINTER(Program)], C.c_int),
            "pcap_freecode": ([C.POINTER(Program)], None),
            "pcap_next_ex": ([C.c_void_p, C.POINTER(C.POINTER(PacketHeader)), C.POINTER(C.POINTER(C.c_ubyte))], C.c_int),
            "pcap_setnonblock": ([C.c_void_p, C.c_int, C.c_char_p], C.c_int),
            "pcap_close": ([C.c_void_p], None),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.dll, name)
            function.argtypes, function.restype = args, result

    def devices(self):
        head = C.POINTER(Device)()
        error = C.create_string_buffer(256)
        if self.dll.pcap_findalldevs(C.byref(head), error) != 0:
            raise RuntimeError("adapter enumeration failed")
        result = {}
        try:
            node = head
            for _ in range(1024):
                if not node:
                    break
                name = node.contents.name or b""
                match = re.fullmatch(rb"\\Device\\NPF_\{([0-9A-Fa-f-]+)\}", name)
                if match and GUID.fullmatch(match[1].decode("ascii")):
                    result[match[1].decode("ascii").upper()] = name
                node = node.contents.next
            else:
                raise RuntimeError("adapter list exceeded bound")
        finally:
            self.dll.pcap_freealldevs(head)
        return result

    def capture(self, guid, seconds, output):
        devices = self.devices()
        if guid not in devices:
            raise RuntimeError("exact adapter GUID was not found")
        error = C.create_string_buffer(256)
        handle = self.dll.pcap_open_live(devices[guid], 32, 0, 250, error)
        if not handle:
            raise RuntimeError("capture open failed; check existing driver and local permissions")
        try:
            if self.dll.pcap_datalink(handle) != 1:
                raise RuntimeError("selected interface is not Ethernet capture")
            program = Program()
            if self.dll.pcap_compile(handle, C.byref(program), FILTER.encode("ascii"), 1, 0xFFFFFFFF) != 0:
                raise RuntimeError("filter compilation failed")
            try:
                if self.dll.pcap_setfilter(handle, C.byref(program)) != 0:
                    raise RuntimeError("filter installation failed")
            finally:
                self.dll.pcap_freecode(C.byref(program))
            if self.dll.pcap_setnonblock(handle, 1, error) != 0:
                raise RuntimeError("bounded nonblocking capture is unavailable")
            start = time.monotonic()
            count = 0
            with output.open("x", encoding="ascii", newline="\n") as stream:
                while time.monotonic() - start < seconds:
                    header = C.POINTER(PacketHeader)()
                    data = C.POINTER(C.c_ubyte)()
                    rc = self.dll.pcap_next_ex(handle, C.byref(header), C.byref(data))
                    if rc == 0:
                        time.sleep(0.02)
                        continue
                    if rc != 1:
                        raise RuntimeError("capture ended unexpectedly")
                    h = header.contents
                    if not data or h.captured > 32 or h.wire > 65535:
                        continue
                    row = parse_frame(C.string_at(data, h.captured), h.wire)
                    if row is None:
                        continue
                    row.update(seq=count + 1, elapsed_ms=int((time.monotonic() - start) * 1000), direction="unknown", wire_length=h.wire)
                    row = validate_row(row)
                    encoded = json.dumps(row, separators=(",", ":")) + "\n"
                    if stream.tell() + len(encoded) > LIMIT:
                        break
                    stream.write(encoded)
                    stream.flush()
                    count += 1
            return count
        finally:
            self.dll.pcap_close(handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list", action="store_true")
    group.add_argument("--interface", help="Exact physical Ethernet GUID; braces optional")
    group.add_argument("--validate", type=Path, help="Offline validate a single JSONL segment")
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not (args.list or args.interface or args.validate):
        parser.print_help()
        return 0
    if args.validate:
        with args.validate.open("rb") as f:
            raw = f.read(LIMIT + 1)
        print(json.dumps(summary(read_jsonl(raw))))
        return 0
    if not 1 <= args.seconds <= 300:
        parser.error("seconds must be 1..300")
    capture = Npcap()
    if args.list:
        print(json.dumps(sorted(capture.devices())))
        return 0
    guid = args.interface.strip("{}")
    if not GUID.fullmatch(guid) or args.output is None:
        parser.error("exact GUID and a new output filename are required")
    print(json.dumps({"records": capture.capture(guid.upper(), args.seconds, args.output)}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError):
        print("Operation stopped. No raw packet or account data is printed.", file=sys.stderr)
        raise SystemExit(2)
