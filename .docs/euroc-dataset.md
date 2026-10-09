# EuRoC MAV dataset installation

EuRoC MAV is an established visual–inertial benchmark published in 2016. It contains stereo monochrome camera images at 20 Hz, IMU measurements at 200 Hz, sensor calibration, and motion ground truth. It is a dataset for testing SLAM implementations; loop-event labels still need to be defined for our detector evaluation.

Official sources:

- [ETH ASL dataset description](https://projects.asl.ethz.ch/datasets/euroc-mav/)
- [ETH Research Collection dataset](https://doi.org/10.3929/ethz-b-000690084)

The ETH Research Collection returned HTTP 429 during setup. The installer therefore uses the public [GlowBond mirror](https://huggingface.co/datasets/GlowBond/EuRoC_MAV_Dataset), pinned to revision `29d08aeb1c8d9dc5c30497cc538d9cc61f872bb7`. This is a third-party mirror, not an ETH-hosted download. Publisher-listed rights: In Copyright – Non-Commercial Use Permitted.

## Location and format

```text
evaluation/datasets/euroc/
  manifest.json
  _archives/                  # Original ASL sequence ZIPs and source/hash metadata
  MH_01_easy/mav0/
  MH_02_easy/mav0/
  MH_03_medium/mav0/
  MH_04_difficult/mav0/
  MH_05_difficult/mav0/
  V1_01_easy/mav0/
  V1_02_medium/mav0/
  V1_03_difficult/mav0/
  V2_01_easy/mav0/
  V2_02_medium/mav0/
  V2_03_difficult/mav0/
```

Each sequence preserves the ASL structure, including `cam0`, `cam1`, `imu0`, and `state_groundtruth_estimate0`. Camera directories contain PNGs, timestamp indexes, and calibration. Timestamps remain in integer nanoseconds. Additional ground-truth streams supplied by the dataset remain intact.

The installation selects ASL sequence ZIPs from the three environment archives. Duplicated ROS bags and separate calibration-recording archives are omitted; the calibration metadata inside each sequence is retained. The compressed sequence payloads total approximately 10.74 GB, with additional space required for extraction.

## Reproduce or resume installation

From the project root:

```powershell
uv run python evaluation/src/install_euroc.py
```

The installer retains partial downloads for retry, verifies their byte counts and outer ZIP entry CRC32, and records the SHA256 of each recovered ASL ZIP. Extracting the inner ZIP verifies the CRC32 of each extracted file. These checks establish download integrity against the pinned mirror archive; they do not establish equality with an independently supplied publisher checksum.

After extraction, the installer checks that every indexed image exists, synchronized stereo frames are available, stream timestamps increase, IMU and ground-truth streams are present, and sensor metadata exists. It records matched stereo pairs and any unpaired frames without changing the original data. For example, the original `V1_02_medium` has an extra final right-camera frame. It decodes the first, middle, and last frame from each camera to check the expected 752 × 480 image shape.

`manifest.json` records the current installation status, downloaded sequence hashes, stream counts, and durations. A status of `complete` means all eleven sequences passed installation checks. Each sequence also has an `installation.json` report. The dataset folder is excluded from Git.

## Evaluation status

The development/test split is still unassigned. Installation does not establish that EuRoC is outside a pretrained model's training distribution. Process supervision and event reporting are implemented, but the configured benchmark list remains empty until native adapters are installed.

Known evaluation considerations include independently controlled camera exposure and limitations in ground-truth synchronization documented by ETH. OpenVINS also documents an orientation issue in the original `V1_01_easy` ground truth and an alternative estimate: [OpenVINS dataset documentation](https://github.com/rpng/open_vins/blob/master/docs/gs-datasets.dox). Preserve the original data and decide which ground-truth policy to use before comparing algorithms.
