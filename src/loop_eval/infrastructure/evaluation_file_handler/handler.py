"""One active file handler; per-benchmark FIFOs and one output-writing thread."""

import json
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, Full, Queue
from zoneinfo import ZoneInfo

from loop_eval.infrastructure.evaluation_file_handler.markdown_report import render_report
from loop_eval.tasks.feature_matching.xyz.coverage import (
    empty_breakdown,
    merge_breakdown,
    validate_breakdown,
)


def artifact_reference(path: str, report_directory: Path) -> str:
    """Link artifacts even when reports use a different configured directory."""
    target = Path(path).resolve()
    try:
        return Path(os.path.relpath(target, report_directory.resolve())).as_posix()
    except ValueError:
        return target.as_posix()  # Windows paths on different drives.


class EvaluationFileHandler:
    _instance = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls):
        with cls._instance_lock:
            if cls._instance is None:
                raise RuntimeError("No active evaluation file handler")
            return cls._instance

    def __init__(
        self,
        report_path: Path,
        metadata: dict,
        benchmark_ids: list[str],
        queue_capacity: int = 1024,
    ) -> None:
        if queue_capacity < 1:
            raise ValueError("queue_capacity must be positive")
        with self._instance_lock:
            if type(self)._instance is not None:
                raise RuntimeError("An evaluation file handler is already active")
            type(self)._instance = self
        try:
            self.report_path = report_path
            self.markdown_path = report_path.with_suffix(".md")
            self.artifact_dir = report_path.with_suffix("")
            report_path.parent.mkdir(parents=True, exist_ok=True)
            # Reserve a new filename before any writer can replace it.
            with report_path.open("x", encoding="utf-8") as stream:
                stream.write("{}\n")
            with self.markdown_path.open("x", encoding="utf-8") as stream:
                stream.write("# LDO evaluation report\n\nInitializing.\n")
            self.artifact_dir.mkdir()
            self._queues = {key: Queue(maxsize=queue_capacity) for key in benchmark_ids}
            self._cases = {
                key: {
                    "benchmark_id": key,
                    "status": "pending",
                    "event_count": 0,
                    "event_counts": {},
                    "proposal_count": 0,
                    "geometric_acceptance_count": 0,
                    "constraint_count": 0,
                    "loop_query_count": 0,
                    "eligible_loop_query_count": 0,
                    "geometric_rejection_count": 0,
                    "loop_decision_count": 0,
                    "detected_loop_count": 0,
                    "rejection_reasons": {},
                    "verification_gates": {},
                    "solver_diagnostics": {},
                    "candidate_selection": {},
                    "retrieval_count": 0,
                    "empty_loop_retrieval_count": 0,
                    "detection_metrics": {
                        "tp": None,
                        "fp": None,
                        "fn": None,
                        "precision": None,
                        "recall": None,
                        "availability_reason": "Independent loop labels and evaluator are not configured",
                    },
                }
                for key in benchmark_ids
            }
            self._report = {
                "schema_version": 1,
                **metadata,
                "status": "running",
                "cases": list(self._cases.values()),
                "events_file": str(self.artifact_dir / "events.jsonl"),
            }
            self._wake = threading.Event()
            self._stop = threading.Event()
            self._failure = None
            self._accepting = True
            self._final_status = "failed"
            self._final_error = None
            self._write_report()
            self._thread = threading.Thread(target=self._consume, name="evaluation-output-writer")
            self._thread.start()
        except BaseException:
            with self._instance_lock:
                type(self)._instance = None
            raise

    def check(self) -> None:
        if self._failure is not None:
            raise RuntimeError("Evaluation output writer failed") from self._failure

    def _enqueue(self, benchmark_id: str, item: dict) -> None:
        if benchmark_id not in self._queues:
            raise ValueError(f"Unknown benchmark: {benchmark_id}")
        while True:
            self.check()
            if not self._accepting:
                raise RuntimeError("Evaluation file handler is closed")
            try:
                self._queues[benchmark_id].put(item, timeout=0.1)
                self._wake.set()
                return
            except Full:
                continue  # Backpressure; never silently discard an event.

    def enqueue(self, benchmark_id: str, event: dict) -> None:
        self._enqueue(benchmark_id, {"kind": "event", "event": event})

    def log(self, benchmark_id: str, text: str) -> None:
        self._enqueue(benchmark_id, {"kind": "stderr", "text": text})

    def record_status(self, benchmark_id: str, **fields) -> None:
        self._enqueue(benchmark_id, {"kind": "status", "fields": fields})

    def _write_report(self) -> None:
        temporary = self.report_path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(self._report, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
        self._replace(temporary, self.report_path)
        markdown_temporary = self.markdown_path.with_suffix(".md.tmp")
        markdown_temporary.write_text(
            render_report(self._report, self.report_path.name, self.artifact_dir.name),
            encoding="utf-8",
        )
        self._replace(markdown_temporary, self.markdown_path)

    @staticmethod
    def _replace(source: Path, target: Path) -> None:
        """Keep atomic replacement while tolerating brief Windows/OneDrive locks."""
        for attempt in range(9):
            try:
                source.replace(target)
                return
            except PermissionError:
                if attempt == 8:
                    raise
                time.sleep(min(0.05 * 2**attempt, 0.5))

    def _consume(self) -> None:
        logs = {}
        try:
            with (self.artifact_dir / "events.jsonl").open("x", encoding="utf-8") as events:
                while not self._stop.is_set() or any(not q.empty() for q in self._queues.values()):
                    consumed = False
                    for benchmark_id, fifo in self._queues.items():
                        try:
                            item = fifo.get_nowait()
                        except Empty:
                            continue
                        consumed = True
                        try:
                            if item["kind"] == "event":
                                event = item["event"]
                                events.write(json.dumps(event, allow_nan=False) + "\n")
                                events.flush()
                                case = self._cases[benchmark_id]
                                name = event["event_type"]
                                case["event_count"] += 1
                                case["event_counts"][name] = case["event_counts"].get(name, 0) + 1
                                if name == "loop_candidate_verified":
                                    payload = event["payload"]
                                    if payload["status"] not in {
                                        "accepted",
                                        "rejected",
                                        "insufficient_evidence",
                                    }:
                                        raise ValueError("Invalid operational verification status")
                                    per_method = case.setdefault(
                                        "shared_verification", {}
                                    ).setdefault(payload["method"], {})
                                    per_method[payload["status"]] = (
                                        per_method.get(payload["status"], 0) + 1
                                    )
                                if name == "comparison_result":
                                    if "comparison_result" in self._report:
                                        raise ValueError("Comparison result already published")
                                    self._report["comparison_result"] = event["payload"]
                                    case["benchmark_type"] = "controlled_comparison"
                                if name == "retrieval_setup":
                                    case["benchmark_type"] = "image_retrieval"
                                    case["retrieval_policy"] = event["payload"]
                                    case["image_retrieval"] = {
                                        "queries": 0,
                                        "eligible_queries": 0,
                                        "empty_queries": 0,
                                        "empty_eligible_queries": 0,
                                        "candidate_count": 0,
                                        "featureless_queries": 0,
                                        "timings_ms": {},
                                    }
                                if name == "retrieval_query":
                                    if case.get("benchmark_type") != "image_retrieval":
                                        raise ValueError("Retrieval query before setup")
                                    payload = event["payload"]
                                    summary = case["image_retrieval"]
                                    summary["queries"] += 1
                                    summary["eligible_queries"] += (
                                        payload["eligible_history_count"] > 0
                                    )
                                    summary["empty_queries"] += not payload["candidates"]
                                    summary["empty_eligible_queries"] += (
                                        payload["eligible_history_count"] > 0
                                        and not payload["candidates"]
                                    )
                                    summary["candidate_count"] += len(payload["candidates"])
                                    summary["featureless_queries"] += payload["feature_count"] == 0
                                    for operation, value in payload["timings_ms"].items():
                                        timing = summary["timings_ms"].setdefault(
                                            operation,
                                            {
                                                "count": 0,
                                                "total": 0,
                                                "minimum": value,
                                                "maximum": value,
                                            },
                                        )
                                        timing["count"] += 1
                                        timing["total"] += value
                                        timing["minimum"] = min(timing["minimum"], value)
                                        timing["maximum"] = max(timing["maximum"], value)
                                if name == "retrieval_diagnostic":
                                    case["retrieval_diagnostic"] = event["payload"]
                                if name == "candidate_check_started":
                                    case["candidate_evaluation"] = {
                                        "status": "running",
                                        "checked_pairs": 0,
                                        "excluded_pairs": 0,
                                        "exclusion_reason_counts": {},
                                        "outcome_counts": {},
                                        "reason_counts": {},
                                        "rank_outcome_counts": {},
                                        "ransac_totals": {
                                            "raw_matches": 0,
                                            "retained_matches": 0,
                                            "rejected_matches": 0,
                                            "status_counts": {},
                                        },
                                        "feature_totals": {
                                            "supported": 0,
                                            "contradicted": 0,
                                            "untestable": 0,
                                        },
                                        "coverage_breakdown": empty_breakdown(),
                                        "stereo_totals": {
                                            "pairs_with_reliable_stereo": 0,
                                            "paired_landmarks": 0,
                                            "consistent_landmarks": 0,
                                        },
                                        "provenance": event["payload"],
                                    }
                                if name == "candidate_excluded":
                                    review = case["candidate_evaluation"]
                                    payload = event["payload"]
                                    if (
                                        payload.get("eligible") is not False
                                        or payload.get("reason") != "reference_pose_required"
                                        or not payload.get("missing_reference_poses")
                                    ):
                                        raise ValueError("Invalid candidate eligibility exclusion")
                                    review["excluded_pairs"] += 1
                                    reasons = review["exclusion_reason_counts"]
                                    reasons[payload["reason"]] = (
                                        reasons.get(payload["reason"], 0) + 1
                                    )
                                if name == "candidate_checked":
                                    if "candidate_evaluation" not in case:
                                        raise ValueError(
                                            "Candidate evidence before checker initialization"
                                        )
                                    payload = event["payload"]
                                    if payload.get("accuracy_label") is not None or payload.get(
                                        "outcome"
                                    ) not in {
                                        "suspicious",
                                        "inconclusive",
                                        "overlap_supported",
                                        "feature_evaluated",
                                    }:
                                        raise ValueError(
                                            "Diagnostic candidate evidence must not claim accuracy labels"
                                        )
                                    review = case["candidate_evaluation"]
                                    if (
                                        review["provenance"].get("eligibility_rule")
                                        and payload.get("pose_evidence", {}).get("available")
                                        is not True
                                    ):
                                        raise ValueError(
                                            "Evaluated pair lacks required reference poses"
                                        )
                                    review["checked_pairs"] += 1
                                    outcome = payload["outcome"]
                                    r = payload.get("ransac")
                                    if r is not None:
                                        if (
                                            r["raw_match_count"]
                                            != r["retained_match_count"] + r["rejected_match_count"]
                                            or r["retained_match_count"]
                                            != payload["measurements"]["match_count"]
                                        ):
                                            raise ValueError(
                                                "RANSAC counts differ from retained matches"
                                            )
                                        totals = review["ransac_totals"]
                                        for target, source in (
                                            ("raw_matches", "raw_match_count"),
                                            ("retained_matches", "retained_match_count"),
                                            ("rejected_matches", "rejected_match_count"),
                                        ):
                                            totals[target] += r[source]
                                        statuses = totals["status_counts"]
                                        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
                                    stereo = payload.get("stereo")
                                    if stereo is not None:
                                        if "feature_counts" in stereo:
                                            counts = stereo["feature_counts"]
                                            if (
                                                set(counts)
                                                != {"supported", "contradicted", "untestable"}
                                                or any(
                                                    type(n) is not int or n < 0
                                                    for n in counts.values()
                                                )
                                                or sum(counts.values())
                                                != payload["measurements"]["match_count"]
                                            ):
                                                raise ValueError(
                                                    "Feature verdict counts do not account for every reported correspondence"
                                                )
                                            for verdict, count in counts.items():
                                                review["feature_totals"][verdict] += count
                                            if "coverage_breakdown" in stereo:
                                                validate_breakdown(
                                                    stereo["coverage_breakdown"],
                                                    sum(counts.values()),
                                                    counts["untestable"],
                                                )
                                                merge_breakdown(
                                                    review["coverage_breakdown"],
                                                    stereo["coverage_breakdown"],
                                                )
                                        totals = review["stereo_totals"]
                                        policy = review["provenance"]["policy"]
                                        if policy.get("version", 0) >= 4:
                                            enough = stereo.get(
                                                "reported_match_count", 0
                                            ) > 0 and stereo.get(
                                                "paired_landmarks", 0
                                            ) >= stereo.get("required_support_matches", 1)
                                        else:
                                            enough = (
                                                stereo.get("paired_landmarks", 0)
                                                >= policy["minimum_stereo_landmarks"]
                                            )
                                        totals["pairs_with_reliable_stereo"] += enough
                                        totals["paired_landmarks"] += stereo.get(
                                            "paired_landmarks", 0
                                        )
                                        totals["consistent_landmarks"] += stereo.get(
                                            "consistent_landmarks", 0
                                        )
                                    review["outcome_counts"][outcome] = (
                                        review["outcome_counts"].get(outcome, 0) + 1
                                    )
                                    rank = review["rank_outcome_counts"].setdefault(
                                        str(payload["rank"]), {}
                                    )
                                    rank[outcome] = rank.get(outcome, 0) + 1
                                    for reason in payload["reasons"]:
                                        review["reason_counts"][reason] = (
                                            review["reason_counts"].get(reason, 0) + 1
                                        )
                                if name == "candidate_check_completed":
                                    payload = dict(event["payload"])
                                    review = case["candidate_evaluation"]
                                    if (
                                        payload["checked_pairs"] != review["checked_pairs"]
                                        or payload["outcome_counts"] != review["outcome_counts"]
                                    ):
                                        raise ValueError(
                                            "Candidate evidence summary differs from received pairs"
                                        )
                                    if (
                                        payload.get("feature_totals", review["feature_totals"])
                                        != review["feature_totals"]
                                    ):
                                        raise ValueError(
                                            "Feature verdict summary differs from received pairs"
                                        )
                                    if (
                                        "coverage_breakdown" in payload
                                        and payload["coverage_breakdown"]
                                        != review["coverage_breakdown"]
                                    ):
                                        raise ValueError(
                                            "Coverage failure summary differs from received pairs"
                                        )
                                    if (
                                        payload.get("ransac_totals", review["ransac_totals"])
                                        != review["ransac_totals"]
                                    ):
                                        raise ValueError(
                                            "RANSAC summary differs from received pairs"
                                        )
                                    if (
                                        payload.get("stereo_totals", review["stereo_totals"])
                                        != review["stereo_totals"]
                                    ):
                                        raise ValueError(
                                            "Stereo summary differs from received pair evidence"
                                        )
                                    if (
                                        payload.get("excluded_pairs", 0) != review["excluded_pairs"]
                                        or payload.get("exclusion_reason_counts", {})
                                        != review["exclusion_reason_counts"]
                                    ):
                                        raise ValueError(
                                            "Candidate exclusions differ from received events"
                                        )
                                    accounted = payload["checked_pairs"] + payload.get(
                                        "excluded_pairs", 0
                                    )
                                    if payload.get("returned_pairs", accounted) != accounted:
                                        raise ValueError(
                                            "Returned candidates must equal evaluated plus excluded pairs"
                                        )
                                    if (
                                        case.get("benchmark_type") == "image_retrieval"
                                        and accounted != case["image_retrieval"]["candidate_count"]
                                    ):
                                        raise ValueError(
                                            "Independent checker missed returned candidates"
                                        )
                                    for example in payload["examples"]:
                                        example["image"] = artifact_reference(
                                            example["image"], self.report_path.parent
                                        )
                                    review.update(payload)
                                    review["status"] = "complete"
                                case["proposal_count"] += name == "loop_proposed"
                                case["geometric_acceptance_count"] += (
                                    name == "loop_verified"
                                    and event["payload"].get("accepted") is True
                                )
                                case["constraint_count"] += name == "constraint_inserted"
                                case["loop_query_count"] += name == "loop_query"
                                case["eligible_loop_query_count"] += (
                                    name == "loop_query"
                                    and event["payload"].get("eligible") is True
                                )
                                case["geometric_rejection_count"] += (
                                    name == "loop_verified"
                                    and event["payload"].get("accepted") is False
                                )
                                case["loop_decision_count"] += name == "loop_decision"
                                case["detected_loop_count"] += (
                                    name == "loop_decision"
                                    and event["payload"].get("accepted") is True
                                )
                                if name == "completed":
                                    result = event["payload"].get("result")
                                    if isinstance(result, dict) and isinstance(
                                        result.get("runtime"), dict
                                    ):
                                        case["runtime"] = result["runtime"]
                                    if isinstance(result, dict) and "candidate_census" in result:
                                        case["candidate_census"] = result["candidate_census"]
                                if name == "revisit_validation":
                                    validation = dict(event["payload"])
                                    for prefix in ("query", "historical"):
                                        key = f"{prefix}_image"
                                        if key in validation:
                                            validation[key] = (
                                                Path(validation[key])
                                                .relative_to(self.report_path.parent)
                                                .as_posix()
                                            )
                                    case["revisit_validation"] = validation
                                if name == "loop_retrieval":
                                    case["retrieval_count"] += 1
                                    case["empty_loop_retrieval_count"] += (
                                        event["payload"]["loop_candidates"] == 0
                                    )
                                if (
                                    name == "loop_candidate"
                                    and event["payload"]["candidate_kind"] == "loop"
                                ):
                                    payload = event["payload"]
                                    stage = case["candidate_selection"].setdefault(
                                        payload["selection_stage"], {}
                                    )
                                    reason = payload["selection_reason"]
                                    stage[reason] = stage.get(reason, 0) + 1
                                if name == "loop_verified":
                                    payload = event["payload"]
                                    if payload.get("accepted") is False:
                                        reason = payload.get("rejection_reason") or "unreported"
                                        case["rejection_reasons"][reason] = (
                                            case["rejection_reasons"].get(reason, 0) + 1
                                        )
                                    for gate, measurement in payload.get(
                                        "gate_measurements", {}
                                    ).items():
                                        value = measurement["observed"]
                                        summary = case["verification_gates"].setdefault(
                                            gate,
                                            {
                                                "reached": 0,
                                                "passed": 0,
                                                "failed": 0,
                                                "minimum": value,
                                                "maximum": value,
                                                "threshold": measurement["threshold"],
                                            },
                                        )
                                        if summary["threshold"] != measurement["threshold"]:
                                            raise ValueError(
                                                f"Inconsistent verification threshold: {gate}"
                                            )
                                        summary["reached"] += 1
                                        summary["passed"] += measurement["passed"] is True
                                        summary["failed"] += measurement["passed"] is False
                                        summary["minimum"] = min(summary["minimum"], value)
                                        summary["maximum"] = max(summary["maximum"], value)
                                    for name, value in payload.get("diagnostics", {}).items():
                                        summary = case["solver_diagnostics"].setdefault(
                                            name,
                                            {
                                                "count": 0,
                                                "minimum": value,
                                                "maximum": value,
                                                "total": 0,
                                            },
                                        )
                                        summary["count"] += 1
                                        summary["minimum"] = min(summary["minimum"], value)
                                        summary["maximum"] = max(summary["maximum"], value)
                                        summary["total"] += value
                            elif item["kind"] == "stderr":
                                if benchmark_id not in logs:
                                    logs[benchmark_id] = (
                                        self.artifact_dir / f"{benchmark_id}.stderr.log"
                                    ).open("x", encoding="utf-8")
                                logs[benchmark_id].write(item["text"])
                                logs[benchmark_id].flush()
                            else:
                                self._cases[benchmark_id].update(item["fields"])
                                self._write_report()
                        finally:
                            fifo.task_done()
                    if not consumed:
                        self._wake.wait(0.05)
                        self._wake.clear()
            self._report["status"] = self._final_status
            ended = datetime.now(UTC)
            self._report["ended_at_utc"] = ended.isoformat()
            self._report["ended_at"] = ended.astimezone(
                ZoneInfo(self._report.get("timezone", "UTC"))
            ).isoformat()
            if self._final_error:
                self._report["error"] = self._final_error
            self._write_report()
        except BaseException as error:
            self._failure = error
        finally:
            for stream in logs.values():
                stream.close()

    def close(self, status: str, error: str | None = None) -> None:
        """Call after producers stop; drain all queues before finalizing the report."""
        if not self._accepting:
            self.check()
            return
        self._accepting = False
        self._final_status, self._final_error = status, error
        self._stop.set()
        self._wake.set()
        self._thread.join()
        with self._instance_lock:
            type(self)._instance = None
        self.check()
