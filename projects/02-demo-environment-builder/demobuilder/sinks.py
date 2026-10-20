"""Where a build goes: CSV files for review, or any JSON API that accepts batched upserts."""
from __future__ import annotations

import csv
import dataclasses
import json
import time
import urllib.request
from pathlib import Path
from typing import Iterable

PUSH_ORDER = ("sites", "teams", "skills", "queues", "people", "cases")


def _rows(items: Iterable) -> Iterable[dict]:
    for item in items:
        row = dataclasses.asdict(item) if dataclasses.is_dataclass(item) else dict(item)
        yield {k: (json.dumps(v) if isinstance(v, (list, tuple, dict)) else v) for k, v in row.items()}


class CsvSink:
    def __init__(self, out_dir: str | Path):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def push(self, resource: str, items: Iterable) -> int:
        path = self.out_dir / f"{resource}.csv"
        count = 0
        with path.open("w", newline="") as fh:
            writer = None
            for row in _rows(items):
                if writer is None:
                    writer = csv.DictWriter(fh, fieldnames=list(row))
                    writer.writeheader()
                writer.writerow(row)
                count += 1
        return count


class HttpSink:
    """POSTs `{"items": [...]}` batches to `<base_url>/<resource>/bulk`; upserts must be keyed by import id."""

    def __init__(self, base_url: str, api_key: str, batch_size: int = 500, max_rps: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.batch_size = batch_size
        self.min_gap = 1.0 / max_rps
        self._last = 0.0

    def _post(self, resource: str, batch: list[dict]) -> None:
        wait = self.min_gap - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(
            f"{self.base_url}/{resource}/bulk",
            data=json.dumps({"items": batch}, default=str).encode(),
            headers={"authorization": f"Bearer {self.api_key}", "content-type": "application/json"},
            method="POST",
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=60):
                    break
            except urllib.error.HTTPError as err:
                if err.code not in (429, 502, 503) or attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        self._last = time.monotonic()

    def push(self, resource: str, items: Iterable) -> int:
        batch, count = [], 0
        for row in _rows(items):
            batch.append(row)
            if len(batch) == self.batch_size:
                self._post(resource, batch)
                count += len(batch)
                batch = []
        if batch:
            self._post(resource, batch)
            count += len(batch)
        return count
