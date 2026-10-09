"""First operating point: retrieval ordering with complete matching evidence."""

from ..contracts import Candidate, KeyframeInput


class RetrievalOrderPolicy:
    def apply(
        self, query: KeyframeInput, candidates: tuple[Candidate, ...]
    ) -> tuple[Candidate, ...]:
        return candidates

    def reset(self) -> None:
        pass
