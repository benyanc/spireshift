"""Use the normalized rest checker on twelve fresh declared diagnostic worlds."""

from __future__ import annotations

from unittest.mock import patch

from spireshift import native_mixed_handoff_cases_v1, native_mixed_handoff_session_v1
from spireshift.native_mixed_handoff_checks_v2 import rest_menu
from spireshift.native_mixed_handoff_inputs_v2 import MODULE, SCHEMA, load


def main() -> int:
    with (
        patch.multiple(native_mixed_handoff_session_v1, MODULE=MODULE, SCHEMA=SCHEMA, load=load),
        patch.object(native_mixed_handoff_cases_v1, "rest_menu", rest_menu),
    ):
        return native_mixed_handoff_session_v1.main()


if __name__ == "__main__":
    raise SystemExit(main())
