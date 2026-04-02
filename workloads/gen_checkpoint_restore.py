from __future__ import annotations

import json
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parents[1] / "traces" / "checkpoint_restore.jsonl"
MB = 1024 * 1024


def generate_events():
    events = []
    t = 0
    params = [f"param_{index}" for index in range(20)]
    acts = [f"act_{index}" for index in range(20)]

    for param in params:
        events.append({"t": t, "event": "alloc", "id": param, "size": 4 * MB, "phase": "training"})
        t += 1
        events.append(
            {
                "t": t,
                "event": "touch",
                "id": param,
                "mu": 0.65,
                "sigma": 0.10,
                "phase": "training",
            }
        )
        t += 1

    for act in acts:
        events.append({"t": t, "event": "alloc", "id": act, "size": 2 * MB, "phase": "training"})
        t += 1
        events.append(
            {
                "t": t,
                "event": "touch",
                "id": act,
                "mu": 0.45,
                "sigma": 0.12,
                "phase": "training",
            }
        )
        t += 1

    for act in acts[:10]:
        events.append({"t": t, "event": "free", "id": act, "phase": "training"})
        t += 1

    events.append({"t": t, "event": "safe_window", "phase": "training_to_save"})
    t += 1

    active_objects = params + acts[10:]
    for obj_id in active_objects:
        events.append(
            {
                "t": t,
                "event": "touch",
                "id": obj_id,
                "mu": 0.10,
                "sigma": 0.05,
                "phase": "checkpoint_save",
            }
        )
        t += 1

    for obj_id in active_objects:
        events.append({"t": t, "event": "free", "id": obj_id, "phase": "checkpoint_save"})
        t += 1

    events.append({"t": t, "event": "safe_window", "phase": "save_to_restore"})
    t += 1

    for obj_id in active_objects:
        size = 4 * MB if obj_id.startswith("param_") else 2 * MB
        events.append({"t": t, "event": "alloc", "id": obj_id, "size": size, "phase": "restore"})
        t += 1
        events.append(
            {
                "t": t,
                "event": "touch",
                "id": obj_id,
                "mu": 0.90,
                "sigma": 0.05,
                "phase": "restore",
            }
        )
        t += 1

    events.append({"t": t, "event": "safe_window", "phase": "restore_to_resume"})
    t += 1

    for _ in range(2):
        for obj_id in active_objects:
            events.append(
                {
                    "t": t,
                    "event": "touch",
                    "id": obj_id,
                    "mu": 0.65,
                    "sigma": 0.10,
                    "phase": "resume_training",
                }
            )
            t += 1

    return events


def main():
    events = generate_events()
    OUT_PATH.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
