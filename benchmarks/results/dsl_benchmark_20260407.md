# Bricks DSL Benchmark — v0.4.52

_Generated: 2026-04-07 20:31 UTC_

| Task | DSL Valid | Steps | Bricks Correct | For-Each | Branch | Tokens | Time(s) |
|------|:---------:|-------|:--------------:|:--------:|:------:|-------:|--------:|
| simple_3_step | PASS | 3/3 PASS | PASS | n/a | n/a | 300 | 0.01 |
| filter_aggregate | PASS | 2/2 PASS | PASS | n/a | n/a | 300 | 0.00 |
| for_each_pipeline | PASS | 2 | PASS | PASS | n/a | 300 | 0.00 |
| conditional_routing | PASS | 1 | PASS | n/a | PASS | 300 | 0.00 |
| complex_10_step | PASS | 10 PASS | PASS | n/a | n/a | 300 | 0.02 |

**Result: 5/5 tasks valid**

## Notes
- Benchmark uses mock LLM responses (no real API calls).
- Token counts reflect mock response sizes.
- Step counts measured from `FlowDefinition.to_blueprint()` output.
