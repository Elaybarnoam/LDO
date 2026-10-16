"""Unseen reports preserve unknowns and scope repeated trajectory IDs by scene."""

import json

from loop_eval.tasks.reference_geometry.direct_report import aggregate
from loop_eval.tasks.unseen_tartanair import report


def result_fixture():
    environments = []
    for name, empty in (("SceneA", False), ("SceneB", True)):
        sequence = {
            "trajectory": "P000",
            "features": {
                "orb": {"supported": 0, "contradicted": 0, "untestable": 1, "zero_match_pairs": 0},
                "ldo": {
                    "supported": int(not empty),
                    "contradicted": 0,
                    "untestable": 1,
                    "zero_match_pairs": 0,
                },
            },
            "retrieval": {
                "5": {
                    "orb": {
                        "returned_pairs": int(not empty),
                        "true_positive_pairs": 0,
                        "false_positive_pairs": 0,
                        "unknown_pairs": int(not empty),
                        "confirmed_events": int(not empty),
                        "detected_confirmed_events": 0,
                    },
                    "ldo": {
                        "returned_pairs": 2 * int(not empty),
                        "true_positive_pairs": int(not empty),
                        "false_positive_pairs": 0,
                        "unknown_pairs": int(not empty),
                        "confirmed_events": int(not empty),
                        "detected_confirmed_events": int(not empty),
                    },
                }
            },
        }
        environments.append(
            {
                "environment": name,
                "report": f"/{name}/report.json",
                "report_sha256": "a" * 64,
                "task": {"aggregate": aggregate([sequence], 5), "sequences": [sequence]},
            }
        )
    return {
        "environments": environments,
        "protocol": {"top_k": 5},
        "freeze_sha256": "b" * 64,
        "aggregate": aggregate([e["task"]["sequences"][0] for e in environments], 5),
    }


def test_unknown_bounds_and_zero_denominators_are_not_false_positives():
    result = result_fixture()
    text = report.render(result)
    assert "| SceneA | orb | Unavailable | 0.0% to 100.0% |" in text
    assert "| SceneA | ldo | 100.0% | 50.0% to 100.0% |" in text
    assert "| SceneB | ldo | Unavailable | Unavailable |" in text
    assert "| SceneA | P000 | ldo |" in text
    assert "| SceneB | P000 | ldo |" in text
    assert result["aggregate"]["orb"]["retrieval"]["false_positive_pairs"] == 0
    assert result["aggregate"]["ldo"]["retrieval"]["confirmed_events"] == 1


def test_combined_report_uses_shared_file_handler(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "ROOT", tmp_path)
    config = tmp_path / "config.yaml"
    config.write_text("version: 1\n")
    result = result_fixture()
    path = report.publish(result, config)
    document = json.loads(path.read_text())
    assert document["status"] == "completed"
    assert document["comparison_result"]["unseen_tartanair"]["freeze_sha256"] == "b" * 64
    assert path.with_suffix(".md").read_text().startswith("# LDO versus ORB: unseen")
    assert (path.with_suffix("") / "source/unseen_tartanair/workflow.py").exists()
