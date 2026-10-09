# Evaluation process and output contract

`runner.py` only invokes `Orchestrator().run()`. The orchestrator loads configuration, initializes the singleton file handler, and starts, monitors, waits for, or stops benchmark adapters. The handler has no process-management responsibilities.

```text
Benchmark adapter -> stdout JSON line -> orchestrator listener
                                      -> handler.enqueue(benchmark_id, event)
                                      -> that benchmark's bounded FIFO
                                      -> single writer
                                      -> events.jsonl and timestamped report
```

Each benchmark is a subprocess with its own Python/native memory. The parent singleton is not directly accessible from its memory. Pipes provide IPC (inter-process communication). Stdout carries protocol messages; stderr carries diagnostics. Native SLAM logs must be captured or redirected by the adapter, not mixed with its event stdout.

## Configure and run

Add real adapters to `evaluation/src/config.yaml`. For example, after creating the named adapter:

```yaml
benchmarks:
  - id: orb_slam3_original
    command: ["{python}", "evaluation/src/benchmarks/orb_slam3.py"]
    cwd: .
    timeout_seconds: 600
```

Commands are argument lists executed without a shell. Supported substitutions are `{python}`, `{project_root}`, and `{dataset_root}`. Relative working and dataset/output paths resolve from the project root. Set `run.max_parallel` to control concurrency and `output.queue_capacity` to bound each FIFO.

```powershell
uv run python evaluation/src/runner.py
uv run python -m unittest discover -s evaluation/tests -v
```

The installed configuration has no benchmark entries. It intentionally rejects an empty evaluation before creating output. Test fixtures are synthetic processes, not SLAM benchmarks or evidence of detection quality.

## Publish from an adapter

Concrete benchmark adapters should inherit the abstract `Benchmark` class, which supplies lifecycle events, cleanup handling, diagnostics, and measurement publishing. See [benchmark inheritance](benchmark-inheritance.md). The direct publisher interface below is the underlying protocol; subclasses normally use inherited `publish()` and loop-event helpers and leave terminal events to `run()`.

The orchestrator supplies `EVALUATION_RUN_ID`, `EVALUATION_BENCHMARK_ID`, `EVALUATION_DATASET_ROOT`, and `EVALUATION_SEED` environment variables, and exposes the evaluation source modules through `PYTHONPATH`.

```python
from modules.benchmark_publisher.publisher import BenchmarkPublisher

publisher = BenchmarkPublisher()
publisher.publish("started")
# Invoke/instrument the native benchmark and publish its real measurements.
publisher.publish("loop_proposed", {"query_keyframe_id": 100, "historical_keyframe_id": 10},
                  sequence_id="MH_01_easy", dataset_timestamp_ns=1403636579763555584)
publisher.publish("completed")
```

This example illustrates the protocol; its keyframe IDs are placeholders. Other events include `loop_verified` with an explicit boolean `accepted`, `constraint_inserted`, `timing`, and `failed`. Payloads are JSON objects. The publisher assigns contiguous event numbers starting at 1 and rejects publishing after a terminal event. It is safe to call from multiple threads inside one adapter process; use one publisher per adapter.

The orchestrator checks identity, protocol version, event ordering, and message structure. A successful process must both emit `completed` and exit with code zero. Malformed events, a `failed` terminal event, missing completion, timeout, nonzero exit, or leftover child processes are recorded as failures. Adapters must wait for native children before completing.

## File ownership and queue behavior

One active `EvaluationFileHandler` exists in the parent. `EvaluationFileHandler.instance()` retrieves it; constructing another while it is active is rejected. Each run closes and releases it after producers stop and FIFOs drain.

Each benchmark's events and stderr chunks enter its own `queue.Queue`. The writer consumes one queued item per benchmark per pass, preserving the arrival order within that FIFO. There is no global chronological ordering guarantee across processes. Full queues apply backpressure rather than discarding measurements. For latency comparisons, distinguish IPC/output overhead from the benchmark's reported computation time.

Reports are named from the start time in `Asia/Jerusalem` by default, with microseconds and a random run suffix. Local and UTC timestamps are stored in the report. File creation is exclusive; updates use temporary-file replacement. The same-stem artifact directory contains the flushed `events.jsonl` stream and per-benchmark stderr logs. Atomic replacement prevents a half-written JSON report but is not a guarantee of durability after power loss.

The handler organizes raw event counts, proposal counts, explicit geometric acceptances, constraint counts, configuration, process outcomes, and execution duration. Independent TP/FP/FN, precision, and recall are `null` with an availability reason until a ground-truth evaluator is implemented. Unknown event types are retained for future evaluators.

The orchestrator owns native process trees using Windows Job Objects or POSIX process groups. Timeouts and cancellation stop those trees. At normal exit, remaining descendants are cleaned up and the case fails. Reports finish as `complete`, `partial`, or `failed`; runs containing failed cases raise `EvaluationRunError` with the report path. An output-writer failure propagates to the orchestrator and cannot be reported as success.
