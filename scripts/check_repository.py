"""Check active documentation, scientific preservation, and publication lineage."""

import ast
import hashlib
import importlib.util
import json
import re
import sys
from urllib.parse import unquote

from loop_eval.paths import project_root

ROOT = project_root()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    failures = []
    ledger = json.loads((ROOT / "docs/decisions/migration-ledger.json").read_text())
    pinned = {
        "evaluation/src/tasks/feature_matching/xyz/xyz.py",
        "evaluation/src/tasks/feature_matching/xyz/stereo_worker.py",
        "stereo_observations/stereo_worker.py",
        "evaluation/src/tasks/feature_matching/xyz/config.yaml",
    }
    for row in ledger["files"]:
        path = ROOT / row["new"]
        if not path.is_file():
            failures.append(f"Migrated file missing: {row['new']}")
        elif (row["old"].startswith(".docs/") or row["old"] in pinned) and digest(path) != row[
            "original_sha256"
        ]:
            failures.append(f"Historical/pinned bytes changed: {row['new']}")

    for record in ledger["numerical_preservation"]:
        expected = record["definition_ast_sha256"]
        tree = ast.parse((ROOT / record["new"]).read_text())
        actual = {
            node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in expected
        }
        if actual != expected:
            failures.append(
                f"Numerical definitions changed: {record['new']}; version and evaluate separately"
            )

    paths = [ROOT / name for name in ("README.md", "CONTRIBUTING.md", "CHANGELOG.md")]
    for folder in ("docs", "src", "configs", "examples", "tests", "data"):
        paths.extend((ROOT / folder).rglob("*.md"))
    for path in paths:
        relative = path.relative_to(ROOT)
        if relative.is_relative_to("docs/archive"):
            continue  # Original relative links intentionally retain historical meaning.
        text = path.read_text(encoding="utf-8")
        if len(re.findall(r"^```", text, flags=re.M)) % 2:
            failures.append(f"Unbalanced fenced code in {relative}")
        if len(re.findall(r"^\$\$$", text, flags=re.M)) % 2:
            failures.append(f"Unbalanced display math in {relative}")
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        for target in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)\)", text):
            target = target.strip("<>")
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            target = unquote(target.split("#")[0])
            if not (path.parent / target).exists():
                failures.append(f"Broken link in {relative}: {target}")

    index = json.loads((ROOT / "results/index.json").read_text())
    identities = set()
    for experiment in index["experiments"]:
        identifier = experiment["id"]
        if identifier in identities:
            failures.append(f"Duplicate experiment ID: {identifier}")
        identities.add(identifier)
        manifest_path = ROOT / "results" / experiment["manifest"]
        manifest = json.loads(manifest_path.read_text())
        if (
            manifest.get("schema_version") != 1
            or manifest.get("kind") != "historical_evidence_index"
        ):
            failures.append(f"Unsupported evidence manifest: {manifest_path}")
        if manifest.get("raw_evidence_in_repository") is not False:
            failures.append(f"Historical summary must not imply bundled raw evidence: {identifier}")
        for name, expected in manifest["sources"].items():
            if digest(ROOT / name) != expected:
                failures.append(f"Evidence source changed: {name}")
        for name, expected in manifest.get("derived", {}).items():
            if digest(manifest_path.parent / name) != expected:
                failures.append(f"Derived result changed: {identifier}/{name}")
        generator = manifest["generator"]
        if digest(ROOT / generator["path"]) != generator["sha256"]:
            failures.append(
                f"Result generator changed: {identifier}; regenerate publication artifacts"
            )

    for folder in ("diagrams", "figures"):
        base = ROOT / "docs/assets" / folder
        manifest = json.loads((base / "manifest.json").read_text())
        generator = manifest.get("generator", "scripts/reproduce/publish.py")
        if digest(ROOT / generator) != manifest["generator_sha256"]:
            failures.append(f"Figure generator changed: {folder}; regenerate assets")
        for row in manifest["figures"]:
            if digest(base / row["file"]) != row["sha256"]:
                failures.append(f"Figure bytes changed: {row['file']}")
            if "experiment_id" in row:
                metric_path = ROOT / "results" / row["experiment_id"] / "metrics.json"
                if digest(metric_path) != row["source_metrics_sha256"]:
                    failures.append(f"Figure source metrics changed: {row['file']}")

    spec = importlib.util.spec_from_file_location(
        "publication", ROOT / "scripts/reproduce/publish.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for identifier, metrics in module.summaries().items():
        stored = json.loads((ROOT / "results" / identifier / "metrics.json").read_text())
        if stored != metrics:
            failures.append(f"Derived metrics disagree with archived evidence: {identifier}")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    expected = module.headline_table(module.summaries()["matching-oldtown"]).strip()
    match = re.search(
        r"<!-- BEGIN OLDTOWN_TABLE -->\s*(.*?)\s*<!-- END OLDTOWN_TABLE -->", readme, re.S
    )
    if not match or match.group(1).strip() != expected:
        failures.append("README headline table disagrees with archived evidence")
    return failures


if __name__ == "__main__":
    errors = check()
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        raise SystemExit(1)
    print(
        "Active documentation, archive/pinned bytes, result metrics, and figure lineage verified."
    )
