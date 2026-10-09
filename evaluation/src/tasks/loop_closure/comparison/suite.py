"""Equal-sequence aggregation, preserving missing metrics instead of hiding them."""

import json
from pathlib import Path

import numpy as np

from .reference import sha256


def aggregate(reports: list[Path]) -> dict:
    if not reports:
        raise ValueError("No comparison reports supplied")
    sequences = {}
    hashes = {}
    protocol = None
    for path in reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("status") not in {"complete", "completed"}:
            raise ValueError("Suite requires completed reports")
        result = report["comparison_result"]
        if result["sequence"] in sequences:
            raise ValueError("Duplicate sequence would bias equal-sequence aggregation")
        if protocol is not None and result["protocol"] != protocol:
            raise ValueError("Suite protocols differ")
        protocol = result["protocol"]
        sequences[result["sequence"]] = result
        hashes[str(path)] = sha256(path)
    metrics = {}
    for k in map(str, protocol["k_values"]):
        metrics[k] = {}
        for method in ("orb", "ldo"):
            rows = [r["retrieval"][k][method] for r in sequences.values()]
            metrics[k][method] = {}
            for name in ("precision", "complete_query_pair_recall", "complete_query_success"):
                values = [row[name] for row in rows]
                metrics[k][method][name] = {
                    "equal_sequence_mean": float(np.mean(values))
                    if all(v is not None for v in values)
                    else None,
                    "available_sequences": sum(v is not None for v in values),
                    "total_sequences": len(rows),
                }
    result = {
        "sequence": "suite",
        "claim_status": "Suite aggregation is descriptive; no automatic superiority claim.",
        "claim_validated": False,
        "source_sha256": hashes,
        "protocol": protocol,
        "retrieval": {},
        "equal_sequence_metrics": metrics,
        "sequences": sequences,
        "limitation": "Configuration/model training overlap and held-out split must be audited separately.",
    }
    verified = [r.get("verified_connections") for r in sequences.values()]
    if any(verified):
        if not all(verified):
            raise ValueError("Cannot mix verified-loop and retrieval-only sequence reports")
        if any(
            v["verifier_policy"] != verified[0]["verifier_policy"]
            or v["assessment_policy"] != verified[0]["assessment_policy"]
            for v in verified
        ):
            raise ValueError("Operational or assessment policies differ across sequences")
        aggregates = {}
        for k in map(str, protocol["k_values"]):
            aggregates[k] = {}
            for method in ("orb", "ldo"):
                aggregates[k][method] = {}
                for name in ("pair_recall", "query_success"):
                    values = [v["query_metrics"][k][method][name] for v in verified]
                    aggregates[k][method][name] = {
                        "equal_sequence_mean": float(np.mean(values))
                        if all(value is not None for value in values)
                        else None,
                        "available_sequences": sum(value is not None for value in values),
                        "total_sequences": len(values),
                    }
        result["verified_equal_sequence_metrics"] = aggregates
    return result
