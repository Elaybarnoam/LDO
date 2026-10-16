# Installation and execution profiles

## CPU development and demonstration

Use Python 3.11 and `uv` from the repository root:

```bash
uv sync --locked
uv run ldo-research doctor
uv run ldo-research smoke --output artifacts/smoke.json
uv run python -m pytest -q
```

The smoke command runs the actual causal detector with synthetic adapters; it
does not download models or measure learned-model accuracy. Expected eligible
history counts are `[0, 0, 1, 2]`, and the last query returns `0`, `1`.

`uv sync` includes development dependencies. Exact editable mapping avoids
Python 3.11 Windows path-decoding problems in Unicode checkout names. Wheels do
not need the editable import machinery. To build distributable artifacts:

```bash
uv build
```

The distribution retains the compatibility name `visual-imu-loop-detector`;
the implemented public scope is visual. The installed command is `ldo-research`.

## Figures and saved-result presentation

```bash
uv sync --locked --extra visualization
uv run python scripts/reproduce/publish.py --output artifacts/reproduced-results --figures artifacts/reproduced-figures
uv run python scripts/figures/render_diagrams.py --output artifacts/reproduced-diagrams
```

These regenerate presentation from tracked historical summaries. They do not
rerun inference, reconstruct missing raw evidence, or repeat reference evaluation.
See [reproducibility](reproducibility.md).

## Windows review and launch

The normal Windows environment supports CPU tests, metadata/report work, and
OpenCV review. Existing launchers remain available after installation:

```powershell
uv run python evaluation/view_suspicious.py --help
uv run python evaluation/reference_geometry.py --help
uv run python evaluation/compare.py --help
```

Reference/comparison launchers forward actual execution to WSL as before; help
and supported review commands stay local. Configure `LDO_WSL_DISTRO` and
`LDO_WSL_PYTHON` when the defaults differ from your installation. Export variables
in the relevant shell; `.env.example` is documentation and is not automatically loaded.

## WSL native/CUDA experiments

The existing full experiments were run in Ubuntu-24.04 with separately installed
model environments, CUDA, native ORB dependencies, stereo inference, and datasets.
Python locking alone does not install these external assets.

Inside WSL, create a runtime profile before installing models/data:

```bash
uv sync --locked --extra ldo
uv run ldo-research configure --runtime-root /home/you/ldo-runtime --output artifacts/local-configs
export LDO_CONFIG_ROOT="$PWD/artifacts/local-configs"
export LDO_MODEL_ROOT=/home/you/ldo-runtime/ldo-models
uv run python -m ldo.install --root "$LDO_MODEL_ROOT"
uv run ldo-research reference --help
```

Replace `/home/you/ldo-runtime` with a real absolute Linux directory. The generator
copies numerical values, replaces `/opt/loop-detector` runtime prefixes, and
resolves inter-recipe references to the new profile. It refuses an existing output
directory. Profiles are new configuration provenance and do not modify defaults.
Generate inside WSL for WSL execution so the generated paths are Linux paths.

Install the pinned native ORB source/build and stereo runtime separately using
the [native build guide](../src/loop_eval/benchmarks/orb_slam3/setup/README.md),
[component benchmark guide](../src/loop_eval/benchmarks/orb_dbow2/README.md), and
[stereo installer](../src/loop_eval/tasks/feature_matching/xyz/install_fast_stereo.py).
Use a new native build location after migration: historical manifests can name
old source paths and must not be patched in place. Check CUDA with `nvidia-smi`
and the selected model environment; `doctor` reports package/executable presence
without importing model libraries or claiming GPU readiness.

`ldo-research doctor --model-root /path/to/models` explicitly verifies installed
artifact hashes. `doctor --probe-cuda` queries driver/device visibility with
`nvidia-smi`; it does not certify PyTorch/model-runtime compatibility.

## Configuration precedence

1. Explicit command `--config` selects that file where the task exposes the option.
2. Default recipe lookup uses `LDO_CONFIG_ROOT` if set; missing files there fail.
3. Otherwise defaults come from the detected checkout or bundled wheel resources.
4. `LDO_PROJECT_ROOT` explicitly selects a checkout and is validated.
5. `LDO_MODEL_ROOT` overrides the LDO detector's configured model root.

Detector-relative optional paths resolve against its YAML directory. Historical
evaluation recipes contain checkout-relative cross-references; materialized
profiles resolve them explicitly. A model-root override does not override the
independent stereo runtime or native build locations.
