"""Run the archive batch with the verified reward-matching rules."""

from unittest.mock import patch

from spireshift import native_a8_archive_batch_v2 as runner
from spireshift.native_a8_archive_rewards_v3 import MATCHER, installed, screen

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-archive-reward-check-v3.json"
SCHEMA = "native-a8-archive-batch-v3"
REQUIRED = runner.REQUIRED | {
    "src/spireshift/native_a8_archive_batch_v3.py",
    "src/spireshift/native_a8_archive_rewards_v3.py",
    "scripts/qualify-a8-archive-batch-v3.sh",
}


def main() -> int:
    with patch.multiple(
        runner,
        RECIPE=RECIPE,
        SCHEMA=SCHEMA,
        MATCHER=MATCHER,
        REQUIRED=REQUIRED,
        installed=installed,
        screen=screen,
    ):
        return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
