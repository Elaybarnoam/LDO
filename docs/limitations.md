# Limitations and open research

## Implemented scope

Current LDO and component ORB + DBoW2 detectors consume camera images only. IMU
fusion is unimplemented. Optional image-only stereo/PnP verification produces
relative-pose proposals; LDO's integration into a corrective SLAM backend and
downstream trajectory improvement are not established by these experiments.
Native ORB-SLAM3 instrumentation is a separately identified benchmark.

## Evidence completeness

Unknown reference depth, semantics, overlap, and other unavailable evidence remain
unknown. Precision among judgeable assignments is conditional on that subset.
Unknown-inclusive bounds can overlap even when judged precision differs. Confirmed
event runs are not necessarily independent physical revisits, and incomplete pair
labels withhold overall recall. A 20-supported-match diagnostic is not an accepted
SLAM constraint. Zero-match pairs remain part of the pair population.

## Data and generalization

The main curated tests use synthetic TartanAir environments; early trajectories
are short. Shared simulator assets, static-world assumptions, and unaudited upstream
pretraining exposure limit claims of generalization. Factory/Desert later became
development data, and OldTownFall is now inspected. Real-world, long-term, dynamic,
seasonal, and cross-session performance require fresh protocols and evidence.

## Selection and failure

Confidence 0.4 reduces contradicted assignments but loses one useful event under
the external diagnostic. EfficientLoFTR failed promotion despite producing more
supported matches. Oracle capacities and descriptor ranks are diagnostic bounds,
not a model's recovered performance or proof of one internal failure cause.
Operational thresholds and pose tolerances remain provisional rather than
publication-calibrated operating points.

## Computation and distribution

Exact retrieval and descriptor storage grow with historical frames. Bounded local
caching does not imply bounded total memory or real-time latency. Full runtime
measurement needs explicit hardware, warmup, synchronization, cache state, and
repeat distributions. Bulk evidence and model/native environments are external;
tracked summaries support presentation reproduction, not automatic raw-run recovery.

The repository's own license is not yet specified. Upstream code, models, data,
vocabularies, and illustrative dataset images retain their own terms. Confirm
redistribution permissions before a public release.

## Next research

Investigate assignment quality and low-overlap observations using genuinely new
development/validation data and explicit per-event retention objectives. Reserve
unexamined data for the next test. Study inertial integration, calibrated pose
uncertainty, real-world transfer, and SLAM effects as separately evaluated extensions.
