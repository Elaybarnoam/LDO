# LDO descriptor versus assignment analysis

## Scope

Audit the frozen confidence-0.3 SuperPoint/LightGlue baseline before selecting a
matching change. Use only the 352 existing positive Factory/Desert development
pairs (224 fit, 128 validation). OldTownFall stays post-test explanation data.
Every pair already has provided TartanAir depth maps and reference poses.

Retrieval, model weights, keypoints, assignments and the XYZ evaluator stay fixed.
This is an offline diagnostic, not an improved model or a new loop-acceptance rule.

## Questions and falsifiable predictions

1. Descriptor ambiguity: geometrically supported alternatives rank poorly among
   the full historical descriptor set, especially in pairs below 20 supports.
2. Assignment gap: supported alternatives occupy strong reciprocal descriptor
   ranks but were not returned as supported matches by LightGlue.
3. Feature capacity: insufficient geometrically supported one-to-one capacity
   remains even before looking at descriptor ranks. Prior development diagnosis
   found sufficient capacity for all 352 selected pairs; verify that invariant.

## Input/output topology

```text
Frozen development pair manifest + baseline model provenance
    + hash-verified cached SuperPoint keypoints/descriptors
    + hash-verified diagnostic geometry edges and baseline verdicts
                       |
                       v
             L2-normalized cosine similarities
                       |
                       v
    Forward/reverse descriptor ranks across ALL detected keypoints
                       |
                       v
   Supported-edge capacity at top-1 / top-5 / top-10 / top-50 ranks
        + missed-supported-query and actual-assignment diagnostics
                       |
                       v
         Per-pair NPZ + machine-readable aggregate JSON
                       |
                       v
       Existing FIFO evaluation handler -> dated JSON and Markdown
```

## Mathematical conventions

For query descriptor i and historical descriptor j:

`S_ij = (d_i / ||d_i||) dot (e_j / ||e_j||)`.

Rank every supported edge against all competing descriptors, including features
with unknown reference evidence. Use the conservative rank: all similarities
within 1e-7 of the selected score occupy the same worst tied rank. Report both
forward-only and reciprocal rank restrictions. Reciprocal top-k means the SAME
edge ranks at most k in both directions; do not combine different edges' ranks.

Build a bipartite graph from supported edges satisfying each rank restriction.
Maximum matching measures one-to-one geometric capacity; points cannot be reused.
The 20-match boundary is the unchanged diagnostic, not native SLAM acceptance.

Count queries with a supported alternative but no supported baseline assignment.
Report how many have forward top-1/5/10 alternatives. Also count contradicted
assignments whose query has a higher-cosine supported alternative. Keep reference
unknowns distinct from contradictions.

## Integrity and interpretation

- Verify frozen source inputs, original baseline evidence, feature manifests,
  descriptors, keypoint alignment and the saved geometry-edge hashes.
- Freeze this task's source/configuration and input hashes in a separate output
  root. Resumption rejects changed inputs; no original artifact is overwritten.
- Keep per-scene and fit/validation summaries separate; validation here is
  diagnostic evidence, not a fresh test of a future design.
- Raw descriptor ranks do not describe LightGlue's contextual internal scores.
- A reference-compatible edge is not proof of a unique visible feature identity.
- This positive-pair sample cannot measure overall false-loop rates or justify
  promoting a matcher without complete replay and fresh environment testing.

## Next decision

Use the rank/capacity results to choose one targeted matching experiment. High
rank capacity motivates examining contextual matching/rejection. Low rank
capacity motivates stronger descriptors or an image-pair-conditioned engine.
Mixed results should remain mixed rather than assigning all blame to one module.

Future promotion still requires fewer incorrect matches, adequate correct-match
retention, preservation of every baseline usable event and unchanged external
reference checks, followed by a frozen fresh-environment test.
