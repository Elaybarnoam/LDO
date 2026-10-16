# Python environment

The project uses uv, Python 3.11, and a local `.venv`. `pyproject.toml` declares dependencies; `uv.lock` records the resolved versions and should be committed with the project.

uv uses copy mode for package installation because the project is located in OneDrive, which can reject hardlinks.

Run commands from the project root:

```powershell
uv sync
uv run python evaluation/src/runner.py
```

The runner invokes the orchestrator. Configure benchmark adapter commands in `evaluation/src/config.yaml` before running it. The default list is empty, so it produces a configuration error rather than a misleading empty evaluation. See [evaluation IPC](evaluation-ipc.md) for adapter requirements.

Select `.venv\Scripts\python.exe` as the Python interpreter in the IDE. Activation is optional when using `uv run`.

The base dependencies provide numerical computation (NumPy/SciPy), image processing (OpenCV without GUI dependencies), YAML configuration, and result tables (pandas).

Python 3.11 is the initial compatibility choice for the research stack. Confirm each chosen model's requirements before integrating it. Add PyTorch and model-specific dependencies when the model and CPU/CUDA configuration are selected. The current environment is for evaluation tooling; neural inference dependencies and native SLAM build environments are still pending.

Downloaded datasets, evaluation output, and the local environment are excluded from Git. The uv lock file is retained.
