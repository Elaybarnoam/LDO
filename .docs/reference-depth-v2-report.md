# TartanAir reference-depth evaluator v2

Same saved ORB and LDO correspondences, new independent evaluator. No detector inference or matching was rerun. Original results are preserved. Candidate labels and event-hit counts are unchanged.

Valid positive finite non-sky depths have no metric distance cutoff. Sky is excluded using official semantic masks. Inverse depth is interpolated within the active subpixel footprint only; mixed-depth footprints remain unknown. XYZ and symmetric reprojection tolerances are unchanged.

## Feature results before and after

| Environment | Detector | Evaluator | Correct | Incorrect | Unknown | Judgeable coverage | Correct among judgeable |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| AbandonedFactory2 | orb | old | 5974 | 17214 | 25985 | 47.2% | 25.8% |
| AbandonedFactory2 | orb | new | 6413 | 18878 | 23882 | 51.4% | 25.4% |
| AbandonedFactory2 | ldo | old | 154417 | 224291 | 396982 | 48.8% | 40.8% |
| AbandonedFactory2 | ldo | new | 249339 | 419831 | 106520 | 86.3% | 37.3% |
| DesertGasStation | orb | old | 1715 | 5119 | 80672 | 7.8% | 25.1% |
| DesertGasStation | orb | new | 2375 | 8399 | 76732 | 12.3% | 22.0% |
| DesertGasStation | ldo | old | 19236 | 37946 | 259113 | 18.1% | 33.6% |
| DesertGasStation | ldo | new | 34201 | 109167 | 172927 | 45.3% | 23.9% |
| Combined | orb | old | 7689 | 22333 | 106657 | 22.0% | 25.6% |
| Combined | orb | new | 8788 | 27277 | 100614 | 26.4% | 24.4% |
| Combined | ldo | old | 173653 | 262237 | 656095 | 39.9% | 39.8% |
| Combined | ldo | new | 283540 | 528998 | 279447 | 74.4% | 34.9% |

## Verdict transitions

| Environment | Detector | Transition | Matches |
| --- | --- | --- | ---: |
| AbandonedFactory2 | orb | contradicted->contradicted | 16767 |
| AbandonedFactory2 | orb | contradicted->supported | 447 |
| AbandonedFactory2 | orb | supported->contradicted | 244 |
| AbandonedFactory2 | orb | supported->supported | 5730 |
| AbandonedFactory2 | orb | untestable->contradicted | 1867 |
| AbandonedFactory2 | orb | untestable->supported | 236 |
| AbandonedFactory2 | orb | untestable->untestable | 23882 |
| AbandonedFactory2 | ldo | contradicted->contradicted | 224290 |
| AbandonedFactory2 | ldo | contradicted->untestable | 1 |
| AbandonedFactory2 | ldo | supported->supported | 154417 |
| AbandonedFactory2 | ldo | untestable->contradicted | 195541 |
| AbandonedFactory2 | ldo | untestable->supported | 94922 |
| AbandonedFactory2 | ldo | untestable->untestable | 106519 |
| DesertGasStation | orb | contradicted->contradicted | 4966 |
| DesertGasStation | orb | contradicted->supported | 153 |
| DesertGasStation | orb | supported->contradicted | 95 |
| DesertGasStation | orb | supported->supported | 1620 |
| DesertGasStation | orb | untestable->contradicted | 3338 |
| DesertGasStation | orb | untestable->supported | 602 |
| DesertGasStation | orb | untestable->untestable | 76732 |
| DesertGasStation | ldo | contradicted->contradicted | 37946 |
| DesertGasStation | ldo | supported->supported | 19236 |
| DesertGasStation | ldo | untestable->contradicted | 71221 |
| DesertGasStation | ldo | untestable->supported | 14965 |
| DesertGasStation | ldo | untestable->untestable | 172927 |
| Combined | orb | contradicted->contradicted | 21733 |
| Combined | orb | contradicted->supported | 600 |
| Combined | orb | supported->contradicted | 339 |
| Combined | orb | supported->supported | 7350 |
| Combined | orb | untestable->contradicted | 5205 |
| Combined | orb | untestable->supported | 838 |
| Combined | orb | untestable->untestable | 100614 |
| Combined | ldo | contradicted->contradicted | 262236 |
| Combined | ldo | contradicted->untestable | 1 |
| Combined | ldo | supported->supported | 173653 |
| Combined | ldo | untestable->contradicted | 266762 |
| Combined | ldo | untestable->supported | 109887 |
| Combined | ldo | untestable->untestable | 279446 |

## Remaining unknown evidence

One primary reason per match, with invalid pixels/depth, sky and unmapped semantics taking precedence over boundary ambiguity.

| Environment | Detector | Reason | Matches |
| --- | --- | --- | ---: |
| AbandonedFactory2 | orb | ambiguous_depth_boundary | 794 |
| AbandonedFactory2 | orb | sky | 23088 |
| AbandonedFactory2 | ldo | sky | 106520 |
| DesertGasStation | orb | ambiguous_depth_boundary | 2245 |
| DesertGasStation | orb | sky | 74487 |
| DesertGasStation | ldo | sky | 172927 |
| Combined | orb | ambiguous_depth_boundary | 3039 |
| Combined | orb | sky | 97575 |
| Combined | ldo | sky | 279447 |

## Distance breakdown

Distance is the maximum sampled axial depth at the two endpoints. Unusable endpoints appear in unknown_depth.

| Environment | Detector | Distance | Correct | Incorrect | Unknown |
| --- | --- | --- | ---: | ---: | ---: |
| AbandonedFactory2 | orb | 0_to_50_m | 6413 | 18878 | 0 |
| AbandonedFactory2 | orb | 50_to_200_m | 0 | 0 | 0 |
| AbandonedFactory2 | orb | over_200_m | 0 | 0 | 0 |
| AbandonedFactory2 | orb | unknown_depth | 0 | 0 | 23882 |
| AbandonedFactory2 | ldo | 0_to_50_m | 249339 | 419831 | 0 |
| AbandonedFactory2 | ldo | 50_to_200_m | 0 | 0 | 0 |
| AbandonedFactory2 | ldo | over_200_m | 0 | 0 | 0 |
| AbandonedFactory2 | ldo | unknown_depth | 0 | 0 | 106520 |
| DesertGasStation | orb | 0_to_50_m | 2071 | 7118 | 0 |
| DesertGasStation | orb | 50_to_200_m | 277 | 741 | 0 |
| DesertGasStation | orb | over_200_m | 27 | 540 | 0 |
| DesertGasStation | orb | unknown_depth | 0 | 0 | 76732 |
| DesertGasStation | ldo | 0_to_50_m | 26213 | 70614 | 0 |
| DesertGasStation | ldo | 50_to_200_m | 7421 | 18389 | 0 |
| DesertGasStation | ldo | over_200_m | 567 | 20164 | 0 |
| DesertGasStation | ldo | unknown_depth | 0 | 0 | 172927 |
| Combined | orb | 0_to_50_m | 8484 | 25996 | 0 |
| Combined | orb | 50_to_200_m | 277 | 741 | 0 |
| Combined | orb | over_200_m | 27 | 540 | 0 |
| Combined | orb | unknown_depth | 0 | 0 | 100614 |
| Combined | ldo | 0_to_50_m | 275552 | 490445 | 0 |
| Combined | ldo | 50_to_200_m | 7421 | 18389 | 0 |
| Combined | ldo | over_200_m | 567 | 20164 | 0 |
| Combined | ldo | unknown_depth | 0 | 0 | 279447 |

## Interpretation

- This evaluator revision follows inspection of these test results; it is not fresh held-out evidence or model optimization.
- More judged matches can be correct or incorrect. Sampling changes can revise earlier known verdicts; inspect the transition table.
- Semantic labels identify sky, not trustworthy depth on every other object. Reflective, transparent, rendered background and boundary surfaces can still limit physical interpretation.
- The unchanged tolerances are operational criteria, not calibrated uncertainty probabilities. Controlled cases test implementation behavior; they do not prove every real correspondence label.
- Unknowns are not false positives. Feature precision is conditional on judgeable evidence, not accepted loop-closure accuracy.
- Image-pair overlap labels were not recomputed, so the original candidate/event results remain under the original depth policy.
- Original EuRoC XYZ and frozen TartanAir evaluators remain unchanged.

## Provenance

Source results SHA256: `f4042982a4bf147ffb2c0fa41653186b770ab6a2538b4dc30f6df887c8785841`

Configuration SHA256: `06c984f865a729efa478d99f02bd7a366c5afb0e13b2c1712697d14f85c71e5d`

Per-feature compressed evidence, semantic-mask hashes and code snapshots are recorded in the accompanying JSON report.
