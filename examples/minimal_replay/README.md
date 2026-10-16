# CPU causal replay example

```bash
uv run ldo-research smoke --output artifacts/smoke.json
```

Four synthetic frames arrive one second apart. With a two-second exclusion,
queries `0` and `1` have no eligible history, query `2` returns `0`, and query
`3` returns `0`, `1` in stable timestamp order. Each candidate has two synthetic
identity assignments. The output marks `research_result: false`.

This runs the production `Detector` through deterministic synthetic adapters.
It verifies installation and illustrates causal semantics. It does not evaluate
MegaLoc, SuperPoint, LightGlue, geometric correctness, or loop-detection accuracy.

See the [method](../../docs/method.md) and [installation guide](../../docs/installation.md).
