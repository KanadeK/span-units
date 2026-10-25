"""An executable end-to-end example using only synthetic input."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    source = root / "annotations.jsonl"
    output = root / "converted.jsonl"
    source.write_text(
        json.dumps(
            {"text": "A😀中", "spans": [{"start": 1, "end": 4, "text": "😀中", "label": "demo"}]}
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "span_units",
            str(source),
            "--from-unit",
            "utf16",
            "--to-unit",
            "utf8",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(output.read_text(encoding="utf-8"))["spans"][0]["end"] == 8
    assert json.loads(result.stdout)["output_written"] is True
    print("PASS: UTF-16 span [1,4) became UTF-8 span [1,8), preserving text.")
