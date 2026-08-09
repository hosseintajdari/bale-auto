import tempfile
import unittest
from pathlib import Path

from scripts.scan_secrets import scan_repository, scan_text


class SecretScannerTests(unittest.TestCase):
    def test_detects_a_private_key_header(self):
        header = "-" * 5 + "BEGIN PRIVATE KEY" + "-" * 5
        findings = scan_text("bad.pem", header)
        self.assertEqual(findings[0].rule, "private-key")

    def test_detects_a_token_assignment_with_a_value(self):
        key = "TELEGRAM_BOT_" + "TOKEN"
        findings = scan_text("bad.env", f"{key}=live-" + "secret-value")
        self.assertEqual(findings[0].rule, "assigned-secret")

    def test_allows_empty_values_in_env_example(self):
        key = "TELEGRAM_BOT_" + "TOKEN"
        self.assertEqual(scan_text(".env.example", f"{key}="), [])

    def test_finding_does_not_contain_the_matched_value(self):
        key = "SERVICE_" + "PASSWORD"
        value = "do-not-print-this-value"
        finding = scan_text("bad.env", f"{key}={value}")[0]
        self.assertNotIn(value, repr(finding))

    def test_repository_scan_skips_binary_files_and_git_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "binary.bin").write_bytes(b"\x00" + b"TOKEN=value")
            git = root / ".git"
            git.mkdir()
            (git / "config").write_text("API_KEY=value", encoding="utf-8")
            self.assertEqual(scan_repository(root), [])


if __name__ == "__main__":
    unittest.main()
