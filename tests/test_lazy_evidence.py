"""Large evidence stays on disk while feature filters remain exact."""

import json

import pytest
from tasks.feature_matching.viewer.lazy_evidence import PairStore
from tasks.feature_matching.viewer.viewer import PairViewer


def test_lazy_groups_navigation_cache_limit_and_changed_evidence(tmp_path):
    path = tmp_path / "pairs.jsonl"
    pairs = [
        {
            "pose_evidence": {"available": True},
            "query_timestamp_ns": stamp,
            "stereo": {
                "feature_results": [
                    {"verdict": v, "marker": stamp}
                    for v in ("supported", "contradicted", "untestable")
                ],
                "feature_counts": {"supported": 1, "contradicted": 1, "untestable": 1},
            },
        }
        for stamp in (1, 2)
    ]
    path.write_text("".join(json.dumps(pair) + "\n" for pair in pairs))
    store = PairStore(path, capacity=1)

    class Review:
        policy = {"version": 8}

    review = Review()
    review.pair_store = store
    review.all_pairs = list(store.headers())
    assert review.all_pairs[0]["stereo"]["feature_results"] == []
    assert store.cache == {}
    viewer = PairViewer(review)
    assert viewer.feature_group_counts == {
        "all": 6,
        "supported": 2,
        "contradicted": 2,
        "untestable": 2,
    }
    viewer.switch_xyz("contradicted")
    assert viewer.visible_landmarks(review.pairs[0]) == [{"verdict": "contradicted", "marker": 1}]
    viewer.move(1)
    assert viewer.index == 1
    assert viewer.visible_landmarks(review.pairs[1])[0]["marker"] == 2
    assert len(store.cache) == 1
    path.write_text(path.read_text().replace('"marker": 1', '"marker": 9'))
    with pytest.raises(ValueError, match="changed"):
        store.load(review.all_pairs[0])
