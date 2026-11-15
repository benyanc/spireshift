from __future__ import annotations

import ast
import hashlib
import subprocess
import tomllib
from pathlib import Path


def test_frozen_comparison_format_exception_has_exact_bytes_and_identical_ast() -> None:
    root = Path(__file__).resolve().parents[2]
    source_path = "src/spireshift/native_flow_inputs_v4.py"
    settings = tomllib.loads((root / ".ruff.toml").read_text())
    assert settings == {"extend": "pyproject.toml", "format": {"exclude": [source_path]}}
    raw = (root / source_path).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "b2276bae5bb4a73ddf3fff0eab6c472ff5dee00656190a9c1801aa8d83377db1"
    )
    formatted = subprocess.run(
        [
            "ruff",
            "format",
            "--isolated",
            "--line-length",
            "100",
            "--stdin-filename",
            "frozen.py",
            "-",
        ],
        input=raw.decode(),
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    ).stdout
    assert ast.dump(ast.parse(raw)) == ast.dump(ast.parse(formatted))
