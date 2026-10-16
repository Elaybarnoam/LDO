"""Derive compact public tables and figures from immutable historical evidence.

Run from an installed checkout. This performs no model inference or reference
rescore; it reproduces presentation of the archived measurements only.
"""

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path

from loop_eval.paths import project_root

ROOT = project_root()
STUDIES = [
    (
        "tartanair-pilot-v1",
        "TartanAir pilot",
        "tartanair-reference-geometry-plan.md",
        "tartanair-reference-geometry-results.md",
        "tartanair-direct-report.md",
        "pilot",
        "reference-v1",
    ),
    (
        "sequential-optimization",
        "Sequential optimization",
        "ldo-sequential-optimization-plan.md",
        "ldo-sequential-optimization-results.md",
        "ldo-sequential-optimization-results.json",
        "held-out at execution; now inspected",
        "reference-v1",
    ),
    (
        "factory-desert-frozen",
        "Frozen Factory/Desert comparison",
        "ldo-unseen-tartanair-plan.md",
        "ldo-unseen-tartanair-results.md",
        "ldo-unseen-tartanair-results.json",
        "test at execution; later matching development",
        "reference-v1",
    ),
    (
        "reference-depth-v2",
        "Reference depth v2 rescore",
        "reference-depth-v2-plan.md",
        "reference-depth-v2-results.md",
        "reference-depth-v2-report.json",
        "rescore of inspected evidence",
        "feature-depth-v2; original pair policy",
    ),
    (
        "matching-oldtown",
        "Matching selection and OldTownFall test",
        "ldo-matching-optimization-plan.md",
        "ldo-matching-optimization-results.md",
        "ldo-matching-optimization-results.json",
        "Factory/Desert development; OldTownFall test at execution, now inspected",
        "feature-depth-v2; original pair policy",
    ),
    (
        "matching-diagnostics",
        "Matching failure diagnosis",
        "ldo-matching-diagnostics-plan.md",
        "ldo-matching-diagnostics-results.md",
        "ldo-matching-diagnostics-results.json",
        "reference-assisted analysis of inspected evidence",
        "feature-depth-v2",
    ),
    (
        "descriptor-analysis",
        "Descriptor and assignment audit",
        "ldo-descriptor-analysis-plan.md",
        "ldo-descriptor-analysis-results.md",
        "ldo-descriptor-analysis-results.json",
        "positive development pairs; reference-assisted diagnosis",
        "feature-depth-v2",
    ),
    (
        "efficientloftr-trial",
        "Joint image-pair matcher trial",
        "ldo-image-pair-matching-plan.md",
        "ldo-image-pair-matching-results.md",
        "ldo-image-pair-matching-results.json",
        "Factory/Desert fit and validation; failed promotion, no fresh test",
        "feature-depth-v2",
    ),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


def source(name):
    return json.loads((ROOT / "docs/archive" / name).read_text(encoding="utf-8"))


def feature_counts(row):
    s, c, u = (row[k] for k in ("supported", "contradicted", "untestable"))
    n = s + c + u
    return {
        "supported": s,
        "contradicted": c,
        "unknown": u,
        "judged_precision": s / (s + c) if s + c else None,
        "coverage": (s + c) / n if n else None,
        "correctness_bounds": [s / n, (s + u) / n] if n else None,
    }


def summaries():
    matching = source("ldo-matching-optimization-results.json")["test"]["aggregate"]
    oldtown = {}
    for name, row in matching.items():
        oldtown[name] = feature_counts(row["features"]["overall"])
        oldtown[name].update(
            {
                key: row[key]
                for key in (
                    "events",
                    "raw_event_hits",
                    "usable_event_hits",
                    "candidate_true",
                    "candidate_false",
                    "candidate_unknown",
                )
            }
        )
    trial = source("ldo-image-pair-matching-results.json")
    joint = {}
    for name in ("baseline", "candidate"):
        row = trial[name]["validate"]["overall"]
        joint[name] = feature_counts(row)
        joint[name].update(
            {key: row[key] for key in ("pairs", "positive_pairs", "usable_positive_pairs")}
        )
    joint["promoted"] = trial["preliminary_pair_gates_passed"]
    unseen = source("ldo-unseen-tartanair-results.json")["aggregate"]
    return {
        "matching-oldtown": oldtown,
        "efficientloftr-trial": joint,
        "factory-desert-frozen": {name: row["retrieval"] for name, row in unseen.items()},
    }


def table_text(rows):
    flat = [
        {"method": name, **{k: v for k, v in row.items() if not isinstance(v, list)}}
        for name, row in rows.items()
        if isinstance(row, dict)
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(flat[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(flat)
    return output.getvalue()


def headline_table(rows):
    baseline, selected = rows["baseline"], rows["selected"]
    lines = [
        "| Measurement | Baseline LDO (0.3) | Experimental LDO (0.4) |",
        "| --- | ---: | ---: |",
    ]
    for label, key in (
        ("Supported assignments", "supported"),
        ("Contradicted assignments", "contradicted"),
        ("Unknown assignments", "unknown"),
    ):
        lines.append(f"| {label} | {baseline[key]:,} | {selected[key]:,} |")
    for label, key in (
        ("Correct among judgeable", "judged_precision"),
        ("Judgeable coverage", "coverage"),
    ):
        lines.append(f"| {label} | {baseline[key]:.1%} | {selected[key]:.1%} |")
    for label, key in (
        ("Raw confirmed event hits", "raw_event_hits"),
        ("Events with ≥20 supported matches", "usable_event_hits"),
    ):
        lines.append(
            f"| {label} | {baseline[key]}/{baseline['events']} | {selected[key]}/{selected['events']} |"
        )
    return "\n".join(lines) + "\n"


def publish(output):
    values = summaries()
    registry = []
    for identifier, title, protocol, narrative, evidence, role, evaluator in STUDIES:
        folder = output / identifier
        sources = ["docs/archive/" + p for p in (protocol, narrative, evidence)]
        manifest = {
            "schema_version": 1,
            "kind": "historical_evidence_index",
            "experiment_id": identifier,
            "title": title,
            "status": "completed_historical",
            "dataset_role": role,
            "evaluator": evaluator,
            "sources": {p: digest(ROOT / p) for p in sources},
            "generator": {"path": "scripts/reproduce/publish.py", "sha256": digest(Path(__file__))},
            "raw_evidence_in_repository": False,
            "scope": "Index and derived presentation; not a new inference run or numerical rescore",
        }
        if identifier in values:
            write_json(folder / "metrics.json", values[identifier])
            (folder / "table.csv").write_text(
                table_text(values[identifier]), encoding="utf-8", newline="\n"
            )
            manifest["derived"] = {p: digest(folder / p) for p in ("metrics.json", "table.csv")}
            if identifier == "matching-oldtown":
                (folder / "table.md").write_text(
                    headline_table(values[identifier]), encoding="utf-8", newline="\n"
                )
                manifest["derived"]["table.md"] = digest(folder / "table.md")
        write_json(folder / "manifest.json", manifest)
        registry.append(
            {
                "id": identifier,
                "title": title,
                "manifest": identifier + "/manifest.json",
                "dataset_role": role,
                "evaluator": evaluator,
            }
        )
    write_json(output / "index.json", {"schema_version": 1, "experiments": registry})
    return values


def figures(values, output):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.ticker import MaxNLocator

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.hashsalt": "ldo-research-v1",
            "figure.facecolor": "white",
        }
    )
    output.mkdir(parents=True, exist_ok=True)
    provenance = []

    def save(fig, name, experiment, selection):
        for extension in ("svg", "png", "pdf"):
            path = output / f"{name}.{extension}"
            metadata = (
                {"Date": None}
                if extension == "svg"
                else ({"CreationDate": None, "ModDate": None} if extension == "pdf" else None)
            )
            fig.savefig(path, dpi=170, bbox_inches="tight", metadata=metadata)
            provenance.append(
                {
                    "file": path.name,
                    "sha256": digest(path),
                    "experiment_id": experiment,
                    "selection_rule": selection,
                    "source_metrics_sha256": hashlib.sha256(
                        (json.dumps(values[experiment], indent=2, sort_keys=True) + "\n").encode()
                    ).hexdigest(),
                }
            )
        plt.close(fig)

    row = values["matching-oldtown"]
    labels = ["Baseline 0.3", "Experimental 0.4"]
    methods = [row["baseline"], row["selected"]]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), layout="constrained")
    for i, key in enumerate(("supported", "contradicted", "unknown")):
        heights = [r[key] for r in methods]
        positions = [i * 3 + j for j in range(2)]
        bars = axes[0].bar(positions, heights, color=["#225f92", "#d67a26"], width=0.85)
        axes[0].bar_label(bars, labels=[f"{v:,}" for v in heights], padding=3, fontsize=9)
    axes[0].set_xticks([0.5, 3.5, 6.5], ["Supported", "Contradicted", "Unknown"])
    axes[0].set_ylabel("Reported feature assignments")
    axes[0].set_ylim(0, 120000)
    axes[0].set_title("Correspondence counts (depth-v2)")
    for j, key in enumerate(("raw_event_hits", "usable_event_hits")):
        bars = axes[1].bar(
            [j * 3, j * 3 + 1], [r[key] for r in methods], color=["#225f92", "#d67a26"], width=0.85
        )
        axes[1].bar_label(bars, padding=3)
    axes[1].set_xticks([0.5, 3.5], ["Raw retrieval", "≥20 supported matches"])
    axes[1].set_ylim(0, 20)
    axes[1].set_ylabel("Confirmed events reached / 17")
    axes[1].set_title("The useful-event trade-off")
    axes[1].yaxis.set_major_locator(MaxNLocator(integer=True))
    fig.legend(
        [Patch(color="#225f92"), Patch(color="#d67a26")],
        labels,
        loc="outside lower center",
        ncol=2,
        frameon=False,
    )
    save(
        fig,
        "matching-tradeoff",
        "matching-oldtown",
        "All three OldTownFall trajectories; both frozen LDO variants",
    )

    fig, ax = plt.subplots(figsize=(9, 3.1), layout="constrained")
    joint = values["efficientloftr-trial"]
    left = [0, 0]
    for key, color, hatch in (
        ("supported", "#246e54", ""),
        ("contradicted", "#b95142", "//"),
        ("unknown", "#9ca8b4", ".."),
    ):
        counts = [joint[n][key] for n in ("baseline", "candidate")]
        bars = ax.barh([1, 0], counts, left=left, color=color, hatch=hatch, label=key.title())
        ax.bar_label(
            bars,
            label_type="center",
            labels=["", f"{counts[1]:,}"],
            fontsize=10,
            bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none", "pad": 2},
        )
        left = [a + b for a, b in zip(left, counts, strict=True)]
    ax.text(
        left[0] + 4000,
        1,
        "\n".join(
            f"{key.title()}: {joint['baseline'][key]:,}"
            for key in ("supported", "contradicted", "unknown")
        ),
        va="center",
        fontsize=10,
    )
    ax.set_yticks([1, 0], ["SuperPoint + LightGlue", "EfficientLoFTR trial"])
    ax.set_xlabel("Reported feature assignments on 320 identical validation pairs")
    ax.set_title("More supported matches, more contradicted and unknown matches")
    fig.legend(*ax.get_legend_handles_labels(), loc="outside lower center", ncol=3, frameon=False)
    save(
        fig,
        "joint-matcher-trial",
        "efficientloftr-trial",
        "All 320 fixed validation pairs; no promotion or fresh-test replay",
    )

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4), layout="constrained")
    unseen = values["factory-desert-frozen"]
    x = [0, 1]
    bottom = [0, 0]
    for key, color, label in (
        ("true_positive_pairs", "#246e54", "Reference-positive"),
        ("false_positive_pairs", "#b95142", "Reference-negative"),
        ("unknown_pairs", "#9ca8b4", "Unknown"),
    ):
        counts = [unseen[n][key] for n in ("orb", "ldo")]
        bars = axes[0].bar(x, counts, bottom=bottom, color=color, label=label)
        axes[0].bar_label(bars, label_type="center")
        bottom = [a + b for a, b in zip(bottom, counts, strict=True)]
    axes[0].set_xticks(x, ["ORB + DBoW2", "LDO 0.3"])
    axes[0].set_ylabel("Returned candidate pairs")
    axes[0].set_title("Same replay; independent pair labels")
    bars = axes[1].bar(
        x,
        [unseen[n]["detected_confirmed_events"] for n in ("orb", "ldo")],
        color=["#626b75", "#225f92"],
    )
    axes[1].bar_label(bars, labels=["42 / 53", "48 / 53"], padding=4)
    axes[1].set_ylim(0, 60)
    axes[1].set_xticks(x, ["ORB + DBoW2", "LDO 0.3"])
    axes[1].set_ylabel("Confirmed event runs reached")
    axes[1].set_title("Incomplete references withhold overall recall")
    fig.legend(
        *axes[0].get_legend_handles_labels(), loc="outside lower center", ncol=3, frameon=False
    )
    save(
        fig,
        "retrieval-evidence",
        "factory-desert-frozen",
        "All 11 Factory/Desert trajectories; original pair policy",
    )
    write_json(
        output / "manifest.json",
        {
            "schema_version": 1,
            "generator_sha256": digest(Path(__file__)),
            "matplotlib": matplotlib.__version__,
            "figures": provenance,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results")
    parser.add_argument(
        "--figures", type=Path, help="Also render scientific figures to this directory"
    )
    parser.add_argument(
        "--update-readme", action="store_true", help="Refresh the marked headline table"
    )
    args = parser.parse_args()
    values = publish(args.output)
    if args.figures:
        figures(values, args.figures)
    if args.update_readme:
        readme = ROOT / "README.md"
        content = readme.read_text(encoding="utf-8")
        replacement = (
            "<!-- BEGIN OLDTOWN_TABLE -->\n"
            + headline_table(values["matching-oldtown"])
            + "<!-- END OLDTOWN_TABLE -->"
        )
        content, count = re.subn(
            r"<!-- BEGIN OLDTOWN_TABLE -->.*?<!-- END OLDTOWN_TABLE -->",
            replacement,
            content,
            flags=re.S,
        )
        if count != 1:
            raise ValueError("README must contain exactly one headline-table block")
        readme.write_text(content, encoding="utf-8")
    print(f"Indexed {len(STUDIES)} studies in {args.output}")


if __name__ == "__main__":
    main()
