import sys
import tempfile
import unittest
from pathlib import Path

from loop_eval.benchmarks.orb_slam3.euroc_input import prepare
from loop_eval.benchmarks.orb_slam3.native_session import NativeSession


class OrbTests(unittest.TestCase):
    # The stdlib-only fixture stands in for a native executable. Bypass the
    # Windows venv redirector so terminating it terminates the actual process.

    def test_live_trace_order_integer_timestamps_and_complete_drain(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            events, logs = [], []
            session = NativeSession(
                [
                    sys._base_executable,
                    str(Path(__file__).parent / "fixtures/native_orb.py"),
                    "success",
                ],
                workspace,
                "test-revision",
            )
            result = session.execute(
                lambda kind, payload, stamp: events.append((kind, payload, stamp)), logs.append
            )
            self.assertEqual(
                [entry[1]["native_event_number"] for entry in events], list(range(1, 8))
            )
            self.assertEqual(events[1][2], 1403636579763555584)
            self.assertEqual("".join(logs).count("native diagnostic"), 10000)
            self.assertEqual(result["native_exit_code"], 0)
            self.assertEqual(len(result["trajectories"]), 2)
            self.assertTrue(result["candidate_census"]["consistent"])

    def test_invalid_native_runs_cannot_report_success(self):
        for mode in (
            "wrong_revision",
            "wrong_order",
            "no_finish",
            "truncated",
            "failed",
            "unmatched_result",
            "unverified_proposal",
            "wrong_pair",
            "census_mismatch",
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                session = NativeSession(
                    [
                        sys._base_executable,
                        str(Path(__file__).parent / "fixtures/native_orb.py"),
                        mode,
                    ],
                    Path(folder),
                    "test-revision",
                )
                with self.assertRaises((ValueError, RuntimeError)):
                    session.execute(lambda *args: None, lambda *args: None)
                self.assertIsNotNone(session.process.poll())

    def test_input_intersection_preserves_source_and_rejects_missing_imu_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stamps = [1403636579763555584, 1403636579813555584, 1403636579863555584]
            for camera, selected in (("cam0", stamps), ("cam1", stamps[:2])):
                stream = root / "sequence/mav0" / camera
                (stream / "data").mkdir(parents=True)
                (stream / "sensor.yaml").write_text("calibration")
                (stream / "data.csv").write_text(
                    "#timestamp,filename\n"
                    + "".join(f"{stamp},{stamp}.png\n" for stamp in selected)
                )
                for stamp in selected:
                    (stream / "data" / f"{stamp}.png").touch()
            imu = root / "sequence/mav0/imu0"
            imu.mkdir()
            (imu / "sensor.yaml").write_text("calibration")
            path = imu / "data.csv"
            path.write_text(
                "".join(f"{stamp},0,0,0,0,0,9.8\n" for stamp in (stamps[0] - 10, stamps[-1] + 10))
            )
            result = prepare(root / "sequence", root)
            self.assertEqual(result.frame_count, 2)
            self.assertEqual(result.unpaired_camera_frames, 1)
            self.assertEqual(
                result.timestamps_path.read_text().splitlines(), list(map(str, stamps[:2]))
            )
            self.assertEqual(
                len((root / "sequence/mav0/cam0/data.csv").read_text().splitlines()), 4
            )
            path.write_text(f"{stamps[0] + 10},0,0,0,0,0,9.8\n")
            with self.assertRaisesRegex(ValueError, "does not cover"):
                prepare(root / "sequence", root)
