import json
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from campus_eap.metadata import FIELDS, parse_frame, read_jsonl, validate_row


def packet(code=1, method=1, payload=b"", vlan=0):
    body = struct.pack("!BBH", code, 7, 5 + len(payload)) + bytes([method]) + payload
    if code in (3, 4):
        body = struct.pack("!BBH", code, 7, 4)
    eth = bytes(12) + (b"\x88\x8e" if not vlan else b"\x81\x00")
    for i in range(vlan):
        eth += b"\x00\x01" + (b"\x88\x8e" if i + 1 == vlan else b"\x81\x00")
    return eth + struct.pack("!BBH", 1, 0, len(body)) + body


class MetadataTests(unittest.TestCase):
    def record(self):
        frame = packet(payload=b"PRIVATE_SENTINEL")
        row = parse_frame(frame[:32], len(frame))
        return dict(row, seq=1, elapsed_ms=0, direction="unknown", wire_length=len(frame))

    def test_identity_body_and_mac_are_never_returned(self):
        value = validate_row(self.record())
        self.assertEqual(set(value), set(FIELDS))
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(value))
        self.assertTrue(all(type(v) is int or v is None or v == "unknown" for v in value.values()))

    def test_success_has_no_method(self):
        frame = packet(code=3)
        result = parse_frame(frame, len(frame))
        self.assertEqual(result["eap_code"], 3)
        self.assertIsNone(result["eap_type"])

    def test_two_vlan_headers(self):
        frame = packet(vlan=2)
        self.assertEqual(parse_frame(frame, len(frame))["eap_type"], 1)
        self.assertIsNone(parse_frame(frame[:20], len(frame)))

    def test_extra_or_duplicate_fields_rejected(self):
        row = self.record()
        row["username"] = "MUST_NOT_PASS"
        with self.assertRaises(ValueError):
            read_jsonl((json.dumps(row) + "\n").encode())
        line = json.dumps(self.record())[:-1] + ',"seq":1}\n'
        with self.assertRaises(ValueError):
            read_jsonl(line.encode())

    def test_boolean_numbers_and_partial_tail_rejected(self):
        row = self.record()
        row["wire_length"] = True
        with self.assertRaises(ValueError):
            validate_row(row)
        with self.assertRaises(ValueError):
            read_jsonl(json.dumps(self.record()).encode())

    def test_size_and_wire_consistency(self):
        row = self.record()
        row["wire_length"] = 18
        with self.assertRaises(ValueError):
            validate_row(row)
        self.assertIsNone(parse_frame(bytes(33), 60))


if __name__ == "__main__":
    unittest.main()
