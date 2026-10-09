# LDO

LDO is a modular visual loop-detection approach with replaceable retrieval and feature-matching models. The current configuration is **LDO-MegaLoc-LightGlue**, using frozen pretrained MegaLoc, SuperPoint and LightGlue components.

The evaluation program compares LDO with the pinned upstream **ORB + DBoW2** detector. Independent reference evaluators assess reported feature correspondences, image-pair overlap and relative pose. Reference labels never enter either detector or the shared operational verifier.

## Latest experiment: TartanAir V2

Seven ArchVizTinyHouseDay/Data_easy trajectories, identical grayscale images, K=5, and an equally applied 5-second temporal exclusion:

| Measurement | ORB + DBoW2 | LDO |
| --- | ---: | ---: |
| Candidate image pairs | 453 | 453 |
| Accepted constraints passing overlap and pose checks | 28 | 57 |
| Confirmed event runs reached by those constraints | 9/10 | 10/10 |
| Accepted constraints exceeding pose tolerance | 1/40 | 25/142 |
| Judgeable feature-match coverage | 65.9% | 47.8% |

LDO produced more independently confirmed constraints, alongside more accepted pose errors. A pose error does not by itself establish a false place detection. The shared geometric verifier estimates the transform from each method's observations. The pose tolerances are provisional: 0.20 m and 5 degrees.

This is a short synthetic pilot. Trajectories last 9-15 seconds; unknown reference labels withhold overall recall. Neither current detector consumes IMU, and the experiment does not establish long-term revisit performance, real-world superiority or out-of-distribution generalization.

- [Detailed findings and limitations](.docs/tartanair-reference-geometry-results.md)
- [Full pilot report](.docs/tartanair-pilot-report.md)
- [Frozen evaluation protocol](.docs/tartanair-reference-geometry-plan.md)

## Layout

```text
ldo/                         Replaceable detector components and model installation
loop_verification/           Shared observation-only geometric verifier
stereo_observations/          Stereo association and reconstruction
evaluation/                 Evaluation entry points, adapters and task modules
  src/tasks/feature_matching/ External feature XYZ evaluation and review GUI
  src/tasks/loop_closure/     Retrieval, independent event and pose assessment
  src/tasks/reference_geometry/ TartanAir reference-depth pilot
.docs/                       Architecture plans, research and findings
tests/                       Project tests
```

## Python environment

Python 3.11 and uv:

```powershell
uv sync --locked
uv run python -m pytest -q
```

GPU model inference and native ORB builds use WSL Ubuntu-24.04. Their environment and artifact paths are explicit in configuration; they must be installed separately on another machine. See [LDO installation](ldo/README.md), [shared verification](loop_verification/README.md), and the [TartanAir task guide](evaluation/src/tasks/reference_geometry/README.md).

## TartanAir task

After installing the model and native benchmark dependencies:

```powershell
uv run python evaluation/reference_geometry.py install
uv run python evaluation/reference_geometry.py prepare
uv run python evaluation/reference_geometry.py run --prepared evaluation/output/tartanair_reference_<id>
```

The installer pins dataset revision and verifies archive hashes. Saved runs include actual assignments, feature verdicts, verifier decisions, reference assessments and provenance. The FIFO evaluation file handler publishes dated Markdown and JSON reports.

Downloaded datasets, generated reference universes, raw run output, model checkpoints and virtual environments remain local. The repository contains source, configurations, the dependency lock and curated findings. Existing documentation may include local artifact paths from earlier experiments.
