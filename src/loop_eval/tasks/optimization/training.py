"""Adapt only LightGlue's final assignment head using independent training geometry.

Reference geometry is used for supervision and scoring, never model inference.
The pretrained attention stack and SuperPoint are frozen throughout.
"""

import argparse
import json
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
import yaml
from scipy.spatial.distance import cdist

from ldo.artifacts import identity, sha256, verify_install
from ldo.configuration import load_config
from ldo.contracts import LocalFeatures
from ldo.matching.lightglue import LightGlueMatcher
from ldo.matching.superpoint import SuperPointExtractor
from ldo.policies.confidence import CandidateConfidencePolicy
from loop_eval.tasks.reference_geometry.dataset import frames, prepare_sequence
from loop_eval.tasks.reference_geometry.geometry import (
    backproject,
    check_features,
    decode_depth,
    project,
    sample_depth,
)

from .develop import DEFAULT_REPORT, OUT, ROOT, VALIDATE, save
from .observations import change, load, measure

WORK = Path("/opt/loop-detector/ldo-optimization")


class FeatureCache:
    """Content-addressed immutable SuperPoint observations, including descriptors."""

    def __init__(self, config):
        installation = verify_install(config.model_root)
        torch.hub.set_dir(str(config.model_root / "torch"))
        self.identity = identity(
            {
                "installation": installation,
                "maximum_keypoints": config.maximum_keypoints,
                "grayscale": True,
                "resize": None,
            }
        )
        self.extractor = SuperPointExtractor(
            torch.device(config.device), config.maximum_keypoints, self.identity
        )
        self.root = WORK / "features" / self.identity
        self.root.mkdir(parents=True, exist_ok=True)
        self.get = lru_cache(maxsize=512)(self._get)

    def _get(self, image, expected_sha):
        image = Path(image)
        if sha256(image) != expected_sha:
            raise ValueError("Reference image changed before feature extraction")
        path = self.root / (expected_sha + ".npz")
        digest = path.with_suffix(".sha256")
        if not path.exists():
            value = self.extractor.extract(image)
            np.savez_compressed(
                path,
                points=value.points,
                descriptors=value.descriptors,
                scores=value.scores,
                image_size=value.image_size,
            )
            digest.write_text(sha256(path))
        if not digest.exists() or sha256(path) != digest.read_text():
            raise ValueError("Cached training observation changed")
        with np.load(path, allow_pickle=False) as data:
            return LocalFeatures(
                data["points"].copy(),
                data["descriptors"].copy(),
                data["scores"].copy(),
                tuple(data["image_size"]),
                "superpoint",
                self.identity,
            )

    def close(self):
        self.get.cache_clear()
        self.extractor.close()


def supervision(q, h, qdepth, hdepth, relative, policy):
    """Mutual geometric assignment with a 3/5px ambiguity margin.

    -1 is demonstrably unmatched; -2 is unknown and never contributes to loss.
    Positive labels are computed over ALL feature combinations.
    """
    qz, qvalid = sample_depth(qdepth, q, policy)
    hz, hvalid = sample_depth(hdepth, h, policy)
    qxyz, hxyz = backproject(q, qz), backproject(h, hz)
    mapped = qxyz @ relative[:3, :3].T + relative[:3, 3]
    reverse = np.linalg.inv(relative)
    invmapped = hxyz @ reverse[:3, :3].T + reverse[:3, 3]
    predicted_h, forward_h = project(mapped)
    predicted_q, forward_q = project(invmapped)
    # Spatial association is supervised by BOTH directions and physical XYZ.
    dh = cdist(np.nan_to_num(predicted_h, nan=1e9), h)
    dq = cdist(q, np.nan_to_num(predicted_q, nan=1e9))
    distance = np.maximum(dh, dq)
    physical = cdist(np.nan_to_num(mapped, nan=1e9), np.nan_to_num(hxyz, nan=1e9))
    tolerance = np.maximum(
        policy["feature_xyz_tolerance_m"],
        policy["feature_xyz_relative_tolerance"] * np.maximum(qz[:, None], hz),
    )
    eligible = qvalid[:, None] & hvalid[None, :] & forward_h[:, None] & forward_q[None, :]
    positive = eligible & (distance <= 3.0) & (physical <= tolerance)
    cost = np.where(positive, distance, np.inf)
    best_h, best_q = cost.argmin(axis=1), cost.argmin(axis=0)
    qi = np.arange(len(q))
    qi = qi[(best_q[best_h] == qi) & np.isfinite(cost[qi, best_h])]
    hi = best_h[qi]

    def unmatched(pixels, valid, transformed, predicted, forward, target_depth, neighbours):
        z, target_valid = sample_depth(target_depth, predicted, policy)
        inside = forward & (predicted[:, 0] >= 0) & (predicted[:, 0] <= 639)
        inside &= (predicted[:, 1] >= 0) & (predicted[:, 1] <= 639)
        visible = target_valid & (np.abs(transformed[:, 2] - z) <= np.maximum(0.03, 0.01 * z))
        # Projection near a depth edge stays unknown, rather than becoming a negative.
        known = valid & (~inside | target_valid)
        no_partner = neighbours.min(axis=1) > 5.0
        labels = np.full(len(pixels), -2, np.int64)
        labels[known & (~inside | ~visible | no_partner)] = -1
        return labels

    gtq = unmatched(q, qvalid, mapped, predicted_h, forward_h, hdepth, dh)
    gth = unmatched(h, hvalid, invmapped, predicted_q, forward_q, qdepth, dq.T)
    gtq[qi], gth[hi] = hi, qi
    return gtq, gth


def assignment_loss(log_assignment, gtq, gth):
    """Balanced positive/dustbin NLL, excluding all unknown observations."""
    matrix = log_assignment[0]
    qi = torch.where(gtq >= 0)[0]
    positive = -matrix[qi, gtq[qi]].mean() if len(qi) else matrix.sum() * 0
    negative = torch.cat((matrix[:-1, -1][gtq == -1], matrix[-1, :-1][gth == -1]))
    dustbin = -negative.mean() if len(negative) else matrix.sum() * 0
    return 0.5 * positive + 0.5 * dustbin


def train_examples(cache, protocol):
    settings = {
        "root": "/opt/loop-detector/datasets/tartanair_optimization/train",
        "environment": "RetroOffice",
        "difficulty": "Data_easy",
        "reference_only": True,
    }
    examples, provenance = [], []
    replay = WORK / "training_replay"
    for tid in [f"P{i:03d}" for i in range(6)]:
        target = replay / tid
        if not (target / "frames.json").exists():
            info = prepare_sequence(settings, tid, target, protocol["frame_stride"])
            save(target / "source.json", info)
        items = frames(target)
        selected = []
        # Adjacent views teach geometric assignments; widely separated views teach
        # unmatched/difficult associations. Selection is independent of model scores.
        for offset in (1, 2, 4, 8, 12, max(1, len(items) // 2)):
            indices = np.linspace(offset, len(items) - 1, 4, dtype=int)
            selected.extend((int(i), int(i - offset)) for i in indices if i >= offset)
        for qi, hi in dict.fromkeys(selected):
            q, h = items[qi], items[hi]
            qf = cache.get(q["image"], q["image_sha256"])
            hf = cache.get(h["image"], h["image_sha256"])

            # Highest detector scores, with original coordinates and descriptors.
            def subset(features):
                ids = np.argsort(-features.scores, kind="stable")[:256]
                return replace(
                    features,
                    points=features.points[ids],
                    descriptors=features.descriptors[ids],
                    scores=features.scores[ids],
                )

            qf, hf = subset(qf), subset(hf)
            gtq, gth = supervision(
                qf.points,
                hf.points,
                decode_depth(q["depth"]),
                decode_depth(h["depth"]),
                np.linalg.inv(h["pose"]) @ q["pose"],
                protocol,
            )
            counts = {
                "positive": int(np.sum(gtq >= 0)),
                "negative": int(np.sum(gtq == -1) + np.sum(gth == -1)),
                "unknown": int(np.sum(gtq == -2) + np.sum(gth == -2)),
            }
            if not counts["positive"] and not counts["negative"]:
                continue
            examples.append((qf, hf, gtq, gth))
            provenance.append(
                {
                    "trajectory": tid,
                    "q": q["timestamp_ns"],
                    "h": h["timestamp_ns"],
                    "query_image_sha256": q["image_sha256"],
                    "historical_image_sha256": h["image_sha256"],
                    "query_depth_sha256": q["depth_sha256"],
                    "historical_depth_sha256": h["depth_sha256"],
                    **counts,
                }
            )
        print(f"Training observations {tid}: {len(examples)} supervised pairs total", flush=True)
    save(OUT / "training_examples.json", provenance)
    return examples


def rescore(matcher, cache, pairs, contexts, protocol, artifact):
    """Fresh assignments on frozen raw retrieval candidates, independently scored."""
    results, artifacts = [], []
    artifact.mkdir(parents=True, exist_ok=True)
    for trajectory, context in contexts.items():
        items = {r["timestamp_ns"]: r for r in frames(Path(context["info"]["root"]))}
        depth_cache = {}
        for row in (r for r in pairs if r.trajectory == trajectory):
            q, h = items[row.q], items[row.h]
            qf, hf = (
                cache.get(q["image"], q["image_sha256"]),
                cache.get(h["image"], h["image_sha256"]),
            )
            for stamp, features in ((row.q, qf), (row.h, hf)):
                original = Path(context["features_root"]) / f"{stamp}_cam0.npz"
                with np.load(original, allow_pickle=False) as saved:
                    if not np.array_equal(saved["points"], features.points):
                        raise ValueError("Fresh SuperPoint observations differ from the baseline")
            assignments = matcher.match(qf, hf)
            ids = assignments.indices
            for stamp, item in ((row.q, q), (row.h, h)):
                if stamp not in depth_cache:
                    if sha256(Path(item["depth"])) != item["depth_sha256"]:
                        raise ValueError("Reference depth changed")
                    depth_cache[stamp] = decode_depth(item["depth"])
            checks = check_features(
                qf.points[ids[:, 0]],
                hf.points[ids[:, 1]],
                depth_cache[row.q],
                depth_cache[row.h],
                np.linalg.inv(h["pose"]) @ q["pose"],
                protocol,
            )
            name = f"{trajectory}_{row.q}_{row.h}.npz"
            path = artifact / name
            np.savez_compressed(
                path,
                indices=ids,
                scores=assignments.scores,
                verdicts=checks["verdicts"],
                xyz_error_m=checks["xyz_error_m"],
                pixel_error=checks["pixel_error"],
            )
            artifacts.append({"path": name, "sha256": sha256(path)})
            results.append(
                replace(
                    row,
                    scores=assignments.scores,
                    verdicts=checks["verdicts"],
                    historical_count=len(hf.points),
                )
            )
        print(f"Scored matcher {artifact.name}: {trajectory}", flush=True)
    save(artifact / "manifest.json", {"assignments": artifacts, "reference_gates": protocol})
    return results


def main():
    torch.manual_seed(0)
    np.random.seed(0)
    torch.set_num_threads(1)
    WORK.mkdir(parents=True, exist_ok=True)
    config = load_config(ROOT / "configs/evaluation/reference_geometry/ldo.yaml")
    protocol = yaml.safe_load(
        (ROOT / "configs/evaluation/reference_geometry/config.yaml").read_text()
    )["protocol"]
    cache = FeatureCache(config)
    examples = train_examples(cache, protocol)
    if not examples:
        raise RuntimeError("No training supervision")
    matcher = LightGlueMatcher(torch.device(config.device), "superpoint", 0.1, full_depth=True)
    model = matcher.model
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    for parameter in model.log_assignment[-1].parameters():
        parameter.requires_grad_(True)
    optimizer = torch.optim.AdamW(model.log_assignment[-1].parameters(), lr=1e-4)
    captured = {}
    hook = model.log_assignment[-1].register_forward_hook(
        lambda module, inputs, output: captured.update(log_assignment=output[0])
    )
    pairs, contexts = load(DEFAULT_REPORT)
    pairs = [r for r in pairs if r.trajectory in VALIDATE]
    contexts = {k: v for k, v in contexts.items() if k in VALIDATE}
    first = json.loads((OUT / "step1.json").read_text())
    threshold = first["threshold"]
    policy = CandidateConfidencePolicy.from_file(ROOT / "configs/models/candidate-confidence.json")
    base = measure(pairs, contexts, threshold, policy)
    checkpoints, losses, gradient_norms = [], [], []
    generator = np.random.default_rng(0)
    for update in range(301):
        if update in (0, 50, 100, 200, 300):
            model.eval()
            checkpoint = WORK / f"assignment_head_{update:03d}.pt"
            torch.save(model.state_dict(), checkpoint)
            scored = rescore(
                matcher, cache, pairs, contexts, protocol, OUT / f"checkpoint_{update:03d}"
            )
            metrics = measure(scored, contexts, threshold, policy)
            checkpoints.append(
                {
                    "update": update,
                    "checkpoint": str(checkpoint),
                    "checkpoint_sha256": sha256(checkpoint),
                    "metrics": metrics,
                    "change_from_step2": change(base, metrics),
                }
            )
            print(f"Checkpoint {update}: {json.dumps(metrics['features'])}", flush=True)
        if update == 300:
            break
        model.train()
        qf, hf, gtq, gth = examples[int(generator.integers(len(examples)))]
        optimizer.zero_grad(set_to_none=True)
        # Calling the torch model directly preserves the differentiable assignment.
        model({"image0": matcher._tensors(qf), "image1": matcher._tensors(hf)})
        la = captured.pop("log_assignment")
        loss = assignment_loss(
            la, torch.tensor(gtq, device=config.device), torch.tensor(gth, device=config.device)
        )
        if not torch.isfinite(loss):
            raise RuntimeError("Non-finite training loss")
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(model.log_assignment[-1].parameters(), 10.0)
        if not torch.isfinite(norm):
            raise RuntimeError("Non-finite training gradient")
        optimizer.step()
        losses.append(float(loss.detach()))
        gradient_norms.append(float(norm))
    hook.remove()
    # Keep the previous deployed variant when no trained candidate improves it.
    feasible = [
        c for c in checkpoints[1:] if c["change_from_step2"]["supported_match_retention"] >= 0.9
    ]
    selected = (
        min(
            feasible,
            key=lambda c: (
                c["metrics"]["features"]["contradicted"],
                -c["metrics"]["features"]["supported"],
            ),
        )
        if feasible
        else None
    )
    control = checkpoints[0]["metrics"]
    improved = bool(
        selected
        and selected["metrics"]["features"]["contradicted"] < base["features"]["contradicted"]
        and selected["metrics"]["features"]["contradicted"] < control["features"]["contradicted"]
        and selected["metrics"]["features"]["supported"] >= 0.9 * control["features"]["supported"]
    )
    if selected:
        # Verify serialized parameters produce exactly the same assignments.
        reload = LightGlueMatcher(
            torch.device(config.device),
            "superpoint",
            0.1,
            checkpoint=Path(selected["checkpoint"]),
            checkpoint_sha256=selected["checkpoint_sha256"],
            full_depth=True,
        )
        model.load_state_dict(torch.load(selected["checkpoint"], weights_only=True))
        model.eval()
        qf, hf, _, _ = examples[0]
        a, b = matcher.match(qf, hf), reload.match(qf, hf)
        if not np.array_equal(a.indices, b.indices) or not np.array_equal(a.scores, b.scores):
            raise RuntimeError("Checkpoint reload differs")
        reload.close()
    result = {
        "step": 3,
        "training_environment": "RetroOffice",
        "selection_environment": "ArchVizTinyHouseDay",
        "selected": selected,
        "promoted": improved,
        "previous": base,
        "checkpoints": checkpoints,
        "losses": losses,
        "gradient_norms": gradient_norms,
        "trainable_parameters": [n for n, p in model.named_parameters() if p.requires_grad],
        "trainable_parameter_count": sum(p.numel() for p in model.parameters() if p.requires_grad),
        "source_sha256": sha256(Path(__file__)),
        "training_examples_sha256": sha256(OUT / "training_examples.json"),
        "checkpoint_reload_exact": True if selected else None,
        "learning_change_vs_equal_compute": change(control, selected["metrics"])
        if selected
        else None,
    }
    save(OUT / "step3.json", result)
    deployed = yaml.safe_load((ROOT / "configs/models/optimized-policy.yaml").read_text())
    if improved:
        deployed.update(
            variant="LDO-MegaLoc-LightGlue-AdaptedAssignment",
            matcher_full_depth=True,
            matcher_checkpoint=selected["checkpoint"],
            matcher_checkpoint_sha256=selected["checkpoint_sha256"],
        )
    (ROOT / "configs/models/optimized.yaml").write_text(yaml.safe_dump(deployed, sort_keys=False))
    matcher.close()
    cache.close()
    print("STEP3", "promoted" if improved else "previous variant retained", flush=True)


def finalize_saved():
    """Reapply the frozen promotion rule to completed, hashed checkpoint evidence."""
    path = OUT / "step3.json"
    result = json.loads(path.read_text())
    selected = result["selected"]
    control = result["checkpoints"][0]["metrics"]
    if selected and sha256(Path(selected["checkpoint"])) != selected["checkpoint_sha256"]:
        raise ValueError("Selected checkpoint changed")
    result["learning_change_vs_equal_compute"] = (
        change(control, selected["metrics"]) if selected else None
    )
    result["promoted"] = bool(
        selected
        and selected["metrics"]["features"]["contradicted"]
        < result["previous"]["features"]["contradicted"]
        and selected["metrics"]["features"]["contradicted"] < control["features"]["contradicted"]
        and selected["metrics"]["features"]["supported"] >= 0.9 * control["features"]["supported"]
    )
    result["selection_rule"] = (
        "Strictly fewer contradicted matches than predecessor AND equal-compute control, with >=90% supported retention. Test data unused."
    )
    save(path, result)
    deployed = yaml.safe_load((ROOT / "configs/models/optimized-policy.yaml").read_text())
    if result["promoted"]:
        deployed.update(
            variant="LDO-MegaLoc-LightGlue-AdaptedAssignment",
            matcher_full_depth=True,
            matcher_checkpoint=selected["checkpoint"],
            matcher_checkpoint_sha256=selected["checkpoint_sha256"],
        )
    (ROOT / "configs/models/optimized.yaml").write_text(yaml.safe_dump(deployed, sort_keys=False))
    print(
        "STEP3",
        "promoted"
        if result["promoted"]
        else "not promoted: no improvement over equal-compute control",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finalize-saved", action="store_true")
    args = parser.parse_args()
    if args.finalize_saved:
        finalize_saved()
    else:
        main()
