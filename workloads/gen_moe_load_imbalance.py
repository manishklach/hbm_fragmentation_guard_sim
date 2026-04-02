from __future__ import annotations

import json
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parents[1] / "traces" / "moe_load_imbalance.jsonl"
MB = 1024 * 1024


def generate_events():
    events = []
    t = 0
    experts = [f"expert_{index}" for index in range(20)]
    hot_experts = experts[:4]
    cold_experts = experts[4:]

    for expert in experts:
        events.append(
            {"t": t, "event": "alloc", "id": expert, "size": 8 * MB, "phase": "initial_load"}
        )
        t += 1

    cold_cursor = 0
    for round_index in range(28):
        for hot in hot_experts:
            for _ in range(2):
                events.append(
                    {
                        "t": t,
                        "event": "touch",
                        "id": hot,
                        "mu": 0.90,
                        "sigma": 0.05,
                        "phase": "moe_route",
                    }
                )
                t += 1
        for _ in range(2):
            cold = cold_experts[cold_cursor % len(cold_experts)]
            cold_cursor += 1
            events.append(
                {
                    "t": t,
                    "event": "touch",
                    "id": cold,
                    "mu": 0.15,
                    "sigma": 0.10,
                    "phase": "moe_route",
                }
            )
            t += 1

        if round_index % 5 == 4:
            retiring = cold_experts.pop(0)
            events.append({"t": t, "event": "free", "id": retiring, "phase": "expert_swap"})
            t += 1
            replacement = f"expert_new_{round_index}"
            cold_experts.append(replacement)
            events.append(
                {
                    "t": t,
                    "event": "alloc",
                    "id": replacement,
                    "size": 8 * MB,
                    "phase": "expert_swap",
                }
            )
            t += 1
            events.append(
                {
                    "t": t,
                    "event": "touch",
                    "id": replacement,
                    "mu": 0.15,
                    "sigma": 0.12,
                    "phase": "expert_swap",
                }
            )
            t += 1

    return events


def main():
    events = generate_events()
    OUT_PATH.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
