"""Native trace protocol fixture; does not simulate SLAM accuracy."""
import json
import os
from pathlib import Path
import sys
import time

mode = sys.argv[1]
trace = Path(os.environ["ORB_EVALUATION_TRACE"])
pair = {"attempt_id": 1, "query_keyframe_id": 9, "historical_keyframe_id": 2,
        "query_frame_id": 91, "historical_frame_id": 20, "query_map_id": 0, "historical_map_id": 0,
        "query_timestamp_ns": 1403636579763555584, "historical_timestamp_ns": 1403636578763555584,
        "stage": "bow_geometry"}
events = [
    {"schema_version": 1, "event_number": 1, "event_type": "instrumentation_ready", "dataset_timestamp_ns": None,
     "payload": {"revision": "test-revision", "instrumentation_version": 6, "sensor": "stereo_imu"}},
    {"schema_version": 1, "event_number": 2, "event_type": "loop_proposed", "dataset_timestamp_ns": 1403636579763555584,
     "payload": pair},
    {"schema_version": 1, "event_number": 3, "event_type": "loop_verified", "dataset_timestamp_ns": 1403636579763555584,
     "payload": {**pair, "accepted": True, "projection_matches": 81, "verification_seconds": 0.001}},
    {"schema_version": 1, "event_number": 4, "event_type": "native_finished", "dataset_timestamp_ns": None, "payload": {}},
]
if mode == "wrong_revision":
    events[0]["payload"]["revision"] = "other"
elif mode == "wrong_order":
    events[2]["event_number"] = 7
elif mode == "no_finish":
    events.pop()
elif mode == "unmatched_result":
    events[2]["payload"]["attempt_id"] = 2
elif mode == "unverified_proposal":
    events[2]["event_type"] = "timing"
    events[2]["payload"] = {"operation": "tracking", "seconds": 0.01}
elif mode == "wrong_pair":
    events[2]["payload"]["historical_timestamp_ns"] += 1
events[1:1] = [
    {"schema_version": 1, "event_type": "loop_candidate", "dataset_timestamp_ns": pair["query_timestamp_ns"],
     "payload": {**pair, "candidate_kind": "loop", "selection_stage": "top_k", "selection_reason": "selected"}},
    {"schema_version": 1, "event_type": "loop_retrieval", "dataset_timestamp_ns": pair["query_timestamp_ns"],
     "payload": {"loop_candidates": 1, "merge_candidates": 0}},
    {"schema_version": 1, "event_type": "loop_candidate", "dataset_timestamp_ns": pair["query_timestamp_ns"],
     "payload": {**pair, "candidate_kind": "loop", "selection_stage": "geometry_filter", "selection_reason": "passed"}},
]
for number, event in enumerate(events, 1):
    event["event_number"] = number
if mode == "wrong_order":
    events[-1]["event_number"] = 99
elif mode == "census_mismatch":
    events[2]["payload"]["loop_candidates"] = 2
with trace.open("wb") as stream:
    for event in events:
        line = (json.dumps(event) + "\n").encode()
        stream.write(line[:10])
        stream.flush()
        time.sleep(0.005)
        stream.write(line[10:])
        stream.flush()
    if mode == "truncated":
        stream.write(b'{"schema_version":')
for name in ("f_evaluation.txt", "kf_evaluation.txt"):
    Path(name).write_text("1403636579763555584 0 0 0 0 0 0 1\n")
print("native diagnostic " * 10000, flush=True)
if mode == "failed":
    sys.exit(2)
