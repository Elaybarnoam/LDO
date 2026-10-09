# Evaluation task separation

The code is organized into `evaluation/src/tasks/feature_matching/` and `evaluation/src/tasks/loop_closure/`.

The first contains the existing `xyz/` checker and `viewer/`. The second contains the loop-reference/comparison workflow and its dedicated `config.yaml`. Shared process supervision, publishing, report writing and benchmark adapters remain outside the task packages.

See `evaluation/src/tasks/README.md` for the full tree. This change separates responsibilities and preserves evaluation behavior. It does not add the proposed operational loop verifier. Historical evidence directories and archived source snapshots are preserved, and the numerical XYZ implementation and policy keep their original hashes.
