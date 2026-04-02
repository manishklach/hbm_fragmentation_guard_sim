from __future__ import annotations

import json
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parents[1] / "traces" / "multi_tenant_inference.jsonl"
MB = 1024 * 1024


def generate_events():
    events = []
    t = 0
    tenant_b_objects = []
    tenant_c_objects = []

    for round_index in range(70):
        burst_id = f"tenant_A_req_{round_index}"
        events.append({"t": t, "event": "alloc", "id": burst_id, "size": MB, "phase": "tenant_A"})
        t += 1
        events.append(
            {
                "t": t,
                "event": "touch",
                "id": burst_id,
                "mu": 0.20,
                "sigma": 0.20,
                "phase": "tenant_A",
            }
        )
        t += 1
        if round_index % 2 == 1:
            events.append({"t": t, "event": "free", "id": burst_id, "phase": "tenant_A"})
            t += 1

        steady_id = f"tenant_B_cache_{round_index}"
        events.append(
            {"t": t, "event": "alloc", "id": steady_id, "size": 2 * MB, "phase": "tenant_B"}
        )
        t += 1
        tenant_b_objects.append(steady_id)
        touch_target = tenant_b_objects[max(0, len(tenant_b_objects) - 3)]
        events.append(
            {
                "t": t,
                "event": "touch",
                "id": touch_target,
                "mu": 0.88,
                "sigma": 0.05,
                "phase": "tenant_B",
            }
        )
        t += 1
        if round_index % 6 == 5 and tenant_b_objects:
            events.append(
                {"t": t, "event": "free", "id": tenant_b_objects.pop(0), "phase": "tenant_B"}
            )
            t += 1

        heavy_id = f"tenant_C_tensor_{round_index}"
        events.append(
            {"t": t, "event": "alloc", "id": heavy_id, "size": 6 * MB, "phase": "tenant_C"}
        )
        t += 1
        tenant_c_objects.append(heavy_id)
        events.append(
            {
                "t": t,
                "event": "touch",
                "id": heavy_id,
                "mu": 0.55,
                "sigma": 0.10,
                "phase": "tenant_C",
            }
        )
        t += 1
        if len(tenant_c_objects) > 4 and round_index % 3 == 2:
            events.append(
                {"t": t, "event": "free", "id": tenant_c_objects.pop(0), "phase": "tenant_C"}
            )
            t += 1

    return events


def main():
    events = generate_events()
    OUT_PATH.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
