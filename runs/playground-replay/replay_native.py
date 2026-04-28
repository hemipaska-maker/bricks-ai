"""Replay every preset playground scenario against Bricks + Raw LLM engines.

Bypasses both the web HTTP layer and the new ``bricks playground run`` CLI
(which hardcodes LiteLLMProvider). Imports the engines directly and uses
ClaudeCodeProvider so we stay on the Pro account.

Output: one JSON per scenario in this directory + a _summary.json roll-up.

Usage:
    python runs/playground-replay/replay_native.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from dataclasses import asdict, is_dataclass
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from bricks.playground.engine import BricksEngine, RawLLMEngine
from bricks.playground.scenario_loader import (
    _resolve_raw_data,
    load_scenario,
    resolve_preset,
)
from bricks.providers.claudecode.provider import ClaudeCodeProvider

OUT_DIR = Path(__file__).parent
PRESETS = ["crm_pipeline", "ticket_pipeline", "cross_dataset_join", "custom_example"]
MODEL = "sonnet"


def _serializable(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serializable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serializable(x) for x in obj]
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return repr(obj)


def run_one(preset: str, provider) -> dict:
    path = resolve_preset(preset)
    scenario = load_scenario(path)
    raw_data = _resolve_raw_data(scenario, base_dir=path.parent)
    fenced = raw_data if raw_data.strip().startswith("```") else f"```json\n{raw_data}\n```"

    print(f"\n=== {preset} ===")
    print(f"  expected: {scenario.expected_outputs}")

    bricks_engine = BricksEngine(provider=provider)
    t_b = time.monotonic()
    try:
        bricks_res = bricks_engine.solve(scenario.task_text, fenced)
        bricks_dict = _serializable(bricks_res)
    except Exception as exc:  # noqa: BLE001
        bricks_dict = {"error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
    bricks_dur_ms = int((time.monotonic() - t_b) * 1000)

    raw_engine = RawLLMEngine(provider=provider)
    t_r = time.monotonic()
    try:
        raw_res = raw_engine.solve(scenario.task_text, fenced)
        raw_dict = _serializable(raw_res)
    except Exception as exc:  # noqa: BLE001
        raw_dict = {"error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
    raw_dur_ms = int((time.monotonic() - t_r) * 1000)

    print(f"  bricks: outputs={bricks_dict.get('outputs')} err={(bricks_dict.get('error') or '')[:100]}")
    print(f"  rawllm: outputs={raw_dict.get('outputs')} err={(raw_dict.get('error') or '')[:100]}")

    record = {
        "preset": preset,
        "scenario": {
            "name": scenario.name,
            "task_text": scenario.task_text,
            "expected_outputs": scenario.expected_outputs,
            "model": scenario.model,
        },
        "bricks": {**bricks_dict, "_driver_duration_ms": bricks_dur_ms},
        "raw_llm": {**raw_dict, "_driver_duration_ms": raw_dur_ms},
    }
    out_path = OUT_DIR / f"native-{preset}.json"
    out_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return record


def main() -> int:
    provider = ClaudeCodeProvider(model=MODEL)
    summary = []
    for preset in PRESETS:
        try:
            rec = run_one(preset, provider)
        except Exception as exc:  # noqa: BLE001
            print(f"  driver-level failure: {exc}")
            traceback.print_exc()
            summary.append({"preset": preset, "driver_error": f"{type(exc).__name__}: {exc}"})
            continue
        b, r = rec["bricks"], rec["raw_llm"]
        summary.append({
            "preset": preset,
            "expected": rec["scenario"]["expected_outputs"],
            "bricks_outputs": b.get("outputs"),
            "bricks_error": (b.get("error") or "")[:200] if b.get("error") else "",
            "bricks_tokens_in": b.get("tokens_in"),
            "bricks_tokens_out": b.get("tokens_out"),
            "raw_outputs": r.get("outputs"),
            "raw_error": (r.get("error") or "")[:200] if r.get("error") else "",
            "raw_tokens_in": r.get("tokens_in"),
            "raw_tokens_out": r.get("tokens_out"),
        })
    (OUT_DIR / "_summary_native.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nDone. _summary_native.json written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
