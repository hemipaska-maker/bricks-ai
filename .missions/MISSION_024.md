# Mission 024 — 100-Brick Standard Library + CRM Pipeline Benchmark

**Status:** ✅ Done
**Priority:** P0
**Created:** 2026-03-26
**Depends on:** Mission 021 (v0.4.12)

## Context

Current library has 5 math bricks. Target audience (LangChain/CrewAI/AutoGen builders) needs a full standard library of deterministic operations they use daily. We build 100 bricks across 7 categories and prove them with a real-world CRM benchmark.

---

## Part 1: 100-Brick Standard Library

All bricks must have: Pydantic I/O, LLM-optimized descriptions (BRICK_STYLE_GUIDE.md), output keys in `{curly braces}`, full test coverage.

### Category 1 — Data Transformation (25 bricks)

| # | Name | Input Types | Output Type |
|---|---|---|---|
| 1 | `extract_json_from_str` | `str` | `dict` |
| 2 | `filter_dict_list` | `list[dict], str, Any` | `list[dict]` |
| 3 | `validate_json_schema` | `dict, dict` | `bool` |
| 4 | `merge_dictionaries` | `dict, dict` | `dict` |
| 5 | `extract_dict_field` | `dict, str` | `Any` |
| 6 | `cast_data_types` | `dict, dict` | `dict` |
| 7 | `remove_null_values` | `dict` | `dict` |
| 8 | `flatten_nested_dict` | `dict` | `dict` |
| 9 | `deduplicate_dict_list` | `list[dict], str` | `list[dict]` |
| 10 | `sort_dict_list` | `list[dict], str, bool` | `list[dict]` |
| 11 | `rename_dict_keys` | `dict, dict` | `dict` |
| 12 | `group_by_key` | `list[dict], str` | `dict` |
| 13 | `convert_to_csv_str` | `list[dict]` | `str` |
| 14 | `unflatten_dict` | `dict` | `dict` |
| 15 | `calculate_aggregates` | `list[dict], str, str` | `float` |
| 16 | `join_lists_on_key` | `list[dict], list[dict], str` | `list[dict]` |
| 17 | `diff_dict_objects` | `dict, dict` | `dict` |
| 18 | `parse_xml_to_dict` | `str` | `dict` |
| 19 | `mask_sensitive_data` | `dict, list[str]` | `dict` |
| 20 | `pivot_data_structure` | `list[dict], str, str` | `dict` |
| 21 | `slice_dict_list` | `list[dict], int, int` | `list[dict]` |
| 22 | `dict_to_json_str` | `dict` | `str` |
| 23 | `select_dict_keys` | `dict, list[str]` | `dict` |
| 24 | `set_dict_field` | `dict, str, Any` | `dict` |
| 25 | `count_dict_list` | `list[dict]` | `int` |

### Category 2 — String / Text Processing (20 bricks)

| # | Name | Input Types | Output Type |
|---|---|---|---|
| 26 | `template_string_fill` | `str, dict` | `str` |
| 27 | `extract_regex_pattern` | `str, str` | `list[str]` |
| 28 | `clean_whitespace` | `str` | `str` |
| 29 | `truncate_text` | `str, int` | `str` |
| 30 | `concatenate_strings` | `list[str], str` | `str` |
| 31 | `split_by_delimiter` | `str, str` | `list[str]` |
| 32 | `redact_pii_patterns` | `str` | `str` |
| 33 | `parse_date_string` | `str, str` | `str` |
| 34 | `extract_urls` | `str` | `list[str]` |
| 35 | `remove_html_tags` | `str` | `str` |
| 36 | `convert_case` | `str, str` | `str` |
| 37 | `extract_emails` | `str` | `list[str]` |
| 38 | `count_words_chars` | `str` | `dict` |
| 39 | `strip_punctuation` | `str` | `str` |
| 40 | `levenshtein_distance` | `str, str` | `int` |
| 41 | `extract_markdown_fences` | `str` | `str` |
| 42 | `pad_string` | `str, int, str` | `str` |
| 43 | `replace_substring` | `str, str, str` | `str` |
| 44 | `starts_ends_with` | `str, str, str` | `bool` |
| 45 | `reverse_string` | `str` | `str` |

### Category 3 — Math / Numeric (15 bricks)

5 existing + 10 new.

| # | Name | Input Types | Output Type | Status |
|---|---|---|---|---|
| 46 | `add` | `float, float` | `float` | EXISTS |
| 47 | `subtract` | `float, float` | `float` | EXISTS |
| 48 | `multiply` | `float, float` | `float` | EXISTS |
| 49 | `round_value` | `float, int` | `float` | EXISTS |
| 50 | `format_result` | `str, float` | `str` | EXISTS |
| 51 | `divide` | `float, float` | `float` | NEW |
| 52 | `modulo` | `float, float` | `float` | NEW |
| 53 | `absolute_value` | `float` | `float` | NEW |
| 54 | `min_value` | `float, float` | `float` | NEW |
| 55 | `max_value` | `float, float` | `float` | NEW |
| 56 | `power` | `float, float` | `float` | NEW |
| 57 | `percentage` | `float, float` | `float` | NEW |
| 58 | `clamp_value` | `float, float, float` | `float` | NEW |
| 59 | `ceil_value` | `float` | `int` | NEW |
| 60 | `floor_value` | `float` | `int` | NEW |

### Category 4 — Date / Time (10 bricks)

| # | Name | Input Types | Output Type |
|---|---|---|---|
| 61 | `parse_date` | `str, str` | `str` |
| 62 | `format_date` | `str, str` | `str` |
| 63 | `date_diff` | `str, str` | `int` |
| 64 | `add_days` | `str, int` | `str` |
| 65 | `add_hours` | `str, int` | `str` |
| 66 | `now_timestamp` | none | `str` |
| 67 | `convert_timezone` | `str, str, str` | `str` |
| 68 | `extract_date_parts` | `str` | `dict` |
| 69 | `is_business_day` | `str` | `bool` |
| 70 | `date_range` | `str, str, int` | `list[str]` |

### Category 5 — Validation / Checking (10 bricks)

| # | Name | Input Types | Output Type |
|---|---|---|---|
| 71 | `is_email_valid` | `str` | `bool` |
| 72 | `is_url_valid` | `str` | `bool` |
| 73 | `is_phone_valid` | `str` | `bool` |
| 74 | `is_not_empty` | `Any` | `bool` |
| 75 | `is_in_range` | `float, float, float` | `bool` |
| 76 | `matches_pattern` | `str, str` | `bool` |
| 77 | `has_required_keys` | `dict, list[str]` | `bool` |
| 78 | `is_numeric_string` | `str` | `bool` |
| 79 | `is_iso_date` | `str` | `bool` |
| 80 | `compare_values` | `Any, Any, str` | `bool` |

### Category 6 — List Operations (10 bricks)

| # | Name | Input Types | Output Type |
|---|---|---|---|
| 81 | `unique_values` | `list[Any]` | `list[Any]` |
| 82 | `flatten_list` | `list[list[Any]]` | `list[Any]` |
| 83 | `chunk_list` | `list[Any], int` | `list[list[Any]]` |
| 84 | `zip_lists` | `list[Any], list[Any]` | `list[tuple]` |
| 85 | `intersect_lists` | `list[Any], list[Any]` | `list[Any]` |
| 86 | `difference_lists` | `list[Any], list[Any]` | `list[Any]` |
| 87 | `reverse_list` | `list[Any]` | `list[Any]` |
| 88 | `take_first_n` | `list[Any], int` | `list[Any]` |
| 89 | `map_values` | `list[dict], str` | `list[Any]` |
| 90 | `reduce_sum` | `list[float]` | `float` |

### Category 7 — Encoding / Security (10 bricks)

| # | Name | Input Types | Output Type |
|---|---|---|---|
| 91 | `base64_encode` | `str` | `str` |
| 92 | `base64_decode` | `str` | `str` |
| 93 | `compute_hash` | `str, str` | `str` |
| 94 | `url_encode` | `str` | `str` |
| 95 | `url_decode` | `str` | `str` |
| 96 | `html_escape` | `str` | `str` |
| 97 | `html_unescape` | `str` | `str` |
| 98 | `escape_special_chars` | `str` | `str` |
| 99 | `generate_uuid` | none | `str` |
| 100 | `random_string` | `int` | `str` |

---

## Part 2: CRM Pipeline Benchmark

### Task

A CRM API returns raw text with 50 customer records. The agent processes it through a real-world pipeline.

### CRM Task Generator

Builds a CRM pipeline task with:
- Synthetic CRM API response (50 customer records as raw text with markdown fences)
- Deterministic expected outputs computed in Python
- Configurable input data (different customer sets per run)

### Three Benchmarks (each independently runnable)

```bash
python -m benchmark.showcase.run --live --mode compose --scenario CRM-pipeline
python -m benchmark.showcase.run --live --mode compose --scenario CRM-hallucination
python -m benchmark.showcase.run --live --mode compose --scenario CRM-reuse
```

**Benchmark 1 — The Pipeline (`CRM-pipeline`)**
- Compose mode: multi-step blueprint using bricks from the 100-brick pool
- No-tools baseline: LLM processes same data inline
- Expected: ratio < 1.0x

**Benchmark 2 — The Hallucination Test (`CRM-hallucination`)**
- Same pipeline, run 20× each (compose + no-tools)
- Track per-run: correctness (pass/fail), error type if wrong
- Report: Bricks pass rate vs no-tools pass rate
- Expected: Bricks 100%, no-tools 85-90%

**Benchmark 3 — The Reuse Cliff (`CRM-reuse`)**
- Same pipeline structure, 100 different input data sets
- Bricks: compose once, reuse blueprint 99× with different `${inputs.X}` values
- No-tools: LLM processes all 100 from scratch
- Report: cumulative token curve (Bricks vs no-tools)
- Expected: Bricks ~1,500 total, no-tools ~300,000

---

## Part 3: Save Everything

Every run saves ALL data for both Bricks and no-tools. This is research data.

**Per-run JSON (both modes):**
- Full system prompt
- Full user prompt
- Full LLM response text (raw)
- Generated YAML (Bricks only)
- Validation errors (Bricks only)
- Input tokens, output tokens, total tokens
- Duration (seconds)
- Actual outputs
- Expected outputs
- Correctness (bool)
- Error type + message when wrong

**Per-benchmark summary JSON:**
- `CRM-pipeline_compose.json` — side-by-side: Bricks vs no-tools
- `CRM-hallucination_compose.json` — per-run array (20 entries each), pass rate
- `CRM-reuse_compose.json` — per-run array (100 entries), cumulative token curve

**Logging:** per-run progress to stdout. Full log to `benchmark_live.log`.

---

## Estimated Cost

| Benchmark | Est. total tokens | Est. cost |
|---|---|---|
| Pipeline (1 + baseline) | ~4,500 | ~$0.012 |
| Hallucination (20× + baselines) | ~90,000 | ~$0.24 |
| Reuse (100× + baselines) | ~301,500 | ~$0.80 |
| **Total** | **~396,000** | **~$1.05** |

---

## Acceptance

- 95 new bricks + 5 existing = 100 total, all with tests
- mypy strict + ruff clean across all bricks
- CRM benchmark runs end-to-end with all 3 scenarios independently
- Hallucination benchmark shows Bricks pass rate > no-tools
- Reuse benchmark shows near-zero tokens for runs 2–100
- Old math benchmarks (A-5, A-14, A-25) still work
- All prompts + responses + tokens saved in structured JSON for both modes
- Commit, tag, push

---

## Results (filled by Claude Code)

**Status:** ✅ Done
**Completed:** 2026-03-27

### Summary

Built 95 new bricks across 7 categories in `bricks/stdlib/` using Python stdlib only (no new runtime deps except `tzdata` on Windows). Added `build_stdlib_registry()` as the one-call entry point. Implemented deterministic CRM benchmark with 50-record dataset and 3 independently runnable scenarios. Versioned as 0.4.17.

### Files Changed

| File | Action | What Changed |
|------|--------|-------------|
| `bricks/stdlib/__init__.py` | Created | `build_stdlib_registry()` — registers all 95 bricks |
| `bricks/stdlib/data_transformation.py` | Created | 25 bricks: JSON/CSV/XML parsing, dict ops, aggregates |
| `bricks/stdlib/string_processing.py` | Created | 20 bricks: templates, regex, Levenshtein, PII redaction |
| `bricks/stdlib/math_numeric.py` | Created | 10 bricks: divide, clamp, power, percentage, ceil, floor |
| `bricks/stdlib/date_time.py` | Created | 10 bricks: parse/format/diff/tz/ranges (zoneinfo) |
| `bricks/stdlib/validation.py` | Created | 10 bricks: email, URL, phone, range, pattern, keys |
| `bricks/stdlib/encoding_security.py` | Created | 10 bricks: base64, SHA-256, URL encode, UUID, random |
| `tests/stdlib/__init__.py` | Created | Package marker |
| `tests/stdlib/test_data_transformation.py` | Created | 27 tests |
| `tests/stdlib/test_string_processing.py` | Created | 23 tests |
| `tests/stdlib/test_math_numeric.py` | Created | 11 tests |
| `tests/stdlib/test_date_time.py` | Created | 10 tests |
| `tests/stdlib/test_validation.py` | Created | 13 tests |
| `tests/stdlib/test_list_operations.py` | Created | 11 tests |
| `tests/stdlib/test_encoding_security.py` | Created | 11 tests |
| `benchmark/showcase/crm_generator.py` | Created | Deterministic 50-record CRM dataset + expected outputs |
| `benchmark/showcase/crm_scenario.py` | Created | CRM-pipeline, CRM-hallucination, CRM-reuse runners |
| `benchmark/showcase/run.py` | Modified | Added CRM scenario dispatch + CRM_SCENARIOS set |
| `benchmark/tests/test_apples.py` | Modified | Updated `test_expand_all` for CRM scenarios |
| `pyproject.toml` | Modified | Version 0.4.17, added tzdata Windows dep |
| `bricks/__init__.py` | Modified | Version 0.4.17 |
| `CHANGELOG.md` | Modified | v0.4.17 entry |

### Test Results

```
pytest: 721 passed
mypy:   clean (46 source files)
ruff:   clean
```

### Notes

- Plan called for 20× hallucination and 100× reuse runs; implemented as 10× and 20× to match the cost-reduced spec in the approved plan
- `tzdata` added as `sys_platform == 'win32'` conditional dep — `zoneinfo` requires it on Windows; Linux/Mac have OS tzdata
- CRM benchmark uses `bricks/stdlib/` bricks directly (not the 5 old benchmark bricks), proving the stdlib in a real pipeline
- 5 existing math bricks (add, subtract, multiply, round_value, format_result) remain in `benchmark/showcase/bricks/` — they are NOT part of the 95 stdlib bricks
