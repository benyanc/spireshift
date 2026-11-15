"""Bounded local JSON-lines transport; one observation in memory, no shell or retry."""

from __future__ import annotations

import json
import os
import select
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.engine_connector import _stop_child


class JsonLines:
    def __init__(self, root: Path, command: list[str], log: Path) -> None:
        self.stderr = log.open("xb")
        self.child = subprocess.Popen(
            command,
            cwd=root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr,
            start_new_session=True,
        )
        self.buffer = bytearray()
        self.sequence = 0

    def send(self, value: dict[str, Any]) -> None:
        assert self.child.stdin is not None
        self.child.stdin.write((json.dumps(value, allow_nan=False) + "\n").encode())
        self.child.stdin.flush()

    def receive(self, deadline: float) -> dict[str, Any]:
        assert self.child.stdout is not None
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Local checkpoint request cap; preserve the unfinished attempt")
            if not select.select([self.child.stdout], [], [], min(remaining, 1.0))[0]:
                continue
            data = os.read(self.child.stdout.fileno(), 65536)
            if not data:
                raise ValueError(
                    f"Checkpoint bridge exited without a complete reply: {self.child.poll()}"
                )
            self.buffer.extend(data)
            if len(self.buffer) > 16_000_000:
                raise ValueError("Checkpoint bridge exceeded its one-frame memory bound")
        line, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        value: dict[str, Any] = json.loads(line)
        return value

    def project(
        self,
        snapshot: dict[str, Any],
        reads: list[dict[str, Any]],
        navigation: dict[str, Any] | None,
        deadline: float,
    ) -> dict[str, Any]:
        self.sequence += 1
        self.send(
            {
                "request_id": self.sequence,
                "snapshot": snapshot,
                "reads": reads,
                "navigation": navigation,
            }
        )
        reply = self.receive(min(deadline, time.monotonic() + 10))
        if reply.get("request_id") != self.sequence or reply.get("ok") is not True:
            raise ValueError(f"Shared public-input conversion failed: {reply.get('error')}")
        return reply["frame"]  # type: ignore[no-any-return]

    def close(self) -> None:
        try:
            if self.child.stdin is not None:
                self.child.stdin.close()
            code = self.child.wait(timeout=5)
            if code != 0:
                raise ValueError(f"Checkpoint bridge did not exit cleanly: {code}")
        finally:
            self.stop()

    def commit(self, choice: dict[str, Any], receipt: dict[str, Any], deadline: float) -> None:
        self.sequence += 1
        self.send(
            {"request_id": self.sequence, "command": "commit", **choice, "acknowledgement": receipt}
        )
        reply = self.receive(min(deadline, time.monotonic() + 10))
        if reply.get("ok") is not True or reply.get("request_id") != self.sequence:
            raise ValueError(f"Shared navigation delivery failed: {reply.get('error')}")

    def stop(self) -> None:
        _stop_child(self.child)
        self.stderr.close()
