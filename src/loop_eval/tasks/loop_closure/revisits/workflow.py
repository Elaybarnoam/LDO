"""Independent-event task orchestration; final writing stays in the FIFO handler."""

import hashlib
import json
from pathlib import Path

import yaml

from loop_eval.paths import project_root

from ..comparison.metrics import read_trace
from ..comparison.reference import sha256, verify_images, write_json
from .metrics import evaluate, paired_event_uncertainty
from .operating_points import check_frozen_operating_points, select
from .reference import load_frozen

ROOT = project_root()


def fingerprints(config):
    paths = {
        "ldo_configuration": Path(config["matching"]["ldo_config"]),
        "orb_configuration": Path(config["matching"]["orb_config"]),
        "xyz_policy": Path(config["matching"]["xyz_config"]),
        "verifier_policy": ROOT / "configs/verification/config.yaml",
        "pose_assessment_policy": ROOT / "configs/evaluation/loop_closure/assessment.yaml",
    }
    result = {name: sha256(path) for name, path in paths.items()}
    # Dataset identity changes between sequences; freeze algorithm settings.
    orb = yaml.safe_load(paths["orb_configuration"].read_text(encoding="utf-8"))
    algorithm = {
        key: value
        for key, value in orb.items()
        if key not in {"sequence", "dataset_root", "native_dataset_root", "candidate_evaluation"}
    }
    result["orb_configuration"] = hashlib.sha256(
        json.dumps(algorithm, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    return result


def report(
    config: dict,
    frozen_root: Path,
    verification_report: Path | None = None,
    operating_points: Path | None = None,
    select_output: Path | None = None,
) -> dict:
    manifest, reference, policy, events = load_frozen(frozen_root)
    if manifest["protocol"] != config["protocol"]:
        raise ValueError("Frozen reference and replay protocol differ")
    for filename, expected in manifest["reference_files"].items():
        if sha256(Path(filename)) != expected:
            raise ValueError("Reference poses or calibration changed")
    stamps = sorted(map(int, manifest["images"]))
    queries = [q["timestamp_ns"] for q in manifest["queries"]]
    traces, sources = {}, {"frozen_reference_manifest": sha256(frozen_root / "manifest.json")}
    for name, paths in config["methods"].items():
        verify_images(manifest, Path(paths["replay"]))
        traces[name] = read_trace(
            Path(paths["trace"]),
            stamps,
            config["protocol"]["exclusion_ns"],
            max(config["protocol"]["k_values"]),
        )
        sources[f"{name}_trace"] = sha256(Path(paths["trace"]))
    settings = fingerprints(config)
    selected_artifact = json.loads(operating_points.read_text()) if operating_points else None
    if selected_artifact:
        check_frozen_operating_points(
            selected_artifact, manifest["sequence"], policy, config["protocol"], settings
        )
        sources["frozen_operating_points"] = sha256(operating_points)
    result = {
        "sequence": manifest["sequence"],
        "reference_path": str(frozen_root),
        "protocol": config["protocol"],
        "retrieval": {},
        "claim_validated": False,
        "claim_status": "Independent revisit events are primary; unknown reference labels withhold accuracy claims.",
        "source_sha256": sources,
        "independent_revisits": {
            "policy": policy,
            "preparation": json.loads((frozen_root / "preparation.json").read_text()),
            "reference": manifest["freeze"],
            "metrics": {},
            "paired_uncertainty": {},
            "matched_precision": {},
            "secondary_metrics": {},
            "configuration_fingerprints": settings,
        },
    }
    task = result["independent_revisits"]
    proposal_pairs = set()
    proposal_groups = []
    with (frozen_root / "proposals.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            proposal = json.loads(line)
            group = {tuple(pair) for pair in proposal["pairs"]}
            proposal_groups.append(group)
            proposal_pairs.update(group)
    task["pose_proposal_diagnostics"] = {
        str(k): {
            name: {
                "returned_pairs_inside_proposal": sum(
                    (q, c["historical_timestamp_ns"]) in proposal_pairs
                    for q in queries
                    for c in trace[q][:k]
                ),
                "proposal_intervals_with_a_return": sum(
                    any(
                        (q, c["historical_timestamp_ns"]) in group
                        for q in queries
                        for c in trace[q][:k]
                    )
                    for group in proposal_groups
                ),
                "total_proposal_intervals": len(proposal_groups),
                "is_correct_loop_measurement": False,
            }
            for name, trace in traces.items()
        }
        for k in config["protocol"]["k_values"]
    }

    for k in config["protocol"]["k_values"]:
        scores = {
            name: evaluate(reference, trace, queries, events, k) for name, trace in traces.items()
        }
        task["metrics"][str(k)] = scores
        task["paired_uncertainty"][str(k)] = paired_event_uncertainty(
            scores["orb"],
            scores["ldo"],
            config["protocol"]["seed"],
            config["protocol"]["bootstrap_block_queries"],
            config["protocol"]["bootstrap_samples"],
        )
    if select_output:
        if manifest["sequence"] not in policy["development_sequences"]:
            raise ValueError("Operating-point selection is restricted to development sequences")
        points = {
            str(k): {
                name: select(reference, trace, queries, events, k, policy["target_precision"])
                for name, trace in traces.items()
            }
            for k in config["protocol"]["k_values"]
        }
        artifact = {
            "version": 1,
            "available": all(
                p["available"] for methods in points.values() for p in methods.values()
            ),
            "development_sequence": manifest["sequence"],
            "policy": policy,
            "protocol": config["protocol"],
            "configuration_fingerprints": settings,
            "source_sha256": dict(sources),
            "points": points,
        }
        write_json(select_output, artifact)
        task["matched_precision"] = artifact
    elif selected_artifact:
        task["matched_precision"] = {
            "mode": "frozen_held_out",
            "metrics": {
                str(k): {
                    name: evaluate(
                        reference,
                        traces[name],
                        queries,
                        events,
                        k,
                        selected_artifact["points"][str(k)][name]["score_threshold"],
                    )
                    for name in traces
                }
                for k in config["protocol"]["k_values"]
            },
        }
    else:
        task["matched_precision"] = {
            "available": False,
            "reason": "No frozen development operating points supplied",
        }
    if verification_report:
        saved = json.loads(verification_report.read_text())
        if saved.get("status") not in {"completed", "complete"}:
            raise ValueError("Secondary verification report is incomplete")
        secondary = saved["comparison_result"]
        if secondary["sequence"] != manifest["sequence"]:
            raise ValueError("Secondary verification sequence differs")
        for key in ("exclusion_ns", "pose_tolerance_ms", "k_values"):
            if secondary["protocol"][key] != config["protocol"][key]:
                raise ValueError("Secondary verification replay protocol differs")
        v = secondary["verified_connections"]
        if (
            v["scope"]["fixed_pairs"]
            or v["scope"]["query_limit"] is not None
            or v["scope"]["selected_reference_queries_only"]
        ):
            raise ValueError(
                "Secondary event evaluation requires full detector verification replay"
            )
        path = Path(v["artifact_directory"]) / "pairs.jsonl"
        if sha256(path) != v["pairs_sha256"]:
            raise ValueError("Secondary verification evidence changed")
        accepted, usable = {n: set() for n in traces}, {n: set() for n in traces}
        seen = {name: set() for name in traces}
        with path.open() as stream:
            for line in stream:
                row = json.loads(line)
                name = row["method"]
                pair = (row["query_timestamp_ns"], row["historical_timestamp_ns"])
                if name not in seen or pair in seen[name]:
                    raise ValueError("Duplicate or unknown-method secondary verification pair")
                seen[name].add(pair)
                if pair not in reference or not any(
                    c["historical_timestamp_ns"] == pair[1] for c in traces[name][pair[0]]
                ):
                    raise ValueError("Secondary verification pair differs from frozen replay")
                if [row[f"{side}_image_sha256"] for side in ("query", "historical")] != [
                    manifest["images"][str(t)]["sha256"] for t in pair
                ]:
                    raise ValueError("Secondary verification image differs")
                if row["verification"]["status"] == "accepted":
                    accepted[name].add(pair)
                    if row["pose_assessment"].get("within_tolerance"):
                        usable[name].add(pair)
        for name, trace in traces.items():
            expected = {
                (q, c["historical_timestamp_ns"])
                for q in queries
                for c in trace[q]
                if (q, c["historical_timestamp_ns"]) in reference
            }
            if seen[name] != expected:
                raise ValueError(
                    "Secondary verification does not cover the full eligible candidate set"
                )
        task["secondary_metrics"] = {
            str(k): {
                name: {
                    "operational_accepted": evaluate(
                        reference, traces[name], queries, events, k, accepted=accepted[name]
                    ),
                    "pose_accurate_accepted": evaluate(
                        reference, traces[name], queries, events, k, accepted=usable[name]
                    ),
                }
                for name in traces
            }
            for k in config["protocol"]["k_values"]
        }
        task["secondary_counts"] = {
            name: {
                "operational_accepted": len(accepted[name]),
                "accepted_pose_within_provisional_tolerance": len(usable[name]),
            }
            for name in traces
        }
        task["assessment_policy"] = v["assessment_policy"]
        sources["secondary_report"] = sha256(verification_report)
        if secondary.get("features"):
            result["features"] = secondary["features"]
            task["external_xyz_evidence_is_unfiltered"] = True
    return result


def aggregate(reports: list[Path]) -> dict:
    rows, sources = {}, {}
    for path in reports:
        saved = json.loads(path.read_text())
        if saved.get("status") not in {"complete", "completed"}:
            raise ValueError("Event aggregation requires completed reports")
        r = saved["comparison_result"]
        if r["sequence"] in rows or "independent_revisits" not in r:
            raise ValueError("Duplicate sequence or incompatible task report")
        rows[r["sequence"]] = r
        sources[str(path)] = sha256(path)
    if not rows:
        raise ValueError("No event reports")
    first = next(iter(rows.values()))
    for r in rows.values():
        if (
            r["protocol"] != first["protocol"]
            or r["independent_revisits"]["policy"] != first["independent_revisits"]["policy"]
            or r["independent_revisits"]["configuration_fingerprints"]
            != first["independent_revisits"]["configuration_fingerprints"]
        ):
            raise ValueError("Event suite policies/configurations differ")
    metrics = {}
    for k in first["independent_revisits"]["metrics"]:
        metrics[k] = {}
        for name in ("orb", "ldo"):
            metrics[k][name] = {}
            for metric in ("precision", "event_recall"):
                values = [
                    r["independent_revisits"]["metrics"][k][name][metric] for r in rows.values()
                ]
                metrics[k][name][metric] = {
                    "equal_sequence_mean": sum(values) / len(values)
                    if all(x is not None for x in values)
                    else None,
                    "available_sequences": sum(x is not None for x in values),
                    "total_sequences": len(values),
                }
    return {
        "sequence": "suite",
        "protocol": first["protocol"],
        "retrieval": {},
        "claim_validated": False,
        "claim_status": "Equal-sequence event aggregate; unavailable metrics remain unavailable.",
        "source_sha256": sources,
        "independent_event_suite": metrics,
        "sequences": rows,
    }
