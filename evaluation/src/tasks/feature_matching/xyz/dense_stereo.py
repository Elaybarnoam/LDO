"""Evaluation-only legacy cache bridge over shared observation stereo."""

import hashlib
import json
import os
from pathlib import Path

from stereo_observations.dense import DenseStereo as ObservationStereo
from stereo_observations.dense import correspondences as correspondences
from stereo_observations.dense import sample as sample


class DenseStereo(ObservationStereo):
    def __init__(self, policy, k0, d0, k1, d1, size, relative, output):
        super().__init__(
            policy,
            k0,
            d0,
            k1,
            d1,
            size,
            relative,
            output,
            worker_path=Path(__file__).with_name("stereo_worker.py"),
        )
        worker = self.worker
        source = os.environ.get("LDO_STEREO_CACHE_SOURCE")
        if source:
            source = Path(source)
            provenance = json.loads(
                (source.parent / "candidate_checks/provenance.json").read_text()
            )
            old_policy = provenance["policy"]

            def stereo_policy(value):
                return {
                    k: v
                    for k, v in value.items()
                    if k not in {"version", "minimum_image_coverage"}
                    and not k.startswith("ransac_")
                }

            if stereo_policy(old_policy) != stereo_policy(policy):
                raise ValueError("Stereo cache source policy differs")
            hashes = provenance["input_and_code_sha256"]
            for artifact in (
                worker,
                Path(policy["stereo_model_checkpoint"]),
                Path(policy["stereo_model_source"]) / "ldo-install.json",
            ):
                if hashes.get(str(artifact)) != hashlib.sha256(artifact.read_bytes()).hexdigest():
                    raise ValueError(f"Stereo cache source artifact differs: {artifact}")
            self.cache_source = source
            self.source_signature = self._signature_for_policy(old_policy)
