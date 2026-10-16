"""Render editable vector architecture and coordinate-convention diagrams."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from loop_eval.paths import project_root


def box(ax, x, y, width, height, title, detail, color="#e9f0f7"):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.015,rounding_size=.025",
            facecolor=color,
            edgecolor="#516477",
            linewidth=1.2,
        )
    )
    ax.text(
        x + width / 2,
        y + height * 0.68,
        title,
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        color="#172b3e",
    )
    ax.text(
        x + width / 2,
        y + height * 0.3,
        detail,
        ha="center",
        va="center",
        fontsize=10,
        color="#30465c",
    )


def arrow(ax, start, end, color="#344d65", dashed=False):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=14,
            color=color,
            linewidth=1.5,
            linestyle="--" if dashed else "-",
        )
    )


def render(output):
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.hashsalt": "ldo-diagrams-v1"})
    output.mkdir(parents=True, exist_ok=True)
    figures = []

    def save(fig, name):
        for extension in ("svg", "png"):
            path = output / f"{name}.{extension}"
            fig.savefig(
                path,
                dpi=170,
                bbox_inches="tight",
                facecolor="white",
                metadata={"Date": None} if extension == "svg" else None,
            )
            figures.append(
                {
                    "file": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "kind": "implementation_schematic",
                    "research_measurement": False,
                }
            )
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6.2))
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    ax.text(
        0.02,
        0.96,
        "LDO · causal visual proposals and independent assessment",
        fontsize=17,
        fontweight="bold",
        color="#172b3e",
    )
    ax.text(0.02, 0.88, "RUNTIME OBSERVATIONS", fontsize=10, fontweight="bold", color="#225f92")
    boxes = [
        (0.02, "Camera frames", "Chronological replay"),
        (0.27, "Global retrieval", "MegaLoc · exact cosine"),
        (0.52, "Local matching", "SuperPoint + LightGlue"),
        (0.77, "Saved proposals", "IDs · pixels · scores"),
    ]
    for x, title, detail in boxes:
        box(ax, x, 0.67, 0.20, 0.14, title, detail)
    for i in range(3):
        arrow(ax, (boxes[i][0] + 0.215, 0.74), (boxes[i + 1][0] - 0.018, 0.74))
    box(
        ax,
        0.52,
        0.43,
        0.45,
        0.13,
        "Optional operational verification",
        "Image-only stereo → PnP/RANSAC → acceptance gates",
        "#edf4ec",
    )
    arrow(ax, (0.87, 0.65), (0.87, 0.58))
    ax.text(
        0.02,
        0.49,
        "No reference labels or poses\nenter retrieval, matching, or verification.",
        fontsize=12,
        va="center",
        color="#30465c",
    )
    ax.axhline(0.36, color="#9ba8b5", linestyle="--", linewidth=1)
    ax.text(
        0.02, 0.30, "OFFLINE REFERENCE ASSESSMENT", fontsize=10, fontweight="bold", color="#8c5730"
    )
    box(
        ax,
        0.02,
        0.08,
        0.25,
        0.14,
        "Independent references",
        "Depth · poses\nsemantic masks",
        "#fbf1e5",
    )
    box(
        ax,
        0.37,
        0.08,
        0.28,
        0.14,
        "Independent evaluators",
        "Feature · pair · event · pose",
        "#fbf1e5",
    )
    box(
        ax,
        0.75,
        0.08,
        0.22,
        0.14,
        "Evidence and metrics",
        "Supported · contradicted\nunknown retained",
        "#fbf1e5",
    )
    arrow(ax, (0.29, 0.15), (0.35, 0.15), color="#8c5730")
    arrow(ax, (0.67, 0.15), (0.73, 0.15), color="#8c5730")
    arrow(ax, (0.65, 0.42), (0.55, 0.24), dashed=True)
    ax.text(0.38, 0.39, "Optional pose output", fontsize=9, color="#30465c")
    # Direct correspondence assessment uses all saved proposals, independently
    # of the optional verifier's acceptance decision.
    ax.plot(
        [0.975, 0.995, 0.995, 0.64],
        [0.74, 0.74, 0.255, 0.255],
        linestyle="--",
        color="#344d65",
        linewidth=1.2,
    )
    arrow(ax, (0.64, 0.255), (0.64, 0.235), dashed=True)
    ax.text(0.70, 0.275, "All saved assignments", fontsize=9, color="#30465c")
    save(fig, "system-overview")

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.set(xlim=(-0.4, 6), ylim=(-0.5, 3.3))
    ax.axis("off")
    ax.text(
        -0.2,
        3.0,
        "Coordinate convention: query points map into history",
        fontsize=15,
        fontweight="bold",
        color="#172b3e",
    )
    for origin, name, color in (
        ((0.5, 0.1), "Query camera q", "#225f92"),
        ((4.6, 0.1), "Historical camera h", "#b76b2a"),
    ):
        x, y = origin
        arrow(ax, (x, y), (x + 0.7, y), color=color)
        arrow(ax, (x, y), (x, y + 0.7), color=color)
        ax.plot(x, y, "o", color=color)
        ax.text(x, y - 0.3, name, ha="center", fontsize=11, color=color)
    ax.plot(2.5, 2.15, "o", color="#246e54", markersize=9)
    ax.text(2.5, 2.4, "Same static world point", ha="center", fontsize=11, color="#246e54")
    ax.plot([0.5, 2.5], [0.1, 2.15], color="#225f92", linestyle="--")
    ax.plot([4.6, 2.5], [0.1, 2.15], color="#b76b2a", linestyle="--")
    ax.text(1.0, 1.25, r"$X_q = z_q K_q^{-1}\tilde{u}$", fontsize=12, color="#225f92")
    ax.text(3.5, 1.25, r"$X_h = z_h K_h^{-1}\tilde{v}$", fontsize=12, color="#b76b2a")
    arrow(ax, (1.35, 0.25), (3.75, 0.25))
    ax.text(2.55, 0.5, r"$X_h = R_{hq}X_q+t_{hq}$", ha="center", fontsize=14)
    ax.text(
        2.55,
        -0.35,
        "Schematic · undistorted pinhole rays · depth and translation in metres",
        ha="center",
        fontsize=10,
        color="#516477",
    )
    save(fig, "coordinate-conventions")
    manifest = {
        "schema_version": 1,
        "generator": "scripts/figures/render_diagrams.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "figures": figures,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=project_root() / "docs/assets/diagrams")
    render(parser.parse_args().output)


if __name__ == "__main__":
    main()
