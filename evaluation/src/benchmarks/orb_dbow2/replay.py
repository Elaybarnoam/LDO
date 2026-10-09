"""Deterministic, tracking-independent cam0 replay shared by detectors."""

import csv
from decimal import Decimal
from pathlib import Path


def make_replay(sequence: Path, sample_hz):
    frequency = Decimal(str(sample_hz))
    if not frequency.is_finite() or frequency <= 0 or frequency > 20:
        raise ValueError("sample_hz must be in (0, 20]")
    period = Decimal(1_000_000_000) / frequency
    selected, previous, target = [], -1, None
    camera = sequence / "mav0" / "cam0"
    with (camera / "data.csv").open(encoding="utf-8") as stream:
        for row in csv.reader(stream):
            if not row or row[0].startswith("#"):
                continue
            stamp = int(row[0])
            if stamp <= previous:
                raise ValueError("Camera timestamps must be strictly increasing")
            previous = stamp
            if target is None:
                target = Decimal(stamp)
            if stamp < target:
                continue
            filename = row[1].strip()
            if Path(filename).name != filename or "\t" in filename or "\n" in filename:
                raise ValueError("Unsafe image filename")
            image = camera / "data" / filename
            if not image.is_file():
                raise ValueError(f"Missing camera image: {image}")
            selected.append((stamp, image))
            while target <= stamp:
                target += period
    if not selected:
        raise ValueError("Camera sequence is empty")
    return selected
