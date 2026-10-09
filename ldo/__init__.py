"""Replaceable visual retrieval and correspondence architecture."""

from .contracts import KeyframeInput, LoopProposalBatch
from .detector import Detector

__all__ = ["Detector", "KeyframeInput", "LoopProposalBatch"]
