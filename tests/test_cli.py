import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from span_units.cli import run


class CliTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.source = self.root / "input.jsonl"
        self.output = self.root / "output.jsonl"

    def invoke(self, raw, *extra):
        self.source.write_bytes(raw)
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "span_units",
                str(self.source),
                "--from-unit",
                "utf16",
                "--to-unit",
                "utf8",
                "--output",
                str(self.output),
                *extra,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertNotIn("Traceback", process.stderr)
        return process.returncode, json.loads(process.stdout)

    def test_conversion_and_input_preservation(self):
        raw = (
            json.dumps(
                {
                    "text": "A😀中\r\n",
                    "spans": [{"start": 1, "end": 4, "text": "😀中", "label": "place"}],
                }
            ).encode()
            + b"\r\n"
        )
        status, report = self.invoke(raw)
        self.assertEqual(status, 0)
        self.assertTrue(report["output_written"])
        result = json.loads(self.output.read_bytes())
        self.assertEqual(result["spans"][0]["end"], 8)
        self.assertEqual(result["text"], "A😀中\r\n")
        self.assertEqual(self.source.read_bytes(), raw)

    def test_no_partial_output_on_late_span_error(self):
        good = b'{"text":"a","spans":[{"start":0,"end":1}]}\n'
        bad = b'{"text":"secret","spans":[{"start":0,"end":99}]}\n'
        status, report = self.invoke(good + bad)
        self.assertEqual(status, 1)
        self.assertEqual(report["records"], 2)
        self.assertNotIn("secret", json.dumps(report))
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob(".span-units-*")), [])

    def test_malformed_json_rejects_partial_output(self):
        status, report = self.invoke(b'{"text":"a","spans":[]}\n{bad\n')
        self.assertEqual(status, 2)
        self.assertEqual(report["error"]["line"], 2)
        self.assertFalse(self.output.exists())

    def test_strict_json_and_utf8(self):
        for raw in (
            b"\xff",
            b"\xef\xbb\xbf{}",
            b"\n",
            b'{"text":"a","text":"b","spans":[]}',
            b'{"text":"a","spans":[],"x":{"id":1,"id":2}}',
            b'{"text":"a","spans":[],"x":NaN}',
            b'{"text":"a","spans":[],"x":1e999}',
        ):
            with self.subTest(raw=raw):
                self.assertEqual(self.invoke(raw)[0], 2)
                self.assertFalse(self.output.exists())

    def test_resource_limits(self):
        raw = b'{"text":"abc","spans":[]}\n'
        for flag in ("--max-line-bytes", "--max-input-bytes"):
            with self.subTest(flag=flag):
                self.assertEqual(self.invoke(raw, flag, "10")[0], 2)
        self.assertEqual(self.invoke(raw, "--max-chars", "1")[0], 1)

    def test_findings_cap_keeps_failure_count(self):
        status, report = self.invoke(b'{"text":"x","spans":[{}]}\n' * 4, "--max-findings", "1")
        self.assertEqual(status, 1)
        self.assertEqual(report["invalid_records"], 4)
        self.assertEqual(len(report["findings"]), 1)

    def test_no_overwrite(self):
        self.output.write_bytes(b"KEEP")
        self.assertEqual(self.invoke(b'{"text":"","spans":[]}')[0], 2)
        self.assertEqual(self.output.read_bytes(), b"KEEP")

    def test_publish_failure_cleanup(self):
        self.source.write_text('{"text":"","spans":[]}', encoding="utf-8")
        args = argparse.Namespace(
            input=str(self.source),
            output=str(self.output),
            from_unit="utf16",
            to_unit="utf8",
            max_line_bytes=1000,
            max_input_bytes=1000,
            max_chars=100,
            max_spans=100,
            max_findings=100,
        )
        with patch("span_units.cli.os.link", side_effect=OSError("unavailable")):
            report, code = run(args)
        self.assertEqual(code, 2)
        self.assertFalse(report["output_written"])
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".span-units-*")))

    def test_validation_mode(self):
        self.source.write_text('{"text":"","spans":[]}', encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "span_units",
                str(self.source),
                "--from-unit",
                "codepoint",
                "--to-unit",
                "codepoint",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertFalse(json.loads(proc.stdout)["output_written"])

    def test_invalid_option(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "span_units",
                "x",
                "--from-unit",
                "utf8",
                "--to-unit",
                "utf16",
                "--max-chars",
                "0",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)
