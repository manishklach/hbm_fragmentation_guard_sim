from __future__ import annotations

import json
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parents[1] / "traces" / "transformer_prefill_decode.jsonl"
MB = 1024 * 1024


def generate_events():
    events = []
    t = 0
    kv_ids = [f"kv_{index}" for index in range(10)]

    for kv_id in kv_ids:
        events.append({"t": t, "event": "alloc", "id": kv_id, "size": 16 * MB, "phase": "prefill"})
        t += 1
        events.append(
            {
                "t": t,
                "event": "touch",
                "id": kv_id,
                "mu": 0.30,
                "sigma": 0.10,
                "phase": "prefill",
            }
        )
        t += 1

    events.append({"t": t, "event": "safe_window", "phase": "prefill_to_decode"})
    t += 1

    for step in range(18):
        for kv_id in kv_ids:
            events.append(
                {
                    "t": t,
                    "event": "touch",
                    "id": kv_id,
                    "mu": 0.85,
                    "sigma": 0.05,
                    "phase": "decode",
                }
            )
            t += 1
        act_id = f"act_{step}"
        events.append(
            {"t": t, "event": "alloc", "id": act_id, "size": 512 * 1024, "phase": "decode"}
        )
        t += 1
        events.append(
            {
                "t": t,
                "event": "touch",
                "id": act_id,
                "mu": 0.10,
                "sigma": 0.05,
                "phase": "decode",
            }
        )
        t += 1
        events.append({"t": t, "event": "free", "id": act_id, "phase": "decode"})
        t += 1

    return events


def main():
    events = generate_events()
    OUT_PATH.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
