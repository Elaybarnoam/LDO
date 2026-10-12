"""Deterministic fixed development pairs from the original retrieval union."""

import json
from pathlib import Path

from ldo.artifacts import identity, sha256, write_json


def prepare(settings, project_root, output):
    source_path = project_root / settings["source_results"]
    source = json.loads(source_path.read_text())
    contexts = []
    for environment in source["environments"]:
        name = environment["environment"]
        if sha256(Path(environment["report"])) != environment["report_sha256"]:
            raise ValueError("Original model report changed")
        for sequence in environment["task"]["sequences"]:
            trajectory = sequence["trajectory"]
            roles = [
                role for role in ("fit", "validate") if trajectory in settings[role].get(name, [])
            ]
            if len(roles) != 1:
                raise ValueError("Development trajectory must have one explicit split")
            pair_path = Path(environment["task"]["artifact_directory"]) / trajectory / "pairs.jsonl"
            if sha256(pair_path) != sequence["artifact_hashes"]["pairs"]:
                raise ValueError("Original retrieval evidence changed")
            union = {}
            with pair_path.open() as stream:
                for line in stream:
                    row = json.loads(line)
                    key = row["query_timestamp_ns"], row["historical_timestamp_ns"]
                    label = row["reference"]["label"]
                    if key in union and union[key]["label"] != label:
                        raise ValueError("Original pair labels disagree")
                    union[key] = {"q": key[0], "h": key[1], "label": label}
            selected = []
            for label, limit in settings["pair_limits"].items():
                rows = [r for r in union.values() if r["label"] == label]
                rows.sort(
                    key=lambda r: identity([settings["seed"], name, trajectory, r["q"], r["h"]])
                )
                selected.extend(rows[:limit])
            selected.sort(key=lambda r: (r["q"], r["h"]))
            contexts.append(
                {
                    "environment": name,
                    "trajectory": trajectory,
                    "split": roles[0],
                    "reference": sequence["reference"],
                    "pairs": selected,
                    "orb_root": str(
                        Path(environment["task"]["detector_evidence_directory"])
                        / trajectory
                        / "orb"
                    ),
                    "pair_source_sha256": sha256(pair_path),
                }
            )
    value = {
        "source_sha256": sha256(source_path),
        "contexts": contexts,
        "seed": settings["seed"],
        "limits": settings["pair_limits"],
    }
    path = output / "fixed-pairs.json"
    if path.exists() and json.loads(path.read_text()) != value:
        raise ValueError("Fixed development pairs changed; start a new experiment")
    write_json(path, value)
    return contexts
