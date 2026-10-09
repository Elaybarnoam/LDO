"""Exercise the real C++ logger with isolated keyframe identities, not SLAM accuracy."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from benchmarks.loop_events import PAIR_EVENTS, QUERY_EVENTS, normalize_loop_event


@unittest.skipUnless(os.name == "posix" and shutil.which("c++"), "Native logger compilation runs in Linux")
class NativeLoopLoggerTests(unittest.TestCase):
    def test_cpp_decisions_preserve_integer_pair_times_and_pass_shared_contract(self):
        instrumentation = SRC / "benchmarks/orb_slam3/instrumentation"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Map.h").write_text("#pragma once\nstruct Map { unsigned long GetId() { return 0; } };\n")
            (root / "KeyFrame.h").write_text(
                '#pragma once\n#include "Map.h"\nnamespace ORB_SLAM3 { struct KeyFrame { unsigned long mnId, mnFrameId; '
                'double mTimeStamp; Map* map; Map* GetMap() { return map; } }; }\n')
            (root / "main.cc").write_text('''
#include "EvaluationEvents.h"
#include "KeyFrame.h"
#include <string>
int main() {
    using namespace ORB_SLAM3;
    EvaluationEvents::initialize();
    Map map;
    KeyFrame history{2, 20, std::stod("1403636578763555584") / 1e9, &map};
    KeyFrame query{9, 91, std::stod("1403636579763555584") / 1e9, &map};
    EvaluationEvents::keyframe(&history);
    EvaluationEvents::keyframe(&query);
    EvaluationEvents::query(&query, true, "eligible");
    EvaluationEvents::candidate(&query, &history, "database_word_pool", "direct_connected");
    EvaluationEvents::retrieval(&query, 0, 0);
    { EvaluationEvents::Attempt attempt(&query, &history, "bow_geometry");
      attempt.gate("bow_matches", 12, 20);
      attempt.observe("ransac_usable_correspondences", 8);
      attempt.reject("insufficient_3d_correspondences"); }
    { EvaluationEvents::Attempt attempt(&query, &history, "temporal_refinement");
      attempt.gate("projection_matches", 101, 100);
      attempt.accepted = true; attempt.matches = 101; }
    EvaluationEvents::emit("loop_decision", EvaluationEvents::pairPayload(&query, &history) +
                           ",\\\"accepted\\\":true,\\\"stage\\\":\\\"native_final_gate\\\"", query.mTimeStamp);
    EvaluationEvents::pairEvent("constraint_inserted", &query, &history);
    EvaluationEvents::emit("native_finished", "");
}
''')
            binary = root / "logger"
            subprocess.run(["c++", "-std=c++14", "-pthread", "-I", str(root), "-I", str(instrumentation),
                            str(instrumentation / "EvaluationEvents.cc"), str(root / "main.cc"), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            timestamps = root / "timestamps.txt"
            timestamps.write_text("1403636578763555584\n1403636579763555584\n")
            trace = root / "trace.jsonl"
            env = {**os.environ, "ORB_EVALUATION_TRACE": str(trace), "ORB_EVALUATION_TIMESTAMPS": str(timestamps)}
            subprocess.run([str(binary)], env=env, check=True)
            events = [json.loads(line) for line in trace.read_text().splitlines()]
            self.assertEqual(events[0]["payload"]["instrumentation_version"], 6)
            normalized = [normalize_loop_event(event["event_type"], event["payload"], event["dataset_timestamp_ns"],
                                               "orb_slam3_dbow2") for event in events
                          if event["event_type"] in PAIR_EVENTS | QUERY_EVENTS]
            verified = [event for event in events if event["event_type"] == "loop_verified"]
            self.assertEqual([event["payload"]["accepted"] for event in verified], [False, True])
            self.assertIsNone(verified[0]["payload"]["projection_matches"])
            self.assertEqual(verified[0]["payload"]["rejection_reason"], "insufficient_3d_correspondences")
            self.assertEqual(verified[0]["payload"]["diagnostics"]["ransac_usable_correspondences"], 8)
            self.assertEqual(verified[0]["payload"]["gate_measurements"]["bow_matches"],
                             {"observed": 12, "threshold": 20, "passed": False})
            self.assertIsNone(verified[1]["payload"]["rejection_reason"])
            for data in normalized:
                if "historical_timestamp_ns" in data:
                    self.assertEqual(data["historical_timestamp_ns"], 1403636578763555584)
                    self.assertEqual(data["query_timestamp_ns"], 1403636579763555584)
            self.assertEqual(events[-1]["event_type"], "native_finished")
