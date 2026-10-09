"""Entry point for the OpenCV candidate review and XYZ evidence flow."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from tasks.feature_matching.viewer.viewer import main


if __name__ == "__main__":
    raise SystemExit(main())
