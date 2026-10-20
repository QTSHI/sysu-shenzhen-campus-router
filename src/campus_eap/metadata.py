"""Strict numeric EAPOL metadata; never returns MACs, identities or payloads."""
import json
import struct

FIELDS = ("seq", "elapsed_ms", "direction", "wire_length", "eapol_version",
          "eapol_type", "eapol_body_length", "eap_code", "eap_id", "eap_length", "eap_type")
NULLABLE = {"eap_code", "eap_id", "eap_length", "eap_type"}
LIMIT = 262144


def parse_frame(prefix, wire_length=None):
    """Parse only the Ethernet/EAPOL/EAP headers, allowing up to two VLAN tags."""
    if not isinstance(prefix, bytes) or len(prefix) > 32 or len(prefix) < 14:
        return None
    if wire_length is None:
        wire_length = len(prefix)
    if type(wire_length) is not int or not len(prefix) <= wire_length <= 65535:
        return None
    offset = 14
    protocol = struct.unpack_from("!H", prefix, 12)[0]
    for _ in range(2):
        if protocol not in (0x8100, 0x88A8):
            break
        if len(prefix) < offset + 4:
            return None
        protocol = struct.unpack_from("!H", prefix, offset + 2)[0]
        offset += 4
    if protocol != 0x888E or len(prefix) < offset + 4:
        return None
    version, packet_type, body_length = struct.unpack_from("!BBH", prefix, offset)
    if offset + 4 + body_length > wire_length:
        return None
    row = dict(eapol_version=version, eapol_type=packet_type, eapol_body_length=body_length,
               eap_code=None, eap_id=None, eap_length=None, eap_type=None)
    if packet_type != 0:
        return row
    if body_length < 4 or len(prefix) < offset + 8:
        return None
    code, identifier, length = struct.unpack_from("!BBH", prefix, offset + 4)
    if code not in (1, 2, 3, 4) or length != body_length:
        return None
    if code in (3, 4) and length != 4:
        return None
    row.update(eap_code=code, eap_id=identifier, eap_length=length)
    if code in (1, 2):
        if length < 5 or len(prefix) < offset + 9:
            return None
        row["eap_type"] = prefix[offset + 8]
    return row


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate metadata field")
        result[key] = value
    return result


def validate_row(row):
    if not isinstance(row, dict) or set(row) != set(FIELDS):
        raise ValueError("unexpected metadata fields")
    if row["direction"] not in ("in", "out", "unknown"):
        raise ValueError("invalid direction")
    for key in FIELDS:
        if key == "direction" or (key in NULLABLE and row[key] is None):
            continue
        if type(row[key]) is not int or row[key] < 0:
            raise ValueError("numeric metadata required")
    if not 1 <= row["seq"] <= 1000000 or row["elapsed_ms"] > 300000:
        raise ValueError("capture budget exceeded")
    if not 18 <= row["wire_length"] <= 65535:
        raise ValueError("invalid wire length")
    if row["eapol_body_length"] > row["wire_length"] - 18:
        raise ValueError("body exceeds the wire frame")
    if any(row[k] > 255 for k in ("eapol_version", "eapol_type")) or row["eapol_body_length"] > 65535:
        raise ValueError("invalid EAPOL field")
    code = row["eap_code"]
    if row["eapol_type"] != 0:
        if any(row[k] is not None for k in NULLABLE):
            raise ValueError("EAP fields on non-EAP packet")
    elif (code not in (1, 2, 3, 4) or row["eap_id"] is None or row["eap_id"] > 255
          or row["eap_length"] != row["eapol_body_length"]):
        raise ValueError("inconsistent EAP header")
    elif code in (3, 4):
        if row["eap_length"] != 4 or row["eap_type"] is not None:
            raise ValueError("Success/Failure has no method field")
    elif row["eap_length"] < 5 or row["eap_type"] is None or row["eap_type"] > 255:
        raise ValueError("invalid method header")
    return {key: row[key] for key in FIELDS}


def read_jsonl(raw):
    """One observer segment only; reject extra fields before returning anything."""
    if not isinstance(raw, bytes) or len(raw) > LIMIT or (raw and not raw.endswith(b"\n")):
        raise ValueError("invalid bounded metadata stream")
    rows = []
    previous_ms = 0
    for line in raw.splitlines():
        if not 1 <= len(line) <= 511:
            raise ValueError("invalid metadata line")
        row = validate_row(json.loads(line.decode("ascii"), object_pairs_hook=_pairs))
        if row["seq"] != len(rows) + 1 or row["elapsed_ms"] < previous_ms:
            raise ValueError("inconsistent sequence or time")
        rows.append(row)
        previous_ms = row["elapsed_ms"]
    return rows


def summary(rows):
    return {"records": len(rows), "success": sum(r["eap_code"] == 3 for r in rows),
            "failure": sum(r["eap_code"] == 4 for r in rows),
            "request_types": sorted({r["eap_type"] for r in rows if r["eap_code"] == 1}),
            "complete_handshake_proven": False}
