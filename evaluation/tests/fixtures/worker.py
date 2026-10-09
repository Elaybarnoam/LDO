"""Synthetic subprocess for infrastructure tests; not a SLAM benchmark."""

import sys
import subprocess
import time

from modules.benchmark_publisher.publisher import BenchmarkPublisher
from benchmarks import Benchmark

mode = sys.argv[1]
publisher = BenchmarkPublisher()
if mode != "success":
    publisher.publish("started")
if mode == "timeout":
    time.sleep(60)
elif mode == "malformed":
    print("invalid JSON", flush=True)
elif mode == "no_terminal":
    pass
elif mode == "failed":
    publisher.publish("failed", {"error": "synthetic failure"})
    sys.exit(2)
elif mode == "orphan":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    publisher.publish("completed", {"child_pid": child.pid})
else:
    class SyntheticBenchmark(Benchmark):
        def execute(self):
            self.log("diagnostic\n" * 30000)
            for number in range(100):
                self.loop_proposed(number, 0, number)
            self.loop_verified(99, 0, True)
            self.constraint_inserted(99, 0)

    sys.exit(SyntheticBenchmark("synthetic", publisher).run())
