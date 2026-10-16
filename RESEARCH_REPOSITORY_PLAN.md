# Research Repository and Scientific Documentation Plan

**Project:** LDO — visual loop detection, correspondence analysis, and independent geometric evaluation
**Prepared:** 2026-10-15
**Status:** Repository implementation delivered; current checks and external-runtime scope are recorded in `docs/validation.md`.
**Goal:** Make the work understandable, reproducible, mathematically precise, and credible to a research reviewer who has never seen the project.

The standard should come from the quality of the research and its evidence. A polished directory or university-style wording cannot establish scientific quality. Do not imply Stanford affiliation, peer review, novelty, or publication status without supporting facts.

### Implementation record

The runtime packages now live under `src/`, evaluation uses `loop_eval`, and policies/recipes have one home under `configs/`. Tests are consolidated into unit/integration/regression suites. The repository installs as a package and provides CPU replay, runtime diagnosis/profile generation, evidence curation, scientific figure generation, and wheel checks. Current method, notation, protocol/results indexes, contribution/citation metadata, and the illustrated mathematical README are implemented.

Historical `.docs/` evidence is preserved byte-for-byte in `docs/archive/`, with an old-to-new migration ledger and numerical-definition preservation checks. The archive deliberately retains its original structure; current indexes provide the new navigation. Existing bulk evidence stays in place. Large modules retain their cohesive responsibilities instead of being split solely by file length.

See [validation](docs/validation.md), [layout decisions](docs/decisions/layout.md), and the [documentation index](docs/index.md). Full external model/native experiment reruns, a genuinely independent second-machine scientific reproduction, and new research studies are not claimed by repository checks. The project license remains an owner decision; authorship is Elay Barnoam.

This plan covers the directory tree, Python packaging, module design, native/GPU execution, configuration, experimental integrity, mathematical documentation, figures, and the final README. It separates changes that preserve existing behavior from new research that requires a new protocol and fresh evidence.

## 1. Current repository: evidence and priorities

This plan is based on inspection of the current source, configuration, task guides, and curated findings. It is not a complete correctness review or a new execution of the experiments. The starting checkout was clean. The inventory contains **356 tracked files, 208 Python files, 86 Markdown files, and 32 Python files named as tests**; these are file counts, not test-case counts.

| Area | Observed state | Required outcome |
| --- | --- | --- |
| Detector | `ldo/` already separates retrieval, matching, policies, contracts, memory, and evidence | Preserve its small model-independent interface; document invariants and test them through that interface |
| Runtime verification | `loop_verification/` estimates query-to-history metric pose from observations | Keep operational decisions separate from independent correctness labels |
| Stereo | `stereo_observations/` owns shared image-only reconstruction | Preserve geometry conventions and fingerprint-sensitive worker behavior |
| Evaluation | `evaluation/src/` contains reusable infrastructure, benchmark adapters, tasks, and viewers | Introduce a clearly named installed evaluation package; keep experiment-specific logic identifiable |
| Packaging | `uv` lock exists, but `[tool.uv] package = false`; pytest adds repository paths | Support installation and imports outside the checkout directory |
| Documentation | `.docs/` mixes architecture, protocols, results, JSON summaries, research notes, and figures | Establish a visible `docs/` hierarchy and a result/protocol index |
| README | Contains extensive chronological findings, caveats, and commands, but no central mathematical presentation or overview figure | Present one coherent problem/method/evidence narrative and link to the full research record |
| Tests | Both `tests/` and `evaluation/tests/` contain important regressions | Organize tests by purpose and mark external-runtime requirements without losing coverage |
| Artifacts | Datasets and outputs are ignored; curated results and some PNGs are tracked | Preserve immutable runs; publish compact evidence with checksums and provenance |
| Environment | Native/GPU workflows use WSL and several `/opt/loop-detector/...` paths | Make machine-specific paths configurable and document supported execution profiles |
| Research identity | Project metadata says visual–inertial; current detector input is visual | State current capabilities explicitly; keep IMU work a separately evaluated extension |
| Release infrastructure | No tracked `.github/` workflows, root license, citation file, or contribution guide was found | Add appropriate automation and project metadata with verified authorship/license information |

### Existing strengths to preserve

- Reference poses, depth, and labels are excluded from detector inference and operational verification.
- Feature correspondence verdicts, candidate overlap labels, event hits, and accepted constraints are treated as different measurements.
- Unknown evidence is retained rather than silently converted into negative evidence.
- Source/model/configuration fingerprints, saved assignments, pinned dependencies, and historical reports already support auditing.
- Failed trials and retention losses are documented, including the EfficientLoFTR trial and the confidence-0.4 event loss.
- The detector already queries before inserting the current frame and applies temporal eligibility before top-K selection.

### Priorities

1. **P0 — scientific correctness:** establish scope, evidence lineage, coordinate conventions, evaluation denominators, and dataset-role history.
2. **P1 — reproducibility and organization:** package installation, configurable execution, safe migration, consistent experiment records, and automated checks.
3. **P2 — communication:** curated documentation, generated figures, mathematical method explanation, and the final README.
4. **P3 — additional research:** inertial integration, real-world validation, new models, or downstream SLAM evaluation. These are separate experiments, not prerequisites for reorganizing the current work.

## 2. Scientific scope and contribution statement

### Step 1 — Write the scope before moving files

- [ ] Create `docs/overview.md` with the task, supported inputs, outputs, operating assumptions, and implemented capabilities.
- [ ] Define the current system as visual candidate retrieval and correspondence generation, with optional observation-only stereo/PnP verification and independent offline evaluation.
- [ ] Explicitly state that current detectors do not consume IMU and that a verified relative-pose proposal is not an integrated SLAM correction.
- [ ] Choose a public project title consistent with the implemented system. Keep existing identifiers compatible during migration; changing repository/package names is a separate decision.
- [ ] Distinguish the original research contribution from the pretrained MegaLoc, SuperPoint, LightGlue, ALIKED, and EfficientLoFTR methods and the ORB/DBoW2 baseline.
- [ ] Write two or three precise research questions. Candidate questions are below; they become claims only when the experiment supports them.

| Research question | Evidence needed | Claim restriction |
| --- | --- | --- |
| Does LDO retrieve more confirmed revisit opportunities under a shared causal replay protocol? | Same sequences, timestamps, exclusions, K, independent pair labels, event IDs, and unknown accounting | Confirmed-event coverage is not overall recall when reference labels are incomplete |
| Can matching changes remove incorrect assignments while preserving useful observations? | Identical-pair ablations, correct/incorrect/unknown counts, per-scene outcomes, and retained pair/event identities | Better judged precision alone does not establish fewer incorrect assignments or preserved event utility |
| Does observation-only verification produce reliable relative-pose constraints? | Shared verifier, independent overlap and pose assessment, abstentions, runtime, and failure examples | Geometric acceptance alone is not proof of a correct place match or improved SLAM trajectory |

**Deliverable:** one scope document and a contribution table with columns for contribution, implementation, evidence, and limitation.
**Gate:** every headline statement can be mapped to a saved experiment or is explicitly marked as a research objective.

## 3. Target directory tree

Use one repository and one build configuration initially. Multiple distributions, a plugin framework, or a general workflow engine are unnecessary unless actual consumers require them. Preserve the useful `ldo`, `loop_verification`, and `stereo_observations` import names while moving them under `src/`.

```text
.
|-- README.md                         # Public problem/method/evidence entry point
|-- RESEARCH_REPOSITORY_PLAN.md        # This roadmap until execution is complete
|-- pyproject.toml                    # Build, dependencies, tooling, entry points
|-- uv.lock
|-- .python-version
|-- .gitignore
|-- .gitattributes
|-- .env.example                      # Optional documented local path overrides
|-- LICENSE                           # Only after ownership/license decision
|-- CITATION.cff                      # Verified authors and release metadata
|-- CONTRIBUTING.md
|-- CHANGELOG.md
|-- .github/
|   `-- workflows/
|       |-- checks.yml                # CPU tests, lint, packaging, documentation
|       `-- research-runtime.yml      # Explicit optional native/GPU checks
|-- src/
|   |-- ldo/
|   |   |-- contracts.py
|   |   |-- detector.py
|   |   |-- configuration.py
|   |   |-- retrieval/
|   |   |-- matching/
|   |   |-- policies/
|   |   |-- memory.py
|   |   |-- evidence.py
|   |   `-- ...                       # Retain cohesive existing modules
|   |-- loop_verification/
|   |   |-- contracts.py
|   |   |-- verifier.py
|   |   |-- pose_estimation.py
|   |   |-- acceptance.py
|   |   `-- stereo_depth.py
|   |-- stereo_observations/
|   |   |-- geometry.py
|   |   |-- rectification.py
|   |   |-- dense.py
|   |   `-- stereo_worker.py
|   `-- loop_eval/
|       |-- cli.py                    # Installed research entry point
|       |-- benchmarks/               # LDO, ORB+DBoW2, ORB-SLAM3 adapters
|       |-- datasets/                 # Dataset-specific adapters and installation
|       |-- infrastructure/           # Existing orchestration, publishing, reports
|       |-- tasks/                    # Distinct evaluations and experiments
|       |   |-- reference_geometry/
|       |   |-- reference_depth_v2/
|       |   |-- loop_closure/
|       |   |-- feature_matching/
|       |   |-- optimization/
|       |   |-- matching_optimization/
|       |   |-- matching_diagnostics/
|       |   |-- descriptor_analysis/
|       |   |-- image_pair_matching/
|       |   `-- unseen_tartanair/
|       `-- visualization/            # Shared rendering only where reuse exists
|-- configs/
|   |-- models/                       # Named inference variants
|   |-- verification/                 # Operational acceptance/stereo settings
|   |-- evaluation/                   # Independent evaluator policies, versioned
|   |-- experiments/                  # Complete reproducible experiment recipes
|   `-- runtime/                      # Portable examples of host/WSL profiles
|-- tests/
|   |-- unit/
|   |-- integration/
|   |-- regression/
|   |-- fixtures/                     # Small synthetic or redistributable evidence
|   `-- conftest.py
|-- scripts/
|   |-- reproduce/                    # Thin documented launchers
|   `-- figures/                      # Figure regeneration entry points
|-- examples/
|   `-- minimal_replay/               # Small documented CPU example
|-- docs/
|   |-- index.md
|   |-- overview.md
|   |-- notation.md
|   |-- method.md
|   |-- architecture.md
|   |-- installation.md
|   |-- reproducibility.md
|   |-- limitations.md
|   |-- references.bib
|   |-- protocols/                    # Immutable, dated experiment protocols
|   |-- results/                      # Curated findings linked to manifests
|   |-- decisions/                    # Decisions and rationale
|   |-- research/                     # Background notes and investigations
|   |-- archive/                      # Superseded historical documentation
|   `-- assets/
|       |-- diagrams/                 # Editable diagram sources and SVG exports
|       `-- figures/                  # Curated PNG/SVG/PDF research figures
|-- results/
|   |-- index.json                    # Public experiment registry
|   `-- <experiment-id>/
|       |-- manifest.json
|       |-- metrics.json
|       |-- tables/                   # Compact generated CSV tables
|       `-- figure_manifest.json
|-- data/
|   |-- README.md                     # Acquisition, licensing, expected layout
|   `-- manifests/                    # Checksums and metadata, not bulk data
|-- artifacts/                        # Ignored local generated runs/cache pointers
`-- evaluation/                       # Temporary compatibility launchers only
```

Tree entries are proposed destinations, not files that already exist. Add directories when they gain a real responsibility. Keep dataset-specific code with its task until a second consumer justifies extraction. Keep ORB native sources with their adapter initially; explicitly include required sources in distributions, or document native builds as a checkout-only capability.

### Migration map

| Current location | Proposed destination | Migration requirement |
| --- | --- | --- |
| `ldo/` | `src/ldo/` | Preserve public imports and detector behavior |
| `loop_verification/` | `src/loop_verification/` | Preserve pose direction, policies, and reference exclusion |
| `stereo_observations/` | `src/stereo_observations/` | Preserve pinned worker bytes and numerical formulas |
| `evaluation/src/benchmarks/` | `src/loop_eval/benchmarks/` | Update worker/module invocation paths and native build inputs |
| `evaluation/src/modules/` | `src/loop_eval/infrastructure/` | Preserve process lifecycle and singleton FIFO report ownership |
| `evaluation/src/tasks/` | `src/loop_eval/tasks/` | Keep evaluator v1/v2 distinct; update dynamic imports and subprocesses |
| Root/evaluation YAML files | `configs/` by responsibility | Preserve effective values; record old-to-new path mapping |
| `evaluation/*.py` | Installed commands plus temporary wrappers | Existing documented commands delegate during a defined transition |
| `.docs/*plan.md` | `docs/protocols/` or `docs/archive/` | Preserve dates, historical policy, and interpretation |
| `.docs/*results*`, `*report*` | `docs/results/` and `results/<id>/` | Classify narrative vs generated report vs machine-readable source |
| `.docs/*research*` and architecture notes | `docs/research/`, `docs/architecture.md`, `docs/decisions/` | Consolidate current guidance; retain historical versions |
| `.docs/figures/` | `docs/assets/figures/` | Preserve evidence identity, figure provenance, and links |
| `tests/` and `evaluation/tests/` | One classified `tests/` tree | Preserve collected test identities in a migration ledger |
| Existing ignored datasets/runs | Leave in place initially | Add configurable roots; do not physically move bulk or historical artifacts |

## 4. Step-by-step implementation sequence

### Phase 0 — Capture the baseline and migration constraints

1. Record the starting commit, dirty-worktree state, supported operating systems, Python version, and current launch commands.
2. Inventory tracked files, imports, executable modules, YAML references, report links, subprocess invocation strings, model installers, and native build inputs.
3. Record fresh baseline test/lint outcomes for Windows and WSL separately. Historical documents report a Windows file-lock failure; determine its current status rather than calling either platform clean based on an old report.
4. Identify representative saved evidence for: causal retrieval, matching, direct-reference evaluation, operational verification, and generated reporting. Record access requirements and hashes.
5. Save small redistributable characterization fixtures and expected candidate IDs, ranks, assignments, verdicts, event IDs, and report totals. Preserve historical XYZ/policy hashes and worker bytes.
6. Create a migration ledger: old path, new path, imports/commands affected, compatibility action, validation, and completion state.
7. Write decisions for package naming, configuration ownership, data roots, and evidence immutability. Decisions describe the final choice and rationale without creating unnecessary process.

**Deliverables:** baseline validation record, migration ledger, fixture manifest, and initial scope document.
**Gate:** current behavior and known failures are recorded; no scientific result must be regenerated merely to establish a baseline.

### Phase 1 — Organize documentation and evidence navigation

1. Classify every existing Markdown/JSON document as current guide, protocol, results narrative, generated report, research note, or historical archive.
2. Create `docs/index.md` and a table connecting research questions to protocols, implementations, result summaries, and raw-evidence locations.
3. Move documents in small groups and repair relative links. Use concise redirect notes at heavily referenced old documentation paths during transition where useful.
4. Keep historical protocols and generated source snapshots immutable. A current guide may explain an old result but must not rewrite what its original protocol said.
5. Introduce an experiment registry before choosing README headline results. Record evaluator version, variant, dataset role at execution time, and current admissible use.
6. Audit dataset-role history: Factory/Desert were fresh tests for one earlier experiment and subsequently development data for matching selection. OldTownFall has now been inspected and cannot be advertised as fresh for future tuning decisions.
7. Establish the documentation destinations from the target tree. Do not maintain two editable copies of the same current method or installation instructions.

**Deliverables:** documentation index, experiment registry, repaired navigation, and archive policy.
**Gate:** a reader can locate the protocol and evidence behind any existing README result without searching chronological notes.

### Phase 2 — Establish an installable package and stable commands

1. Select and configure a build backend in `pyproject.toml`; enable package installation rather than `package = false`.
2. Move the three runtime packages under `src/` while preserving their import names. Introduce `loop_eval` as the evaluation namespace, avoiding generic top-level `tasks`, `modules`, and `benchmarks` imports.
3. Update absolute/relative imports, dynamic loading, subprocess `-m` targets, WSL launchers, native executable discovery, fixtures, and installer references.
4. Keep thin compatibility wrappers for existing `evaluation/*.py` commands. Document their retirement point; do not duplicate workflow logic.
5. Provide installed commands for environment diagnosis, a CPU smoke example, reference preparation/evaluation, saved-evidence reporting, and figure generation. Final names are established here and used consistently afterward.
6. Remove pytest path injection only after installed imports work. Run an import/smoke check from a temporary directory outside the repository.
7. Build a wheel and source distribution. Verify package contents, required non-Python resources, optional-dependency behavior, and import without CUDA/native dependencies.
8. Keep experiment recipes under `configs/`; accept explicit config paths. If commands need built-in defaults, package those resources deliberately rather than discovering the checkout through the current working directory.

**Deliverables:** installable distribution, command reference, working compatibility wrappers, and packaging smoke check.
**Gate:** a clean environment can install the project and run the CPU example without repository-specific `PYTHONPATH` changes.

### Phase 3 — Improve module interfaces and code clarity

1. Preserve the useful existing seams: `GlobalEncoder`, `PairEngine`, `ProposalPolicy`, detector input/output records, and verifier observation/result records.
2. Document each interface's shape/dtype, coordinate frame, units, ordering, mutability, error modes, lifecycle, and performance implications. A Python type annotation alone is insufficient.
3. Preserve sparse feature-ID assignments and pair-dependent pixel correspondences as distinct contracts. EfficientLoFTR's pair-dependent points must not masquerade as cached SuperPoint feature IDs.
4. Keep model selection in adapter factories. Keep upstream library imports and checkpoint loading inside concrete adapters; CPU imports should not require every model package.
5. Replace undocumented configuration dictionaries at critical seams with validated records or an equivalently explicit schema. Reject incompatible descriptor families, invalid budgets, invalid timestamps, and unknown configuration keys.
6. Keep small numerical routines focused on calculation, returning results and diagnostics. Put filesystem access, process control, and report publication in their existing appropriate modules.
7. Review larger files by responsibility, starting with `markdown_report.py`, the evidence viewer, `comparison.py`, and stereo evaluation. Split only where a coherent module with a smaller interface emerges; file length alone does not justify a new abstraction.
8. Preserve the singleton FIFO report writer, ordering constraints, cancellation, cleanup, and atomic completion semantics. Do not replace working orchestration as part of a cosmetic cleanup.
9. Add annotations and docstrings first to public contracts, geometry, configuration, and evidence readers. Adopt type checking incrementally; isolate third-party typing gaps.
10. Document exact cosine retrieval cost and index growth. The local feature cache is bounded; historical descriptor storage grows with trajectory length. Do not claim bounded total memory or real-time operation without measurement.

**Deliverables:** interface reference, smaller cohesive modules where justified, validated configuration, and explicit error semantics.
**Gate:** behavior-preserving replay agrees on candidate order, assignments, feature verdicts, accepted decisions, and event identities. Any intentional numerical change gets a separate change record and evaluation.

### Phase 4 — Make configuration and runtime portable

1. Separate model settings, operational verification settings, independent evaluator settings, experiment recipes, and local runtime paths.
2. Define path resolution explicitly: configuration-relative paths for recipe assets and documented overrides for data/model/artifact roots. Define and test override precedence.
3. Replace required hardcoded `/opt/...`, home-directory, and Windows paths with configurable roots. Keep those locations as optional examples for the current machine.
4. Write a command that diagnoses Python/dependency versions, CUDA availability, model/checkpoint hashes, WSL distribution, compiler/native binaries, dataset manifests, and writable output roots.
5. Document three supported profiles: CPU development/smoke, Windows review/launch, and WSL native/CUDA experiments. State exactly which operations each profile can run.
6. Verify optional extras and the existing lock strategy across supported profiles. Pin upstream source/checkpoint revisions and native build inputs independently of Python dependency locking.
7. Resolve public release licensing for project code and separately record upstream model, source, vocabulary, checkpoint, and dataset terms. Do not select a license or invent author metadata during reorganization.
8. Make downloads explicit, integrity-checked, and resumable where supported. Ordinary imports, tests, help, and documentation rendering should not silently download data or weights.

**Deliverables:** portable recipe examples, environment diagnosis command, dependency/license inventory, and installation guide.
**Gate:** a second machine can reach the CPU example with documented commands; GPU/native instructions identify every separately installed requirement.

### Phase 5 — Standardize reproducible experiments and evidence

1. Give every experiment an immutable ID and record its research question, protocol revision, split roles, baseline, variants, and promotion criteria.
2. Save the fully resolved configuration, source commit/dirty-state fingerprint, dataset/model identities, runtime versions, seeds, calibration, input order, evaluator policy, and artifact checksums.
3. Standardize run states such as prepared, running, failed, and completed. Publish completion only after required outputs validate; a mutable latest pointer must reference a completed immutable run.
4. Keep raw evidence outside Git; track compact manifests, metrics, and selected redistributable figures. Document retrieval of larger evidence from a stable archive if one is available.
5. Make reporting a deterministic transformation of saved evidence, separate from model execution. Reports should not need to rerun models to regenerate tables or figures.
6. Preserve matched feature identities, original camera coordinates, scores and score meanings, zero-match pairs, unknown reasons, and query/history lineage.
7. Preserve evaluator v1 and depth-v2 identities. A rescore creates a new result linked to the original detector outputs; it does not replace the old result or inherit unrelated pair/event changes.
8. Record source/config path changes as new provenance. Structural refactors can change hashes even when outputs agree: validate old evidence with its original manifest and create an explicit new derivation record. Never edit old hashes to make a cache appear valid.
9. Create a compact report-only reproduction example and a full-run recipe. Include expected totals/tolerances, hardware, storage, and measured run duration once verified.
10. Track failed candidates and selection history. Later reuse of a test scene makes it development evidence for that later decision; it cannot repeatedly function as a fresh test.

**Minimum run manifest fields:**

```yaml
schema_version: <version>
experiment_id: <immutable-id>
protocol_id: <protocol-and-revision>
status: <completed-or-other-state>
source: <commit-dirty-state-and-relevant-source-hashes>
configuration: <resolved-config-location-and-sha256>
dataset: <revision-sequences-calibration-input-order-and-split-roles>
models: <upstream-revisions-checkpoint-hashes-and-preprocessing>
runtime: <os-python-libraries-native-build-device-and-seeds>
evaluation: <evaluator-version-policy-hash-and-reference-scope>
artifacts: <relative-locations-sizes-and-checksums>
derived_from: <source-run-or-null>
```

This is a field checklist, not an implemented schema. Define concrete types and validation before using it as a machine contract.

**Deliverables:** manifest schema, experiment registry, artifact policy, report-only reproduction, and full experiment recipes.
**Gate:** each public result can be traced to exact inputs and regenerated from its evidence, with inaccessible evidence clearly identified.

### Phase 6 — Strengthen evaluation design and verification

1. Separate system comparison on each detector's own retrieved pairs from matching comparison on identical pairs. Label tables accordingly.
2. Freeze dataset splits and policies before new model selection. Select thresholds on development data and reserve genuinely unexamined data for the next fresh test.
3. Keep reference-independent pair/event definitions and explicit coverage of the eligible history. Retrieval-union pair sampling is useful for ablations, but is not an exhaustive reference universe for recall.
4. Report feature, pair, event, operational acceptance, pose, and downstream SLAM measurements separately. State the denominator of each rate beside the result.
5. Retain supported/contradicted/unknown counts and bounds. Unknown coverage is part of the result, not a detail removed for a cleaner table.
6. Report per-scene/per-trajectory results, micro-aggregates, and appropriate macro-aggregates. Retain useful-event identities, not only aggregate counts that can hide losses.
7. Predeclare a statistical analysis unit that reflects temporal dependence. Use paired sequence or appropriate temporal-block analyses when enough independent evidence exists; do not treat individual correspondences as independent experimental samples.
8. Report the scope and limitations of uncertainty estimates. The existing temporal-event bootstrap is conditional on complete references and is not a cross-environment generalization interval.
9. Measure retrieval, extraction, matching, stereo, verification, and offline evaluation separately. For GPU measurements, define synchronization, warmup, cache state, hardware, and repeated-trial procedure; report distributions rather than a single favorable frame.
10. Define a future real-world and downstream SLAM protocol separately if those claims are desired. Include consistent calibration, sensor use, integration, and trajectory metrics; do not infer them from synthetic correspondence counts.

**Deliverables:** metric dictionary, frozen protocol templates, result-table schemas, and runtime-measurement protocol.
**Gate:** every table answers one declared question and exposes its population, reference completeness, and uncertainty limits.

### Phase 7 — Add focused quality checks and CI

1. Classify existing tests as unit, integration, regression, native, GPU, or dataset-dependent. Preserve the tests before renaming or moving them.
2. Keep a fast CPU suite for chronology, contract validation, geometry, metrics, evidence integrity, and report generation. External dependencies use explicit markers and clear skip reasons.
3. Add missing behavior checks at real interfaces: query-before-insert, equality at the temporal cutoff, stable score ties, session reset, sparse/pixel correspondence differences, depth abstention, pose direction, and evaluator-version separation.
4. Add small synthetic geometry checks for axial depth, transform composition, pixel-center convention, distortion, resized feature coordinates, occlusion, sky/unknown semantics, and behind-camera points.
5. Verify report reconstruction on compact saved evidence, source-hash tampering rejection, interrupted-run handling, process cleanup, and preservation of zero-match candidates.
6. Run Ruff lint/format checks and incremental type checking. Separate legacy cleanup from behavior changes; do not use blanket ignores merely to make CI green.
7. Run CPU checks on supported Windows/Linux profiles, plus wheel install/import checks outside the repository. Make native/GPU jobs explicit on suitable infrastructure with no credentials embedded in artifacts.
8. Validate relative documentation links, figure references, manifest schemas, generated-table consistency, and Markdown/math rendering. Prefer local deterministic link checks in ordinary CI.

**Deliverables:** CI workflows, test guide, reproducible fixtures, and current validation record.
**Gate:** required CPU/packaging/docs checks pass; native/GPU results are separately reported and never represented by CPU fixtures alone.

### Phase 8 — Write the mathematical method and metric definitions

Write `docs/notation.md` and `docs/method.md` first, using Section 5 below. Then extract a concise version into the README.

1. Define all frames, timestamps, coordinates, units, score meanings, and random variables before using them.
2. Present the actual visual retrieval/matching method, optional operational verification, and offline reference evaluation as separate subsections.
3. Map each equation and assumption to its implementation and policy configuration.
4. Describe actual algorithms: exact cosine retrieval; pretrained adapters; EPnP/RANSAC and LM refinement for runtime verification; independent depth/pose checks offline.
5. Keep mathematical objectives and implementation details aligned. A robust optimization formulation may explain PnP, but must not falsely imply a differentiable end-to-end objective or a different solver.
6. State synthetic/static-scene assumptions, reference-depth limitations, pretrained exposure uncertainty, incomplete annotations, and experimental operating thresholds.
7. Put unimplemented IMU models or learned objectives in an explicitly future-work document rather than the method description.

**Deliverables:** notation table, equation-to-code map, method document, and metric definitions.
**Gate:** a reviewer can reproduce the geometric conventions and measurement denominators from the text without guessing.

### Phase 9 — Produce figures from evidence

1. Implement the figure specification in Section 6, reusing existing matching-diagnostic images where suitable.
2. Regenerate quantitative figures from versioned metrics/evidence. Do not manually transcribe bar heights or create illustrative performance numbers.
3. Keep editable SVG/Mermaid sources for diagrams and Python plotting code for scientific figures. Use actual saved image pairs for correspondence examples.
4. Record per-figure experiment ID, evaluator version, source evidence, selection rule, rendering code/configuration, and output hash.
5. Check axes, units, denominators, unknown categories, legends, caption scope, readable fonts, image rights, and grayscale/color accessibility.
6. Verify README rendering in light/dark display and at a narrow page width; provide raster previews where vector rendering is unreliable.

**Deliverables:** figure scripts, curated assets, captions/alt text, and figure manifest.
**Gate:** every result figure is reproducible and its caption explains exactly what evidence it represents.

### Phase 10 — Rewrite and validate the public README

1. Use the structure in Section 7 and established project identity from Phase 0.
2. Lead with the task and implemented contribution. Present the architecture figure immediately after a short overview.
3. Include compact mathematical definitions, an evidence-backed result table, representative failure examples, and runnable quickstart commands.
4. Link complete protocols, mathematical details, all ablations, failed promotions, and machine-readable results. Move chronological research history out of the main narrative.
5. Verify commands in a clean environment and confirm that the output matches the described example. Separate CPU smoke, saved-evidence reproduction, and full GPU/native experiments.
6. Add verified citation, license, authorship, acknowledgment, and upstream references. Do not invent a DOI, publication venue, institution, or badges.
7. Review every claim against the experiment registry. Check that the README neither merges evaluator versions nor relabels old test scenes as fresh.
8. Run final documentation/link/asset checks and record the final validation state and remaining limitations.

**Deliverables:** final README, reproducibility guide, verified project metadata, and release checklist.
**Gate:** an unfamiliar reader can understand the problem, identify the contribution, run a small example, trace a result, and see the method's limitations.

## 5. Mathematical specification to develop

These definitions are a writing specification grounded in the current implementation, not a proposal to change its numerical policies. Reconcile each statement with the relevant evaluator version before publication.

### 5.1 Notation and problem definition

| Symbol | Meaning | Convention |
| --- | --- | --- |
| $`I_q, I_h`$ | Query and historical camera images | Original sensor pixel coordinates |
| $`t_q, t_h`$ | Frame timestamps | Integer nanoseconds in contracts; seconds only after explicit conversion |
| $`\Delta`$ | Temporal exclusion duration | Same unit as timestamps in a given equation |
| $`K`$ | Camera intrinsic matrix | Pixels; use $`k`$ for the retrieval budget to avoid ambiguity |
| $`T_{AB}`$ | Transform taking coordinates from frame B to frame A | $`X_A=R_{AB}X_B+t_{AB}`$; homogeneous form where needed |
| $`T_{Wq},T_{Wh}`$ | Reference camera-to-world poses | Offline evidence only |
| $`z_q(u)`$ | Axial camera depth at pixel $`u`$ | Metres; not Euclidean range along the ray |
| $`g(I)`$ | Global visual descriptor | Unit-normalized, fingerprinted representation |
| $`\mathcal C_q`$ | Retrieved historical candidates | Ranked subset of causally eligible history |
| $`\mathcal M_{qh}`$ | Reported temporal correspondences | Sparse IDs or pair-dependent pixels, explicitly distinguished |
| $`y_{qh}`$ | Independent pair label | loop / non-loop / unknown |
| $`a_{qh}`$ | Operational verification result | accepted / rejected / insufficient evidence |

For each query, eligible history is

```math
\mathcal H_q=\{h\in\text{past frames}:\ t_h\le t_q-\Delta\}.
```

The inequality includes equality, matching `bisect_right` in the current index. Frame identifiers and timestamps are different quantities; only timestamps participate in the temporal comparison.

The implemented task is to produce ranked candidates and their correspondences from available camera observations. A candidate score is not a calibrated probability of a loop. Define a place match through an independent overlap policy, rather than assuming the detector output defines its own truth.

### 5.2 Global retrieval

```math
d_q=\frac{g(I_q)}{\|g(I_q)\|_2},\qquad
s(q,h)=d_q^\top d_h,\qquad
\mathcal C_q=\mathrm{Top}_{k}\{(h,s(q,h)):h\in\mathcal H_q\}.
```

Use $`k`$ in prose and code for the candidate budget. Here $`\mathrm{Top}_k`$ returns the ordered candidate identifiers, with earlier-timestamp tie breaking and all eligible frames returned when fewer than $`k`$ exist. Query before inserting $`q`$. Document zero/nonfinite descriptor rejection and representation fingerprints. Current exact retrieval computes similarities over eligible history and orders them; do not describe it as an approximate-nearest-neighbor index.

**Implementation:** `ldo/retrieval/index.py`, `ldo/detector.py`, and encoder adapters.

### 5.3 Local features and assignments

```math
F_q=\{(u_i^q,d_i^q,\alpha_i^q)\}_{i=1}^{n_q},\qquad
\mathcal M_{qh}=\{(i,j,c_{ij})\}.
```

Define original-pixel coordinates $`u`$, local descriptors $`d`$, extractor scores $`\alpha`$, and matcher scores $`c`$. The sparse contract requires one-to-one endpoint IDs. Explain compatible extractor/matcher families, score thresholds, exact comparison operators, feature budgets, and resize-to-original-coordinate mapping.

For an image-pair matcher use $`\{(u_i^q,v_i^h,c_i)\}`$ instead; its observations can depend on both images and need not share stable cached feature IDs. Do not call matching scores posterior correctness probabilities without calibration evidence.

**Implementation:** `ldo/contracts.py`, `ldo/matching/`, and the configuration factories.

### 5.4 Optional observation-only relative-pose verification

Backproject reliable query stereo observations and estimate a transform into the historical camera:

```math
X_i^q=z_q(u_i^q)K_q^{-1}\tilde u_i^q,\qquad
\hat T_{hq}: X_q\mapsto X_h.
```

This pinhole backprojection formula assumes undistorted coordinates. The final method must describe the actual raw-camera calibration/distortion treatment; do not apply $`K^{-1}`$ directly to distorted pixels and call it exact geometry.

Explain the PnP task through historical reprojection residuals:

```math
r_i(T)=\left\|\pi_h(TX_i^q)-v_i^h\right\|_2,
```

where $`\pi_h`$ includes the historical camera's projection/distortion model. The implementation uses seeded EPnP/RANSAC, LM refinement, recomputed residuals/inliers, and deterministic count, ratio, residual, cheirality, geometry, and conditioning gates. Explain those gates with their configuration keys and units.

Distinguish absent/unreliable depth, failed estimation, degenerate geometry, and rejection by policy. Runtime inputs contain no reference pose, overlap label, or offline feature verdict. Accepted output is a geometric constraint proposal, not an independently confirmed loop.

**Implementation:** `loop_verification/pose_estimation.py`, `acceptance.py`, `contracts.py`, and `stereo_observations/`.

### 5.5 Independent correspondence evaluation

For the reference pinhole camera, obtain a reference relative transform and endpoint positions:

```math
T_{hq}^{\star}=(T_{Wh}^{\star})^{-1}T_{Wq}^{\star},\qquad
X_q=z_q^{\star}(u)K_q^{-1}\tilde u,\qquad
X_h=z_h^{\star}(v)K_h^{-1}\tilde v.
```

Define metric disagreement and symmetric reprojection disagreement:

```math
e_{XYZ}=\|T_{hq}^{\star}X_q-X_h\|_2,
```

```math
e_{px}=\max\left(
\|\pi_h(T_{hq}^{\star}X_q)-v\|_2,
\|\pi_q((T_{hq}^{\star})^{-1}X_h)-u\|_2
\right).
```

Transforms on 3D points use the rigid-transform action, or homogeneous coordinates explicitly. A correspondence is supported only when both endpoint samples are judgeable, projections are valid, and both configured gates pass:

```math
e_{XYZ}\le\max(\tau_{abs},\tau_{rel}\max(z_q,z_h)),\qquad
e_{px}\le\tau_{px}.
```

Judgeable correspondences that fail the policy are contradicted. Unjudgeable ones remain unknown/untestable. Document how serialized `untestable` corresponds to the public term unknown.

Explain reference-depth v1 versus v2 separately. V2 uses valid non-sky semantics and inverse-depth interpolation over active bilinear neighbors, with no interpolation across an invalid or discontinuous footprint:

```math
z(u)=\left(\sum_{r\in\mathcal N(u)}\frac{w_r(u)}{z_r}\right)^{-1},\qquad
w_r\ge0,\quad\sum_r w_r=1.
```

Record the integer pixel-center convention, active-neighbor rule, sky/unmapped semantics, discontinuity policy, and assumptions. Do not suggest that v2 changed the independent pair/event policy when only feature correspondences were rescored.

**Implementation:** `evaluation/src/tasks/reference_geometry/geometry.py` and `reference_depth_v2/geometry.py` before migration.

### 5.6 Independent pair overlap and event coverage

For a fixed detector-independent sampling grid, define directional visible-overlap lower and upper bounds. Document sampling, validity, projection, occlusion/depth agreement, and uncertain samples. The current pair policy uses

```math
o_L=\min(o_{q\to h,L},o_{h\to q,L}),\qquad
o_U=\min(o_{q\to h,U},o_{h\to q,U}).
```

```math
y_{qh}=\begin{cases}
\text{loop} & o_L\ge\tau_o,\\
\text{non-loop} & o_U<\tau_o,\\
\text{unknown} & \text{otherwise}.
\end{cases}
```

Define events through the actual reference-positive query runs, temporal gap policy, and historical matches attached to each query. Unknown/negative queries do not bridge confirmed events in the current implementation. These event runs need not be independent physical revisits.

For confirmed reference events $`\mathcal E_{conf}`$,

```math
H_{conf}@k=\frac{\sum_{E\in\mathcal E_{conf}}
\mathbf1[\exists(q,h)\in E:\ h\in\mathcal C_q]}{|\mathcal E_{conf}|}.
```

Define $`(q,h)\in E`$ as one of that event's independently positive query/history pairs. Call this confirmed-event hit coverage when reference completeness is insufficient for overall recall. Report raw retrieval hits, hits with at least 20 independently supported matches, and hits reached by accepted verified constraints separately. The 20-match diagnostic is not a runtime truth filter or a SLAM acceptance criterion.

**Implementation:** `reference_geometry/geometry.py`, `loop_closure/revisits/metrics.py`, and experiment-specific event reporting.

### 5.7 Unknown-aware correspondence and pair metrics

With supported count $`S`$, contradicted count $`C`$, unknown count $`U`$, and $`N=S+C+U`$:

```math
P_{\mathrm{judged}}=\frac{S}{S+C},\qquad
\mathrm{Coverage}=\frac{S+C}{N},\qquad
P_{\mathrm{all}}\in\left[\frac{S}{N},\frac{S+U}{N}\right].
```

State that these are bounds on correctness under the reference policy, not calibrated bounds on physical truth. They are not confidence intervals. Define zero-denominator values as unavailable, and include excluded/missing-input cases outside the evaluated population explicitly. Use analogous known/false/unknown accounting for pair precision.

For ablations report correct retention $`S_{new}/S_{base}`$ and incorrect reduction $`1-C_{new}/C_{base}`$ together with coverage and event identities. Counts on different retrieved populations answer a system question; they do not isolate matcher quality.

### 5.8 Independent pose error

For estimated and reference transforms in the same direction and units:

```math
e_t=\|\hat t_{hq}-t_{hq}^{\star}\|_2,\qquad
e_R=\cos^{-1}\left(\mathrm{clip}
\left(\frac{\mathrm{tr}((R_{hq}^{\star})^\top\hat R_{hq})-1}{2},-1,1\right)\right).
```

Report metres and degrees, with explicit radian-to-degree conversion. Publish tolerances as provisional experiment policy unless calibrated. Small pose error is a different measurement from positive place overlap; a pose error alone does not establish a false place match. Conditioning diagnostics are not calibrated pose covariance.

**Implementation:** `evaluation/src/tasks/loop_closure/pose_assessment.py` and the independent assessment configuration.

### 5.9 Equation-to-code audit

Create a maintained table with columns: definition/equation, implementation, configuration keys, invariant tests, assumptions, and evaluator version. During migration, update source links while retaining historical identifiers in the result manifests. Numerical changes require a new evaluator/policy identity and a documented rescore.

## 6. Figure and image specification

Aim for five or six purposeful public figures, with detailed supplementary figures in `docs/`. The README should remain readable rather than becoming a gallery.

| Figure | Question answered | Content/source | Placement and acceptance requirement |
| --- | --- | --- | --- |
| System overview | What enters the system and what does it produce? | Actual visual retrieval, matching, optional stereo/PnP verification, and separate reference evaluation | README near top; visible separation between runtime observations and offline reference evidence |
| Geometry/convention diagram | Which way do transforms map and how are residuals measured? | Query/history/world frames, $`T_{hq}`$, rays, depths, endpoint projection | Short README method or method document; agree with tested conventions |
| Representative match examples | What does supported/contradicted/unknown evidence look like? | Saved real image pairs and original feature verdicts, including a difficult/failed case | README plus supplement; captions include run/pair identity and evaluator version |
| Matching trade-off | What is gained and what is lost by filtering? | Correct/incorrect counts or retention curves, coverage, and useful-event outcomes | README result section; fixed population and selection rules stated |
| Retrieval/event evidence | Which confirmed opportunities were reached? | Per-sequence candidate metrics or event timeline with unknown intervals | Detailed results, optionally README; distinguish confirmed-event coverage from complete recall |
| Failure and abstention profile | Why can the system or evaluator fail? | Unknown-reason distributions, ambiguity, low overlap, and depth limitations | Limitations/results; include units, counts, and exclusive vs overlapping reason categories |

### Visual rules

- Generate quantitative graphics with standard plotting tools and save publication-quality SVG/PDF plus PNG previews.
- Use editable vector diagrams for architecture and geometry. Do not use generated imagery to fabricate research evidence.
- Use consistent labels, typography, line weights, and method colors. Include symbols/text so supported/contradicted/unknown can be distinguished without color alone.
- Use honest scales and visible denominators. Distinguish counts, percentages, uncertainty intervals, and unknown bounds.
- Include meaningful alt text, numbered captions in longer documents, and relative repository links.
- Select examples with a declared rule: representative positive, representative negative, unknown-heavy case, and failure case. Do not choose only successful examples.
- Existing `.docs/figures/matching-diagnostics/*.png` are candidates for reuse, but first check their provenance, readability, caption, and redistribution terms.
- Do not draw IMU processing in the implemented architecture. A future-work figure may show it explicitly as unimplemented.

**Per-figure provenance:** figure ID, source run, pair/sequence IDs, evaluator revision, input hashes, selection rule, plotting script/configuration, command, and output hash. Commit only selected lightweight publication assets.

## 7. Final README blueprint

Target approximately **1,200–1,800 words**, excluding equations, commands, tables, and captions. This is a readability target, not a reason to omit necessary caveats. Put full derivations and exhaustive experiments in linked documents.

| Order | Section | Required content |
| --- | --- | --- |
| 1 | Title and research status | Accurate name, concise implemented scope, current release/research status |
| 2 | Overview | Problem, practical challenge, implemented solution, and contribution; about 100–150 words |
| 3 | System figure | Runtime path and separate offline reference assessment, with caption/alt text |
| 4 | Problem formulation | Causal history, candidate budget, outputs, and what constitutes independent pair truth |
| 5 | Method | Global retrieval, local assignments, optional runtime verification; compact equations and links |
| 6 | Evidence | One coherent headline table with exact protocol/evaluator/population, coverage, and limits |
| 7 | Qualitative examples | A small success/failure figure from saved evidence with a scientific caption |
| 8 | Quickstart | Supported prerequisites, installation, CPU example, expected output, external dependency note |
| 9 | Reproduce results | Saved-evidence path and full experiment recipe, commands, artifacts, expected checks |
| 10 | Repository map | Compact major-directory overview linked to detailed architecture |
| 11 | Limitations and next work | Current sensor scope, synthetic evidence, incomplete references, failed promotions, runtime/SLAM limits |
| 12 | Citation, license, acknowledgments | Verified metadata and upstream method/data references |

### Evidence selection rules

The README currently spans several distinct studies. Do not combine their best numbers into one apparent experiment.

- Use `optimized-confidence.yaml` confidence 0.3 as the documented research baseline unless a new frozen selection explicitly changes it. The original `megaloc_lightglue.yaml` is a separate configuration with different threshold/exclusion settings.
- Label confidence 0.4 as the experimental matching variant. Retain the OldTownFall result that the 20-supported-match event diagnostic falls from 13/17 to 12/17, despite fewer incorrect assignments.
- Retain the EfficientLoFTR trial as a failed promotion linked from the research record. More correct matches did not satisfy its full promotion criteria.
- Distinguish original feature-reference evaluation from depth-v2 rescores. Do not compare different evaluator versions in an unlabeled column pair.
- Annotate Factory/Desert results with their role in each experiment and later development reuse.
- Every table row needs variant/configuration, dataset/split, evaluator version, population, units, and source manifest. Put detailed provenance in a nearby linked caption or report.
- Prefer a compact table plus links over the current chronological sequence of every intermediate finding.

### README skeleton

```markdown
# LDO: [verified scope-specific subtitle]

[Concise research status and implemented sensor scope.]

## Overview
[Problem, contribution, and what the evidence supports.]

![Architecture and independent evaluation](docs/assets/diagrams/system-overview.svg)
[Scientific caption distinguishing runtime from reference evaluation.]

## Problem formulation
[Inputs, causal history, outputs, independent pair definition.]

## Method
[Compact retrieval/matching/optional verification equations.]
[Link to notation, full method, and implementation.]

## Experimental evidence
[One protocol-specific table with unknown accounting and evidence links.]
[Representative result and failure visualization.]

## Quickstart
[Commands verified on a clean supported environment; expected output.]

## Reproduce the experiments
[Saved-evidence reproduction and full native/GPU recipe.]

## Repository structure
[Small map linking code, configurations, protocols, and results.]

## Limitations and future work
[Evidence-backed scope and genuinely unimplemented work.]

## Citation and acknowledgments
[Verified author/release metadata, upstream references, and license.]
```

Headings above are a proposed README structure, not claims that those assets or commands already exist. Publish only badges backed by working automation.

## 8. Safe migration and review strategy

Use small reviewable changes in this order:

1. Baseline/scope/migration ledger and research registry.
2. Documentation organization and link repair.
3. Build configuration and initial installed smoke example.
4. Runtime packages moved to `src/` with preserved imports.
5. Evaluation namespace migration and compatibility launchers.
6. Configuration relocation and portable runtime paths.
7. Focused interface cleanup with replay parity checks.
8. Manifest/report standardization and reproducibility recipes.
9. Test classification, packaging checks, and CI.
10. Mathematical documentation and equation-to-code audit.
11. Reproducible figures and curated evidence tables.
12. Final README, metadata, and release validation.

Do not combine a file move, numerical policy change, model replacement, and README claim change in one revision. Resolve path issues first; evaluate scientific changes under a separate protocol. Retain historical datasets, manifests, source snapshots, and completed runs unchanged. Where a migration breaks an old launcher, provide a compatibility path or document the exact historical checkout needed to replay it.

## 9. Definition of completion

### Scientific integrity

- [ ] Current visual scope and optional verification are stated accurately; IMU and SLAM integration are not implied.
- [ ] Contributions distinguish original work from pretrained/upstream methods.
- [ ] All mathematical symbols, coordinate frames, depth conventions, units, and score meanings are defined.
- [ ] Runtime modules cannot consume independent reference labels through their declared interfaces.
- [ ] Feature, pair, event, verifier, and pose measurements have separate definitions and denominators.
- [ ] Unknown evidence, evaluator revisions, dataset reuse, failed trials, and event losses remain visible.
- [ ] Every public claim points to a protocol, configuration, and evidence record.

### Engineering and reproducibility

- [ ] The package installs; imports and the CPU example work outside the repository directory.
- [ ] Core tests do not require model downloads, CUDA, native SLAM builds, or private data.
- [ ] Native/GPU workflows have explicit supported environments and verified dependency/provenance instructions.
- [ ] Configuration has documented validation, path resolution, and override precedence.
- [ ] Existing commands have compatibility wrappers or documented migration instructions.
- [ ] Representative saved-evidence replay preserves expected scientific outputs through the refactor.
- [ ] Reports/figures regenerate from evidence; artifact integrity checks and immutable run completion are enforced.
- [ ] Required CI checks pass, with current platform-specific limitations recorded.

### Public presentation

- [ ] The visible directory tree communicates code, recipes, protocols, results, data manifests, and assets clearly.
- [ ] The README presents a coherent research story with concise equations, a system figure, evidence, examples, and reproducible commands.
- [ ] Figures have provenance, captions, alt text, and readable exports.
- [ ] Links, mathematical rendering, table values, and clean-environment commands have been verified.
- [ ] License, citation, authorship, and upstream attribution are accurate; unavailable metadata is not invented.

**Recommended first implementation milestone:** complete Phases 0–2 to establish the scope, evidence registry, navigable documentation, and installed CPU example. Keep the main README rewrite until the method, reproducibility path, and figures have passed their gates.
