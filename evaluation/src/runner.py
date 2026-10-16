"""Compatibility launcher; install the project with uv sync first."""

from loop_eval.infrastructure.orchestrator.orchestrator import Orchestrator

if __name__ == "__main__":
    Orchestrator().run()
