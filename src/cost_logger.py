#!/usr/bin/env python3
"""Cost logger: wraps any subprocess and logs token usage + USD cost.

Usage:
    python src/cost_logger.py --cmd "pier run ..." --log results/cost_log.jsonl

Also provides a CostTracker class for programmatic use.
"""

import argparse
import json
import subprocess
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class CostRecord:
    """Single cost observation."""
    timestamp: str = ""
    task: str = ""
    trial: str = ""
    model: str = ""
    in_tokens: int = 0
    out_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    model_calls: int = 0
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class CostTracker:
    """Accumulates cost records and enforces a spend cap."""

    def __init__(self, cap_usd: float = 100.0, log_path: Path | None = None):
        self.cap = cap_usd
        self.log_path = log_path
        self.records: list[CostRecord] = []
        self._total = 0.0

        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def total_usd(self) -> float:
        return self._total

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.cap - self._total)

    def add(self, record: CostRecord) -> None:
        """Add a cost record. Raises RuntimeError if cap exceeded."""
        self.records.append(record)
        self._total += record.cost_usd

        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict()) + "\n")

        if self._total > self.cap:
            raise RuntimeError(
                f"SPEND CAP EXCEEDED: ${self._total:.2f} > ${self.cap:.2f}"
            )

    def summary(self) -> str:
        n = len(self.records)
        return (
            f"CostTracker: {n} records, "
            f"total=${self._total:.2f}, "
            f"remaining=${self.remaining_usd:.2f}, "
            f"cap=${self.cap:.2f}"
        )


def main():
    ap = argparse.ArgumentParser(
        description="Run a command and log cost to JSONL."
    )
    ap.add_argument("--cmd", required=True, help="Command to run")
    ap.add_argument(
        "--log",
        type=Path,
        default=Path("results/cost_log.jsonl"),
        help="JSONL log file",
    )
    ap.add_argument(
        "--cap", type=float, default=100.0, help="Spend cap in USD"
    )
    args = ap.parse_args()

    tracker = CostTracker(cap_usd=args.cap, log_path=args.log)

    print(f"Running: {args.cmd}")
    print(f"Cost log: {args.log}")
    print(f"Spend cap: ${args.cap:.2f}")
    print("─" * 50)

    t0 = time.time()
    result = subprocess.run(
        args.cmd, shell=True, capture_output=True, text=True
    )
    elapsed = time.time() - t0

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    record = CostRecord(
        timestamp=datetime.utcnow().isoformat() + "Z",
        latency_s=round(elapsed, 2),
        notes=f"exit_code={result.returncode}",
    )
    tracker.add(record)
    print(f"\n{tracker.summary()}")


if __name__ == "__main__":
    main()
