"""Entry point for evaluation."""

from loop_eval.infrastructure.orchestrator.orchestrator import Orchestrator

if __name__ == "__main__":
    Orchestrator().run()
