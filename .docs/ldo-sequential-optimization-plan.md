# Sequential LDO optimization experiment

Frozen before new-environment model evaluation, 2026-10-09.

## Split and claim
- RetroOffice/Data_easy: training only; all source trajectories, selected from official archive sizes before looking at model outcomes.
- ArchVizTinyHouseDay/Data_easy: development only, since every trajectory has already been examined. P000-P004 fit/sweep; P005-P006 validate policy and select matcher checkpoint. Repeated development use is disclosed.
- CountryHouse/Data_easy: held-out environment; all source trajectories. Evaluate planned variants after their configurations/checkpoints are frozen. No test-driven parameter changes. Upstream pretrained training overlap is unaudited; this is adaptation split separation, not proof of zero upstream exposure.
- Same reference depth/pose gates, 2 Hz sampling, 5-second exclusion, K=5. New reference-only adapters need cam0 and reference depth/poses; no stereo/operational verifier enters any measurement.

## Step 1: match confidence
Sweep LightGlue confidence thresholds [0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9] on development P000-P004. Minimize contradicted reported matches subject to retaining >=90% of baseline reference-supported matches. Freeze the threshold, measure P005-P006 separately, and later the held-out environment. Unknown matches remain separate. This tests confidence filtering, not training. Saved scores allow exact post-filtering above the original 0.1 threshold.

## Step 2: candidate confidence
Fit a small regularized logistic score using only P000-P004 known candidate labels and image-derived retrieval/matching evidence. Unknown labels are excluded, not negative. Select its acceptance cutoff using P005-P006, minimizing false known candidate returns while retaining >=90% of known true candidate returns and >=90% of baseline confirmed event hits. The runtime policy can return no candidate. It never consumes ground truth and does not use pose estimation or RANSAC. Raw candidates are retained for offline audit. Compare with the confidence-only version, including correct detections lost and unknown coverage.

## Step 3: real matcher-head fine-tuning
Freeze MegaLoc, SuperPoint and LightGlue transformer layers; adapt the final assignment head on RetroOffice reference-supervised correspondences. This is deliberately a small adaptation pilot, not full official LightGlue training. Train 300 AdamW updates at learning rate 1e-4, seed 0, deterministic cached-feature cap 256. Use symmetric reference geometry, one-to-one supervision, a 3 px positive and 5 px negative ambiguity margin, dustbin unmatched labels, and ignore invalid/ambiguous depth. Supervise all possible feature assignments rather than only the pretrained model's predicted matches.

Evaluate checkpoints 0,50,100,200,300 on P005-P006 using the normal 1024-feature observations. Keep early exit and pruning disabled to reach the adapted head. Include a pretrained full-depth control to separate a compute/configuration effect from learning. Select using development results only; require >=90% supported-match retention and minimize contradicted matches. Keep step 0 if learning does not improve the development criterion. Save full state dict, input/source hashes, loss/gradient diagnostics and strict reload parity. Do not overwrite pretrained weights.

## Step 4: held-out validation

Before held-out inference, the promotion check was made explicit: a trained checkpoint must have strictly fewer contradicted matches than both the previous deployed variant and the equal-compute pretrained control, retaining >=90% of correct matches. Equal errors with fewer correct matches do not qualify. If training fails this check, the existing confidence+policy variant remains selected; the trained checkpoint is still tested as a disclosed experimental variant.

Implementation detail: training uses 24 geometry-supervised frame pairs per RetroOffice trajectory (144 total), including adjacent views and widely separated views. Feature assignments are derived from all selected observations, independently of pretrained reported matches. This pilot does not implement appearance-mined hard-negative training or full transformer fine-tuning. CountryHouse additionally downloads real cam1 images because the pinned native ORB exporter requires them; cam1 is not a detector/scorer input for these direct measurements.
Freeze all planned variants, then run identical CountryHouse inputs for ORB, baseline LDO, confidence-only, confidence+candidate-policy, pretrained full-depth control, and the adapted-head configuration. Report each step against its predecessor and baseline. Improvement is measured, never assumed. Retained good matches, bad matches removed, candidate TP/FP/unknown, confirmed-event hits and unknown bounds are separate metrics. A higher judged precision obtained by discarding many good matches is not unqualified improvement. No accepted-pose statistics are part of this experiment.

If a step fails, report it and retain the safer development-selected predecessor as the recommended configuration. A final superiority claim still requires additional real sequences, independent environments and compute measurements.
