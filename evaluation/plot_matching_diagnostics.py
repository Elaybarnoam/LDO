"""Render optional scientific figures from completed matching diagnostic evidence."""

import argparse
import json
from pathlib import Path

import numpy as np

from ldo.artifacts import sha256, write_json


def _draw(axis, pairs, query_points, historical_points, offset, color):
    for q, h in pairs:
        a, b = query_points[q], historical_points[h]
        axis.plot(
            [a[0], b[0] + offset],
            [a[1], b[1]],
            color=color,
            linewidth=1.1,
            alpha=0.85,
            marker="o",
            markersize=3,
        )


def _select(values, budget):
    return (
        values
        if len(values) <= budget
        else values[np.linspace(0, len(values) - 1, budget, dtype=int)]
    )


def render(results_path: Path, output: Path) -> list[dict]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt

    result = json.loads(results_path.read_text())
    output.mkdir(parents=True, exist_ok=True)
    figures = []
    for event in result["events"]:
        if not event["pairs"]:
            continue
        row = max(event["pairs"], key=lambda r: r["maximum_supported_one_to_one_matches"])
        evidence_path = Path(row["evidence"])
        if sha256(evidence_path) != row["evidence_sha256"]:
            raise ValueError("Diagnostic correspondence evidence changed")
        with np.load(evidence_path, allow_pickle=False) as data:
            qp, hp, ids = data["query_points"], data["historical_points"], data["indices"]
            verdicts, oracle = data["verdicts"], data["oracle_assignment"]
        qi, hi = mpimg.imread(row["query_image"]), mpimg.imread(row["historical_image"])
        if qi.ndim == 2:
            qi = np.repeat(qi[:, :, None], 3, axis=2)
        if hi.ndim == 2:
            hi = np.repeat(hi[:, :, None], 3, axis=2)
        gap, width, height = 24, qi.shape[1], qi.shape[0]
        canvas = np.concatenate(
            [qi, np.ones((height, gap, 3), dtype=qi.dtype) * qi.max(), hi], axis=1
        )
        figure, axes = plt.subplots(2, 1, figsize=(14, 14), facecolor="#f7f7f5")
        figure.suptitle(
            f"{event['trajectory']} event at {event['start_ns'] / 1e9:.2f}s | Pair {row['q'] / 1e9:.2f}s / {row['h'] / 1e9:.2f}s",
            fontsize=17,
            fontweight="bold",
            y=0.985,
        )
        for axis in axes:
            axis.imshow(canvas)
            axis.set_xlim(-1, canvas.shape[1])
            axis.set_ylim(height, -1)
            axis.axis("off")
        count = row["reported"]
        axes[0].set_title(
            f"LDO output: {count['supported']} correct / {count['contradicted']} incorrect / {count['untestable']} unknown\n"
            "Green = supported; red = contradicted; grey = unknown. At most 30 reported lines shown.",
            fontsize=12,
            pad=14,
        )
        colors = {"supported": "#16a34a", "contradicted": "#dc2626", "untestable": "#9ca3af"}

        for kind, budget in (("supported", 10), ("contradicted", 16), ("untestable", 4)):
            _draw(
                axes[0],
                ids[_select(np.flatnonzero(verdicts == kind), budget)],
                qp,
                hp,
                width + gap,
                colors[kind],
            )
        axes[1].set_title(
            f"Reference-only diagnostic: {len(oracle)} supported one-to-one matches exist in the same keypoints\n"
            "Blue lines = oracle examples, never model inputs. At most 20 lines shown.",
            fontsize=12,
            pad=14,
        )
        axes[1].scatter(qp[:, 0], qp[:, 1], s=2, c="#cbd5e1", alpha=0.5)
        axes[1].scatter(hp[:, 0] + width + gap, hp[:, 1], s=2, c="#cbd5e1", alpha=0.5)
        _draw(axes[1], _select(oracle, 20), qp, hp, width + gap, "#2563eb")
        figure.text(
            0.5,
            0.015,
            "Fixed depth / pose / XYZ policy. Geometric capacity does not guarantee unique visual identity or SLAM acceptance.",
            ha="center",
            fontsize=11,
        )
        figure.subplots_adjust(top=0.91, bottom=0.04, hspace=0.22, left=0.025, right=0.975)
        destination = output / f"{event['trajectory']}_{event['event_id']}.png"
        figure.savefig(destination, dpi=110, facecolor=figure.get_facecolor())
        plt.close(figure)
        figures.append(
            {
                "event_id": event["event_id"],
                "trajectory": event["trajectory"],
                "query": row["q"],
                "historical": row["h"],
                "path": str(destination),
                "sha256": sha256(destination),
                "source_evidence_sha256": sha256(evidence_path),
                "query_image_sha256": sha256(Path(row["query_image"])),
                "historical_image_sha256": sha256(Path(row["historical_image"])),
            }
        )
    write_json(
        output / "manifest.json",
        {
            "results_sha256": sha256(results_path),
            "renderer_sha256": sha256(Path(__file__)),
            "matplotlib_version": matplotlib.__version__,
            "figures": figures,
        },
    )
    return figures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(render(args.results, args.output), indent=2))


if __name__ == "__main__":
    main()
