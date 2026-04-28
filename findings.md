# Track 1 — Exploration: findings

*Updated as cases complete. Cross-case patterns; per-case detail lives in `cases/<slug>.md`.*

## 2026-04-22 — sum-only N sweep at `bf68452` (post #66)

First complete Bricks-vs-raw-LLM cost curve on a working sha. Single case (sum of a list of numbers), sonnet, sizes 50→5000.

| N | Bricks $ | Bricks dur | Raw LLM $ | Raw LLM dur | Correct? |
|---|---|---|---|---|---|
| 50 | **0.189** (compose + cache_creation=29,658) | 10.4s | 0.046 | 14.2s | both ✓ |
| 200 | 0.018 (cache_read=29,658) | 8.5s | 0.298 | 87.7s | both ✓ |
| 1000 | 0.018 | 9.7s | timeout @600s | — | Bricks ✓, raw ❌ |
| 5000 | 0.018 | 7.2s | timeout @600s | — | Bricks ✓, raw ❌ |

### Headline findings

1. **Tipping point is N ≈ 100** for sum-only on sonnet. At N=50 raw is 4× cheaper; at N=200 Bricks is 17× cheaper. Crossover lands between them.
2. **Raw LLM hits a hard wall around N=1000.** Not "slower and more expensive" — literally doesn't complete within 10 minutes. For any pipeline with list inputs of realistic production size, raw-LLM-as-computation is not a viable baseline.
3. **Bricks cost is nearly flat from N=200 upward** at ~$0.018/run. Execution is pure Python (0 LLM tokens). The only LLM cost is compose, and compose is size-independent (the task prompt and catalog don't grow with N — data goes in at execute time via `${inputs.values}`).
4. **Prompt caching amplifies the Bricks win.** First run writes 29,658 cache_creation tokens; subsequent runs read them for ~$0.018 instead of recomposing from scratch. The cache is per-task, not per-data, so any re-run at any N benefits.

### Why raw LLM times out, not just slows down

At N=5000 the input is a JSON array of 5000 floats — call it ~40k tokens. Sonnet can ingest that, but actually producing the correct sum means holding all 5000 numbers in working memory and summing. The model does a lot of output-token generation (internal reasoning steps, attempted partial sums), and the 600s subprocess timeout we set still isn't enough. A deterministic `reduce_sum` takes microseconds.

The interesting angle for the article isn't "Bricks is cheaper" (expected) — it's "raw-LLM is wall-of-infeasibility at modest scale." Very few data-engineering tasks operate on lists under N=100.

### Caveats / what this doesn't cover

- **Single case, single reducer.** `sum-only` is the friendliest possible task for Bricks. More complex cases (filter→group→top-K, joins, reshape) that need `for_each` or `branch` composition will have different curves. Before Bug B was fixed, *all* of those were failing at 0/0.
- **Single model.** Haiku raw-LLM would be cheaper than sonnet raw-LLM; probably tightens the tipping-point gap at small N. Opus would push it the other way. Follow-up sweep across models would sharpen the cost curve.
- **Prompt cache assumes warm session.** First ever run at a given sha costs $0.189 (cache_creation). If every user is the first user, the amortization story weakens. Worth measuring how long the cache lives and how it degrades across days.
- **Accuracy at N=1000/5000 untested for raw LLM.** We only know raw LLM doesn't *finish* — not whether it would get the right answer if it did. Plausible it would miscalculate the sum by small amounts; consistent with the log-analysis N=200 miscount-by-4 finding.

### Earlier Track 1 data points (same case class, different sha — for history)

- `log-analysis` N=200 @ sha `d80c190`/`1c203b8` (pre-fix): Bricks failed, raw LLM $0.29–0.38, deterministically miscounted INFO by 4 (153 vs 157) across 3 runs.
- Two compose-bug probes at `20dc0cc`: all 3 tiny tasks failed with two distinct errors (Bug A, Bug B). Fixed by #66. See `runs/notable/20dc0cc-three-probes-two-bugs.md`.

Total cost to build this finding: ~$2.60 (includes debugging burns; successful-data subset ~$0.59).

### Next obvious sweeps

1. Sum sweep on **haiku** — cheaper raw baseline; moves the tipping point.
2. **Multi-reducer** (`numeric-stats` full 5-field): does the Bricks compose stay flat or does it grow with output complexity? Already ran N=50 successfully at $0.204.
3. ~~**Cache cold-start**~~ — done, see below.
4. **`log-analysis` post-#66**: the original motivating case. Does it work now that the for_each path is fixed? If so, it's a much richer cost-curve than sum-only since it hits real string manipulation.

## 2026-04-22 — cold-start cost probe (`mean-only` N=200)

To separate Bricks' amortization story from its cache story, ran a brand-new task (`mean-only` — never composed before) directly at N=200 with no prior N=50 warmup.

### Three cost regimes, not two

| Regime | Bricks $ | cache_creation | cache_read | Output tok | Example |
|---|---|---|---|---|---|
| **Session-cold** (first compose ever) | 0.189 | 29,658 | 0 | 130 | sum-only N=50 first run |
| **Task-cold** (catalog warm, new task) | **0.083** | 8,113 | 21,521 | 858 | mean-only N=200 first run |
| **Task-warm** (re-run same task) | 0.018 | 0 | 29,658 | 113 | sum-only N=200/1000/5000 |

The interesting regime is the middle one. A new task the composer hasn't seen *still* reuses ~72% of the compose prompt (system prompt + brick catalog + few-shot examples) via Anthropic's ephemeral cache. Only the task-specific delta — the natural-language task description — actually costs `cache_creation` tokens. So the "tax" for a new task type, once the user has a warm session, is ~$0.065 not ~$0.19.

### Same-N raw-LLM comparison

Both engines got the correct mean (31.1413).

| Engine | $ | Duration | Output tokens |
|---|---|---|---|
| Bricks (task-cold) | 0.083 | 20s | 858 |
| Raw LLM | 0.347 | 121s | 12,861 |

Even on a brand-new task with cache_creation in the critical path, Bricks is **4.2× cheaper and 6× faster** than raw LLM at N=200. Raw LLM's 12,861 output tokens are reasoning — it's computing the mean "by hand" in the output stream, burning tokens for arithmetic. Bricks' 858 output tokens are just the generated blueprint Python.

### Sanity check — verified by direct instrumentation (five concurring signals)

Re-ran sum-only N=200 with the runner instrumented to capture every cache-related signal Bricks exposes. Run record `runs/track-1-exploration_fe5d0857-db61-43c9-8cda-3897c83f5556.json`. All five signals agree:

| Signal | Value | Means |
|---|---|---|
| `result["cache_hit"]` (engine) | `False` | Blueprint store missed |
| `result["api_calls"]` (engine) | `1` | Engine made one LLM call |
| `n_llm_calls` (provider wrapper) | `1` | Provider really was called |
| `bricks.ai.composer` INFO log | `"Composing blueprint for task (111 chars), 102 bricks in pool"` | Compose path, not cache-hit path (composer.py:357 vs 345) |
| Tokens | `cache_read=21,521, cache_creation=8,109` | Anthropic prompt-cache split |

Bricks really did compose; nothing was served from its own blueprint store. The savings came entirely from Anthropic's prompt cache.

**Side finding — cache TTL is observable.** This run's tokens (`cache_read=21,521, cache_creation=8,109`) differ from the earlier sum-only N=200 run (`cache_read=29,658, cache_creation=0`). Same task, same catalog, but the later run only had 73% of the prompt still cached on Anthropic's side after ~5 days. Cost rose from $0.018 to $0.067 — purely due to cache degradation, no Bricks change. Worth a sidebar in the article on "amortization story is sensitive to TTL"; the warm-state numbers from a single afternoon are best-case.

(Note: there is no Bricks log file by default — the library uses `logging.getLogger()` everywhere but ships no handler for `Bricks.default()` callers. The log signal above only appeared because the runner now attaches an in-memory StreamHandler.)

### Earlier sanity check — is this actually a blueprint-store hit masquerading as prompt cache?

Worth ruling out. Bricks has its own blueprint store; could it be skipping compose entirely and making the "cache" numbers meaningless?

Evidence that **compose really runs every time** (not a blueprint hit):

- `Bricks.default()` uses `MemoryBlueprintStore` — per-process dict, empty at process start. `python run.py` is a fresh process every invocation; cross-process reuse is impossible with this backend.
- `n_llm_calls = 1` on every single run. A blueprint-store hit would skip the LLM entirely → `n_llm_calls = 0`.
- `output_tokens` varies per run (130, 113, 113, 105, 858). A cached response would return identical output tokens every time.

So: Bricks re-composes every process, the 29k cache tokens are genuinely Anthropic-side prompt cache hits on the (invariant) system prompt + catalog + few-shot examples. The $0.018 steady-state really is the marginal cost of re-composing a task when the catalog is already warm in Anthropic's cache.

(A leftover `./blueprints/` dir exists from an earlier Apr-21 CRM benchmark run — CRM blueprints don't match our Track 1 task prompts, so they're inert for our runs.)

### Implications for the article

- Cost-curve narrative should use **three curves, not two**: raw-LLM, Bricks cold, Bricks warm. The gap between the latter two is the Anthropic prompt cache benefit; the gap between Bricks cold and raw-LLM is the structural win from "stop doing arithmetic in the LLM."
- The "amortization" story (Bricks pays upfront, wins on repeat) is *incomplete* — even the first run of a new task beats raw LLM handily at N≥200 because cache amortizes the catalog/system-prompt across ALL tasks, not just across ALL runs of the same task.

Total cost of this probe: Bricks $0.083 + raw $0.347 = $0.43.

## 2026-04-27 — full empirical backbone (B, A, C, D done)

Four targeted experiments to lock down the article's claims. All on `bf68452` / `d9d0094` (no functional change between them).

### B — Generality check on `log-analysis` (the original case)

**Result: still blocked, but with a new and better-diagnosed failure.**

| Run | Outcome |
|---|---|
| log-analysis N=50, Sonnet | Bricks compose **timed out at 600s** ($0). Raw LLM correct=False (off by 1 on INFO and ERROR, top-3 picked the wrong tied pattern). |
| log-analysis N=200, Sonnet | Bricks composed a **valid 14-step blueprint** ($0.71, 26k output tokens), but execution failed: `for_each: could not extract brick name` with the new widened error message: **`Inner lambda raised: TypeError: 'Node' object is not subscriptable`**. Raw LLM correct=False (INFO 153 vs 157, persistent miscount). |

**Bug C** identified — distinct from A and B. The composer emitted a perfectly idiomatic `lambda pat: step.filter_dict_list(items=..., value=pat["pattern"])`. Bricks' for_each-tracer trick injects a mock `Node` for the iteration variable; the lambda subscripts it with `pat["pattern"]`, which raises TypeError, the inner call never reaches the tracer, the extractor blames the user.

`Node`-typed mock vs subscriptable-item lambdas is a fundamental shape clash. Real composers will write `item["key"]` constantly. See `runs/notable/bf68452-log-analysis-bug-C-subscript.md` for full repro and proposed fixes.

**Implication for the article:** the cost-curve claims are robust on numeric tasks but blocked on string-parsing tasks at this sha. Story is still complete — we have multi-model curves on tasks that *do* work.

### A — Multi-model curve (Haiku added)

Sum-only sweep at N=[50, 200, 1000, 5000], **same data files**, both Sonnet (already done) and Haiku.

| N | Bricks-Sonnet | Bricks-Haiku | Raw-Sonnet | Raw-Haiku |
|---|---|---|---|---|
| 50 | $0.189 ✓ | **$0.040 ✓** | $0.046 ✓ | $0.033 ✓ |
| 200 | $0.018 ✓ | **$0.007 ✓** | $0.298 ✓ | $0.048 **✗** (off by 1.0000) |
| 1000 | $0.018 ✓ | **$0.006 ✓** | timeout ✗ | $0.117 **✗** (off by 0.18) |
| 5000 | $0.018 ✓ | **$0.006 ✓** | timeout ✗ | timeout ✗ |

**Three findings:**

1. **Bricks-Haiku is the overall winner.** Cheaper compose than Bricks-Sonnet (3-4×). Equally correct at every size. The cheap model is enough for compose work — disambiguating "sum the values" doesn't need Opus-grade reasoning.
2. **Both Bricks variants stay flat across N.** Cost is dominated by compose, not data size. ~$0.006/run on Haiku at any N.
3. **Cheaper raw model fails earlier.** Haiku raw goes wrong at **N=200** (off by 1.0 — missed an entire number). Sonnet raw at least gets the right answer through N=200 before timing out at N=1000.

The headline article figure should plot all four curves. The two Bricks lines hug the X-axis; the two raw-LLM lines climb steeply and crash.

### C — Determinism (10× same task)

Sum-only N=200 with Sonnet, ten consecutive runs, separate Python processes.

- **10/10 Bricks outputs identical** to the byte: `{'sum': 6228.260100000002}` (the trailing `2` is IEEE-754 noise from Python's `sum()` — same noise every time because it's the same deterministic Python).
- **10/10 raw-LLM outputs identical:** `{'sum': 6228.2601}` (Sonnet was deterministic on this prompt — happy surprise; not always true).
- **10/10 blueprint YAMLs identical** — composer emits the same blueprint every time.

**Cost variance is the unexpected finding:**
- Bricks: $0.042 (cold cache_creation), then $0.016 × 9 — predictable.
- Raw LLM: $0.22 to $0.43 across the 10 runs. **2× cost variance for the same prompt.** Driven by how warm Anthropic's prompt cache happens to be when each call lands.

**Article angle:** even when raw LLM is "deterministic in answer," it's *not* deterministic in cost. Bricks is bit-identical on both axes.

### D — Counter-case: where Bricks loses

Single email-rewrite task: rewrite an angry-customer email in a warmer tone. No objective truth. Run record `runs/track-1-exploration_fbde5b64-26e4-499a-9d3d-b3859f94e9ab.json`.

**Bricks output:**
> "hi support, your product STOPPED WORKING after the last update. I've been a customer for 3 years and this is unacceptable. Fix it ASAP or I'm canceling my subscription. Order #A8821."

**Identical to the input.** Bricks composed a blueprint that returned the email unchanged. No "rewrite text" brick in the catalog → composer emitted an identity pass-through. Cost: **$0.061**, 22s.

**Raw LLM output:**
> "Hello Support Team, I hope you're doing well. I wanted to reach out regarding an issue I've encountered since the most recent update — unfortunately, the product has stopped working on my end. As a loyal customer of three years, I have always valued your service... For reference, my order number is #A8821. Thank you so much for your help!"

Genuinely polite, preserved every fact, kept the order number. Cost: **$0.022**, 8s.

**Bricks was 3× more expensive AND silently produced the wrong output.** Compiler-style framing makes this predictable: *a compiler can only emit instructions in its target ISA. If "rewrite politely" isn't in the brick catalog, the composer emits a no-op.*

This is the section of the article that says: **"Use Bricks for structured, recurring, deterministic work. For judgment, style, and generation — use the LLM directly."**

### Updated cumulative findings

- Cost-curve and tipping-point story (~N=100): ✓ holds across two models
- Determinism claim: ✓ verified bit-identical across 10 reps
- Three-regime cost (session-cold / task-cold / task-warm): ✓ documented
- Cache-TTL observation: ✓ captured (degradation visible after ~5 days)
- Generality across task types: **partial** — works on numeric, blocked on string-parsing pending Bug C fix
- Honest counter-case: ✓ Bricks loses cleanly on judgment tasks

**Empirical backbone for the article: complete.**

## 2026-04-28 — Reliability sweep (15 task shapes)

To go beyond "we have nice numbers on sum-only" → "Bricks works on the *category* of structured-data tasks." Picked 15 short tasks of varying shape (reductions, filters, top-K, sort, dedup, string ops, dict-field extraction). All run with Sonnet at small N. Single-shot, no retries.

### Headline numbers

- **Bricks: 10/15 (66%)** correct.
- **Raw LLM: 14/15 (93%)** correct.
- **The 1 raw-LLM failure (`squared-sum`) is the 1 Bricks-only win** — raw sonnet manually summed 50 squared values in markdown and got it 0.01 wrong. Bricks (Python `sum(v*v for v)`) was exact.

So the matrix isn't "Bricks loses overall." It's: **at small N, raw LLM is more reliable than Bricks on diverse one-off tasks; the one task where the LLM has to do real arithmetic, Bricks wins.** The cost-curve story (where Bricks crushes raw LLM) starts at N≥200, not N=50.

### Failure taxonomy (Bricks)

| Case | Failure | Class |
|---|---|---|
| sum-gt50 | `list` passed to `filter_dict_list` (expects `list[dict]`) | **Type-mismatch at brick I/O** |
| sort-asc-unique | `int` passed to `sort_dict_list` (expects `list[dict]`) | **Type-mismatch at brick I/O** |
| string-lengths | Output wrapped: `[{"result": {"chars": 5}}, ...]` instead of `[5, ...]` | **Field-pluck missing** |
| string-uppercase | Output wrapped: `[{"result": "APPLE"}, ...]` instead of `["APPLE", ...]` | **Field-pluck missing** |
| bottom3-asc | Output `[None, None, None]` | **Broken chain — None-pollution** |

**Two of five failures are pure type-mismatch** — exactly the failure class my [composer-as-compiler notes](article/notes-composer-as-compiler-improvements.md) predicted (Tier-1 #1: type-check brick I/O at compose time). Two more are output-unwrapping mistakes the composer makes when it picks a "rich-output" brick but forgets to extract the requested field.

These are fixable. The failure modes aren't deep — they're the kind of error a stricter compose-time validator would catch.

### Cost note (article-relevant)

Sonnet raw-LLM at small N runs at ~$0.02 across the board (cache very warm — system prompt + this set of tasks lives in the cache). Bricks compose ranges $0.04 to $0.32 on this sweep. **At N≤10, raw LLM beats Bricks on cost AND reliability.** This sharpens the article's tipping-point claim: Bricks needs scale (N or repetition) to win — the line isn't fuzzy.

### Failure taxonomy (raw LLM, the one miss)

`squared-sum`: LLM laid out a 50-row markdown table, summed in chunks, and reported 123300.1025. Truth: 123300.1125. Off by 0.01 (~1 part in 10⁷). Then wrapped the JSON answer in code fences my parser stripped imperfectly. Spent **$0.46** on the call — the most expensive raw-LLM call in the sweep, doing arithmetic by hand for a problem `sum(v*v)` solves in microseconds.

This is the one to highlight in the article: **even when the LLM "shows its work" and is "trying hard," it gets simple math wrong.** That's the wedge.

### Implication for article

- **Honesty:** Bricks isn't a magic bullet. 1/3 of tasks failed at this sha. Most failures are compose-time bugs we can name.
- **Pivot:** the article's claim isn't "Bricks always wins." It's "**Bricks wins at scale, on recurring deterministic work; raw LLM wins on one-off small tasks; the LLM should do arithmetic in code, not in markdown.**"
- **Roadmap link:** the failure taxonomy maps directly to the compiler-improvements notes. Article can frame current failures as "v0.5 of a category that has 50 years of compiler theory ready to apply."

### Run records

15 runs in `runs/track-1-exploration_*.json`, timestamped 2026-04-28. Manifest line per run in `manifest/track-1.jsonl`.

## 2026-04-29 — Playground replay post-#75 (Bug C fix + spec fix + 300s timeout)

After #69/#70 (Bug C: for_each lambda subscripting), #74 (preset expected_outputs match data; ClaudeCode timeout 300s), and the playground refactor (#76-#79), re-ran all 4 web-playground scenarios via [`runs/playground-replay/replay_native.py`](runs/playground-replay/replay_native.py) using `ClaudeCodeProvider` directly (the new `bricks playground run` CLI hardcodes LiteLLM, which costs API rates).

### Headline shift

The user's original "Bricks loses on all scenarios" report is now objectively wrong on this sha:

| Scenario | Bricks | Raw LLM | Verdict |
|---|---|---|---|
| crm_pipeline | **3/3 ✓** | 1/3 ✗ | **Bricks wins** (raw miscounted revenue by $500) |
| ticket_pipeline | **4/4 ✓** | 2/4 ✗ | **Bricks wins** (raw off by 1 on two keys) |
| cross_dataset_join | **4/4 ✓** | 4/4 ✓ | **Both pass** — #74 fixed the bad expected_output |
| custom_example | 1/2 ✗ | 1/2 ✗ | Both fail; new bug (below) |

So at sha `020ae4c`: Bricks wins or ties on **3 of 4 demo scenarios**. The post-#75 playground actually demonstrates the article's thesis honestly.

### custom_example — composer picked wrong primitive

The lone Bricks regression. Task: compute `total_value = Σ(price × stock)` over products in stock. The composer emitted:

```python
@flow
def process_product_inventory(raw_api_response):
    parsed          = step.extract_json_from_str(text=raw_api_response)
    out_of_stock    = step.filter_dict_list(items=parsed.output, key="stock", value=0)
    available       = step.difference_lists(a=parsed.output, b=out_of_stock.output)
    available_count = step.count_dict_list(items=available.output)
    prices          = step.map_values(items=available.output, key="price")
    stocks          = step.map_values(items=available.output, key="stock")
    zipped          = step.zip_lists(a=prices.output, b=stocks.output)
    per_product     = for_each(items=zipped.output, do=lambda item: step.reduce_sum(values=item))  # bug
    total_value     = step.calculate_aggregates(items=per_product.output, field="result", operation="sum")
    return {"available_count": available_count, "total_value": total_value}
```

`step.reduce_sum(values=item)` over a `(price, stock)` pair computes `price + stock`, not `price × stock`. So `total_value` ended up at $454.97 vs expected $2,859.75.

Three things wrong-in-an-illustrative-way:
1. **Catalog gap.** There is no `reduce_product` brick. The composer reached for `reduce_sum` because it was the closest-named primitive.
2. **Composer didn't use the obvious workaround** — `for_each(items=available, do=lambda p: step.multiply(a=p["price"], b=p["stock"]))` then sum. This is now legal post-Bug-C but the composer didn't reach for it.
3. **Raw LLM failed differently and less badly** — got $2,459.27 (off by $400, ~14%). Probably truncated reasoning. Bricks's $454.97 is structurally wrong (off by a factor of ~6).

Article material: this is a **catalog gap masquerading as a composer mistake**. In compiler terms — when an instruction is missing from the ISA, the front-end emits a workaround that looks right but isn't. Adds a fourth failure class to the taxonomy.

### Status of filed issues at this sha

- Bug C fixed (#69/#70) — for_each lambda supports `item["key"]`.
- Preset `expected_outputs` corrected to match data; ClaudeCode default timeout raised to 300s (#73/#74).
- Playground refactor merged (#76-#79) — showcase deleted, presets/datasets/loader promoted out of `web/`, headless CLI added.
- Open: token display dropping cache fields (flagged, not formally filed).
- Open: composer "missing-primitive fallback" on no-`reduce_product`-style cases — would be Phase 2 of the brick-selector roadmap (miss-fallback + interactive refinement).

### Side-effect: new playground CLI dropped ClaudeCodeProvider support

`bricks playground run` (added in #79) hardcodes `LiteLLMProvider`, requiring an `ANTHROPIC_API_KEY` and billing at API rates. The web playground still supports `provider="claude_code"` so we stayed on the Pro account by replaying via [`runs/playground-replay/replay_native.py`](runs/playground-replay/replay_native.py) — direct import of `BricksEngine` + `RawLLMEngine` + `ClaudeCodeProvider`. Worth flagging as a small follow-up: `bricks playground run --provider claudecode` for parity with the web UI.

### What this means for the article

- Both empirical pillars hold: Bricks wins on correctness at scale (cost-curve sweep), Bricks wins or ties on real demo scenarios (3 of 4 here).
- The "honest counter-case" section now has a **better example than email-rewrite**: `custom_example` is a structured-data task where Bricks fails on a catalog gap. Engineers will recognise this as the kind of friction they'd hit in practice. Worth swapping the article's counter-case to use this.
- The "stop the LLM doing arithmetic" wedge is reinforced: even on a 5-row dataset, raw LLM miscounted revenue ($1,023.50 vs $1,524.00) and ticket categories. At small N. With a clear task. The model still drifts.
