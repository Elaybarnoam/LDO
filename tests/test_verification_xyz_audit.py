"""Audit cannot silently discard rejects or join unrelated observations."""

from copy import deepcopy

import pytest
from tasks.loop_closure.disagreement import join_evidence


def evidence():
    profiles = {"orb": {"pairs": {}}, "ldo": {"pairs": {}}}
    records = []
    for i, status in enumerate(("accepted", "rejected", "insufficient_evidence")):
        pair = (100, i)
        profiles["ldo"]["pairs"][pair] = {
            "images": ["q", "h"],
            "counts": {"supported": 8, "contradicted": 1, "untestable": 3},
        }
        records.append(
            {
                "method": "ldo",
                "query_timestamp_ns": 100,
                "historical_timestamp_ns": i,
                "query_image_sha256": "q",
                "historical_image_sha256": "h",
                "rank": i + 1,
                "verification": {
                    "status": status,
                    "reason": "reason",
                    "diagnostics": {"reported_matches": 12},
                },
                "pose_assessment": {"available": False},
            }
        )
    return profiles, records


def test_rejected_and_untestable_candidates_keep_xyz_evidence():
    profiles, records = evidence()
    joined = join_evidence(profiles, records)
    groups = joined["methods"]["ldo"]["by_operational_status"]
    assert sum(g["feature_totals"]["supported"] for g in groups.values()) == 24
    assert sum(g["feature_totals"]["untestable"] for g in groups.values()) == 9
    assert joined["methods"]["ldo"]["strong_support_by_status"]["rejected"] == 1
    assert not joined["highlight_is_operational_gate"]
    assert profiles == evidence()[0]


@pytest.mark.parametrize("failure", ["missing", "image", "count", "duplicate"])
def test_incompatible_or_missing_evidence_fails(failure):
    profiles, records = evidence()
    if failure == "missing":
        del profiles["ldo"]["pairs"][100, 1]
    elif failure == "image":
        records[1]["historical_image_sha256"] = "another"
    elif failure == "count":
        records[1]["verification"]["diagnostics"]["reported_matches"] = 99
    else:
        records.append(deepcopy(records[1]))
    with pytest.raises(ValueError):
        join_evidence(profiles, records)


def test_unknown_evidence_is_not_strong_support():
    profiles, records = evidence()
    profiles["ldo"]["pairs"][100, 1]["counts"] = {
        "supported": 0,
        "contradicted": 0,
        "untestable": 12,
    }
    result = join_evidence(profiles, records)
    row = next(r for r in result["rows"] if r["status"] == "rejected")
    assert not row["strong_xyz_support"]
    assert row["support_among_judgeable"] is None


def test_report_displays_rejected_supported_features_without_relabeling():
    from tasks.loop_closure.comparison.comparison import render_comparison

    profiles, records = evidence()
    result = {
        "sequence": "test",
        "claim_status": "No claim",
        "retrieval": {},
        "verification_xyz_audit": join_evidence(profiles, records),
    }
    report = render_comparison(result)
    assert "| ldo | rejected | 1 | 8 | 1 | 3 | 1 |" in report
    assert "Rejected candidates with strong XYZ support" in report
    assert "changes no verifier or XYZ gate" in report
