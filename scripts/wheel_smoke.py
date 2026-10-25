"""Install the built wheel in a fresh venv and run from outside the source tree."""

import json
import os
import subprocess
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
(wheel,) = (ROOT / "dist").glob("*.whl")
with tempfile.TemporaryDirectory() as folder:
    temp = Path(folder)
    venv.create(temp / "env", with_pip=True)
    python = temp / "env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)],
        check=True,
        cwd=temp,
    )
    result = subprocess.run(
        [str(python), "-I", "-m", "span_units", "--version"],
        check=True,
        capture_output=True,
        text=True,
        cwd=temp,
    )
    assert "0.1.0" in result.stdout
    subprocess.run([str(python), "-I", str(ROOT / "scripts" / "example.py")], check=True, cwd=temp)
    subprocess.run(
        [str(python), "-m", "pip", "uninstall", "-y", "span-units"], check=True, cwd=temp
    )
print(json.dumps({"wheel_install_run_uninstall": "passed"}))
