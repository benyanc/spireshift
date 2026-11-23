from __future__ import annotations

from pathlib import Path

import pytest

from spireshift.engine_qualification import _sha_file
from spireshift.native_mixed_handoff_inputs_v7 import TEST, check_test_amendment


def test_qualification_scope_accepts_only_the_declared_test_type_annotation(tmp_path: Path) -> None:
    original = tmp_path / "original.py"
    original.write_text("from typing import cast\n\ndef control():\n    raw = {}\n")
    current = tmp_path / TEST
    current.parent.mkdir(parents=True)
    current.write_text(
        "from typing import Any, cast\n\ndef control():\n    raw: dict[str, Any] = {}\n"
    )
    cfg = {"original_test": {"path": "original.py", "sha256": _sha_file(original)}}
    code = tmp_path / "runtime.py"
    code.write_text("frozen = True\n")
    parent = {"implementation": {TEST: _sha_file(original), "runtime.py": _sha_file(code)}}
    check_test_amendment(tmp_path, cfg, parent)
    current.write_text(current.read_text().replace("= {}", "= {'new': 1}"))
    with pytest.raises(ValueError, match="Only the declared"):
        check_test_amendment(tmp_path, cfg, parent)
    current.write_text(
        "from typing import Any, cast\n\ndef control():\n    raw: dict[str, Any] = {}\n"
    )
    code.write_text("frozen = False\n")
    with pytest.raises(ValueError, match="changed"):
        check_test_amendment(tmp_path, cfg, parent)
