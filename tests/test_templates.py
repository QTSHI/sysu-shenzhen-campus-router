from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TemplateTests(unittest.TestCase):
    def test_template_contains_no_credentials(self):
        text = (ROOT / "templates/minieap.public.conf.in").read_text(encoding="utf-8")
        values = {line.split("=", 1)[0].strip(): line.split("=", 1)[1].strip()
                  for line in text.splitlines() if "=" in line and not line.startswith("#")}
        self.assertFalse({"username", "password", "passwd", "key", "ssid"} & set(values))
        self.assertEqual(values["max-fail"], "1")
        self.assertEqual(values["no-auto-reauth"], "1")
        self.assertIn("REPLACE_", values["nic"])

    def test_no_private_files_or_packet_dumps(self):
        forbidden = {".pcap", ".pcapng", ".key", ".exe", ".dll", ".bin"}
        for path in ROOT.rglob("*"):
            self.assertFalse(path.is_symlink())
            if path.is_file():
                self.assertNotIn(path.suffix.lower(), forbidden)
                self.assertNotEqual(path.name, "minieap.conf")
                self.assertNotIn("private", [part.lower() for part in path.relative_to(ROOT).parts])


if __name__ == "__main__":
    unittest.main()
