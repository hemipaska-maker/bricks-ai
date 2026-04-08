# bricks-ai-stdlib

Standard library of 100 reusable bricks for the [bricks-ai](https://github.com/hemipaska-maker/bricks-ai) execution engine.

## Categories

| Category | Count | Examples |
|----------|-------|---------|
| Data Transformation | 25 | `filter_dict_list`, `extract_json_from_str`, `calculate_aggregates` |
| String Processing | 21 | `redact_pii_patterns`, `template_string_fill`, `split_by_delimiter` |
| Math & Statistics | 11 | `divide`, `round_number`, `percentage` |
| Validation | 10 | `is_email_valid`, `is_url_valid`, `compare_values` |
| List Operations | 11 | `map_values`, `intersect_lists`, `sort_dict_list` |
| Date & Time | 11 | `parse_date`, `date_diff`, `format_date` |
| Encoding & Security | 11 | `base64_encode`, `url_encode`, `compute_hash` |

All bricks are typed, tested, and auto-discovered by `Bricks.default()`.

## Install

```bash
pip install bricks-ai-stdlib
```

Or install together with the core engine:

```bash
pip install "bricks-ai[stdlib]"
```

## Generate Catalog

To regenerate the full brick catalog documentation:

```bash
python packages/stdlib/scripts/generate_catalog.py
```

This produces `docs/BRICK_CATALOG.md` with every brick's signature, parameters, and description.

## Full Documentation

See the [main repository README](https://github.com/hemipaska-maker/bricks-ai#readme) for full documentation and examples.
