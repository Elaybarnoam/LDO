"""Observation-only verification of candidate loop connections."""

from .contracts import VerificationInput, VerificationResult
from .verifier import LoopVerifier

__all__ = ["LoopVerifier", "VerificationInput", "VerificationResult"]
