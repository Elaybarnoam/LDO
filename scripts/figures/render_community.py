"""Render a saved-evidence walkthrough and social card from immutable figures."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from PIL import __version__ as pillow_version

from loop_eval.paths import project_root

ROOT = project_root()
BG = "#f7f7f5"
INK = "#202423"
MUTED = "#4d5a56"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size):
    # Matplotlib supplies a portable font in the visualization environment.
    from matplotlib import get_data_path

    return ImageFont.truetype(str(Path(get_data_path()) / "fonts/ttf/DejaVuSans.ttf"), size)


def slide(title, subtitle, source, explanation):
    canvas = Image.new("RGB", (1200, 900), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((32, 20), title, font=font(29), fill=INK)
    draw.text((32, 65), subtitle, font=font(18), fill=MUTED)
    with Image.open(source) as image:
        figure = ImageOps.contain(image.convert("RGB"), (1140, 705))
    canvas.paste(figure, ((1200 - figure.width) // 2, 105))
    draw.text((32, 830), explanation, font=font(19), fill=INK)
    draw.text(
        (32, 866),
        "Saved TartanAir simulation evidence | reference-only blue lines are not model outputs",
        font=font(16),
        fill=MUTED,
    )
    return canvas


def render(output):
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "docs/archive/ldo-matching-diagnostics-figures.json"
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = {str(manifest_path.relative_to(ROOT)): digest(manifest_path)}
    selected = source_manifest["figures"][:2]
    figures = []
    for row in selected:
        path = ROOT / "docs/archive/figures/matching-diagnostics" / Path(row["path"]).name
        if digest(path) != row["sha256"]:
            raise ValueError(f"Archived figure hash mismatch: {path}")
        sources[str(path.relative_to(ROOT))] = digest(path)
        figures.append(path)
    frames = [
        slide(
            "LDO | Visual proposals, inspectable evidence",
            "1 / 4  Two diagnosed revisit pairs; selected failures, not aggregate performance",
            figures[0],
            "Query 13 s / history 8 s: 0 supported, 1 contradicted, 0 unknown.",
        ),
        slide(
            "A retrieved revisit can still lack useful assignments",
            "2 / 4  Independent assessment; no operational pose decision is shown",
            figures[0],
            "Existing-feature capacity is only 2. The blue oracle cannot rescue runtime output.",
        ),
        slide(
            "Separate model output from reference-only possibilities",
            "3 / 4  Query 16 s / history 8.5 s; timestamps are rounded for display",
            figures[1],
            "7 supported, 29 contradicted, 2 unknown; existing-feature capacity is 20.",
        ),
        slide(
            "Reproduce the presentation; investigate the failure",
            "4 / 4  Full timestamps, counts and source hashes are linked in the example guide",
            figures[1],
            "CPU-only rendering from saved evidence. No new inference or performance claim.",
        ),
    ]
    frames[0].save(
        output / "evidence-walkthrough.gif",
        save_all=True,
        append_images=frames[1:],
        duration=6000,
        loop=0,
        optimize=False,
        disposal=2,
    )
    frames[0].save(output / "evidence-poster.png")
    card = Image.new("RGB", (1280, 640), BG)
    draw = ImageDraw.Draw(card)
    draw.text((48, 35), "LDO", font=font(60), fill=INK)
    draw.text((48, 115), "Causal visual loop detection", font=font(31), fill=INK)
    draw.text(
        (48, 165), "Visual proposals. Independent geometric evidence.", font=font(23), fill=MUTED
    )
    # Keep the original figure intact, including its oracle disclaimer.
    with Image.open(figures[1]) as image:
        thumb = ImageOps.contain(image.convert("RGB"), (360, 360))
    card.paste(thumb, (850, 230))
    for y, line in enumerate(
        (
            "MegaLoc + SuperPoint / LightGlue",
            "Causal replay and saved assignments",
            "Supported / contradicted / unknown",
            "v0.1.0 | Research preview | Elay Barnoam",
            "github.com/Elaybarnoam/LDO",
            "Illustration: saved TartanAir simulation evidence",
        )
    ):
        draw.text((48, 270 + 47 * y), line, font=font(21 if y < 5 else 17), fill=INK)
    card.save(output / "social-preview.png", optimize=True)
    report = {
        "kind": "saved_evidence_presentation",
        "research_result": False,
        "duration_seconds": 24,
        "scope": "First two archived diagnosed failure figures; TartanAir OldTownFall simulation",
        "limitations": "No trajectory, new inference, runtime acceptance/rejection or real-world validation",
        "generator": "scripts/figures/render_community.py",
        "generator_sha256": digest(Path(__file__)),
        "pillow_version": pillow_version,
        "sources": sources,
        "selected_pairs": [
            {key: row[key] for key in ("event_id", "trajectory", "query", "historical")}
            for row in selected
        ],
        "outputs": {
            path.name: digest(path)
            for path in sorted(output.iterdir())
            if path.name
            in {"evidence-walkthrough.gif", "evidence-poster.png", "social-preview.png"}
        },
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered saved-evidence assets to {output}; no inference performed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/community")
    render(parser.parse_args().output)
