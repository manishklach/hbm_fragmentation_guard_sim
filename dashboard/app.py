from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run_sim import SimulationConfig, load_trace, simulate

TRACE_OPTIONS = {
    "llm_kvcache_growth": REPO_ROOT / "traces" / "llm_kvcache_growth.jsonl",
    "moe_expert_swap": REPO_ROOT / "traces" / "moe_expert_swap.jsonl",
    "fragmentation_stressor": REPO_ROOT / "traces" / "fragmentation_stressor.jsonl",
}
POLICY_COLORS = {
    "confidence": "#1F3A7A",
    "lru": "#E8593C",
    "clockpro": "#2D8450",
}
PHASE_COLORS = ["#1F3A7A", "#E8593C", "#2D8450", "#A56B00", "#7B849A", "#5498FF"]


@st.cache_data(show_spinner=False)
def cached_trace(trace_path: str):
    return load_trace(trace_path)


def run_selected_policies(
    trace_key: str,
    config: SimulationConfig,
    compare_all: bool,
    selected_policy: str,
):
    trace_events = cached_trace(str(TRACE_OPTIONS[trace_key]))
    policies = ["confidence", "lru", "clockpro"] if compare_all else [selected_policy]
    return {policy: simulate(trace_events, policy, config) for policy in policies}


def bucket_counts(result, bucket_count: int = 10):
    if not result.timeline:
        return [f"B{i}" for i in range(bucket_count)], [0] * bucket_count, [0] * bucket_count
    size = max(1, len(result.timeline) // bucket_count)
    labels = []
    faults = []
    migrations = []
    for index in range(bucket_count):
        start = index * size
        if index == bucket_count - 1:
            end = len(result.timeline)
        else:
            end = min(len(result.timeline), (index + 1) * size)
        window = result.timeline[start:end]
        labels.append(f"{index * 10}-{(index + 1) * 10}%")
        faults.append(sum(point.faults for point in window))
        migrations.append(sum(point.migrations for point in window))
    return labels, faults, migrations


def free_extent_histogram(extents: list[tuple[int, int]], bins: int = 8):
    sizes = [size for _, size in extents if size > 0]
    if not sizes:
        return [0], [0], 0
    minimum = min(sizes)
    maximum = max(sizes)
    if minimum == maximum:
        return [f"{minimum}"], [len(sizes)], maximum
    width = max(1, (maximum - minimum + bins - 1) // bins)
    counts = [0] * bins
    labels = []
    for index in range(bins):
        start = minimum + index * width
        end = start + width - 1
        labels.append(f"{start}-{end}")
    for value in sizes:
        index = min((value - minimum) // width, bins - 1)
        counts[int(index)] += 1
    return labels, counts, maximum


def build_csv(results: dict[str, object]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "policy",
            "t",
            "event",
            "phase",
            "occupancy",
            "external_frag",
            "entropy",
            "faults",
            "migrations",
            "bytes_moved",
            "lfe",
            "holes",
        ]
    )
    for policy, result in results.items():
        for point in result.timeline:
            writer.writerow(
                [
                    policy,
                    point.t,
                    point.event,
                    point.phase or "",
                    point.occupancy,
                    point.external_frag,
                    point.entropy,
                    point.faults,
                    point.migrations,
                    point.bytes_moved,
                    point.lfe,
                    point.holes,
                ]
            )
    return buffer.getvalue()


def render_occupancy_chart(results, compare_all: bool, selected_policy: str):
    fig = go.Figure()
    if compare_all:
        for policy, result in results.items():
            x_values = [point.t for point in result.timeline]
            y_values = [point.occupancy for point in result.timeline]
            fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="lines",
                    name=policy,
                    line=dict(color=POLICY_COLORS[policy], width=3),
                )
            )
    else:
        result = results[selected_policy]
        phases = []
        for point in result.timeline:
            if point.phase and point.phase not in phases:
                phases.append(point.phase)
        if not phases:
            phases = ["simulation"]
        for index, phase in enumerate(phases):
            x_values = []
            y_values = []
            for point in result.timeline:
                if (point.phase or "simulation") == phase:
                    x_values.append(point.t)
                    y_values.append(point.occupancy)
                else:
                    x_values.append(point.t)
                    y_values.append(None)
            fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="lines",
                    name=phase,
                    line=dict(color=PHASE_COLORS[index % len(PHASE_COLORS)], width=3),
                )
            )

    fig.update_layout(
        title="HBM Occupancy Over Time",
        xaxis_title="Timestamp",
        yaxis_title="HBM resident bytes",
        legend_title="Policy" if compare_all else "Phase",
        margin=dict(l=24, r=24, t=56, b=24),
    )
    return fig


def render_fragmentation_chart(results, compare_all: bool, selected_policy: str):
    fig = go.Figure()
    targets = results.items() if compare_all else [(selected_policy, results[selected_policy])]
    for policy, result in targets:
        color = POLICY_COLORS.get(policy, "#1F3A7A")
        fig.add_trace(
            go.Scatter(
                x=[point.t for point in result.timeline],
                y=[point.external_frag for point in result.timeline],
                mode="lines",
                name=f"{policy} external_frag" if compare_all else "external_frag",
                line=dict(color=color, width=3),
                yaxis="y1",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[point.t for point in result.timeline],
                y=[point.entropy for point in result.timeline],
                mode="lines",
                name=f"{policy} entropy" if compare_all else "entropy",
                line=dict(color=color, width=2, dash="dash"),
                yaxis="y2",
            )
        )

    fig.update_layout(
        title="Fragmentation Metrics Over Time",
        xaxis_title="Timestamp",
        yaxis=dict(title="external_frag", range=[0, 1]),
        yaxis2=dict(title="entropy", overlaying="y", side="right"),
        legend_title="Series",
        margin=dict(l=24, r=24, t=56, b=24),
    )
    return fig


def render_fault_migration_chart(results, compare_all: bool, selected_policy: str):
    fig = go.Figure()
    policies = results.items() if compare_all else [(selected_policy, results[selected_policy])]
    for policy, result in policies:
        labels, faults, migrations = bucket_counts(result)
        if compare_all:
            fig.add_trace(
                go.Bar(
                    x=labels,
                    y=faults,
                    name=f"{policy} faults",
                    marker_color=POLICY_COLORS[policy],
                )
            )
            fig.add_trace(
                go.Bar(
                    x=labels,
                    y=migrations,
                    name=f"{policy} migrations",
                    marker_color=POLICY_COLORS[policy],
                    opacity=0.45,
                )
            )
        else:
            fig.add_trace(go.Bar(x=labels, y=faults, name="faults", marker_color="#1F3A7A"))
            fig.add_trace(go.Bar(x=labels, y=migrations, name="migrations", marker_color="#E8593C"))

    fig.update_layout(
        title="Fault and Migration Events",
        xaxis_title="Time bucket",
        yaxis_title="Count",
        barmode="group",
        margin=dict(l=24, r=24, t=56, b=24),
    )
    return fig


def render_free_extent_chart(results, compare_all: bool, selected_policy: str):
    fig = go.Figure()
    policies = results.items() if compare_all else [(selected_policy, results[selected_policy])]
    for policy, result in policies:
        labels, counts, largest = free_extent_histogram(result.final_free_extents)
        colors = [
            "#2D8450" if label.startswith(str(largest)) else POLICY_COLORS.get(policy, "#1F3A7A")
            for label in labels
        ]
        fig.add_trace(
            go.Bar(
                x=labels,
                y=counts,
                name=policy if compare_all else "free extents",
                marker_color=colors if not compare_all else POLICY_COLORS[policy],
            )
        )
        if not compare_all:
            fig.add_trace(
                go.Bar(
                    x=[str(largest)],
                    y=[1],
                    name="LFE",
                    marker_color="#2D8450",
                )
            )

    fig.update_layout(
        title="Free Extent Size Distribution",
        xaxis_title="Extent size bucket",
        yaxis_title="Count",
        barmode="group",
        margin=dict(l=24, r=24, t=56, b=24),
    )
    return fig


st.set_page_config(page_title="HBM Fragmentation Guard Dashboard", layout="wide")
st.title("HBM Fragmentation Guard Dashboard")
st.caption("Interactive parameter sweeping for confidence-gated, LRU, and CLOCK-Pro baselines.")

with st.sidebar:
    st.header("Simulation Controls")
    selected_policy = st.radio("Policy", ["confidence", "lru", "clockpro"], index=0)
    trace_key = st.selectbox("Trace", list(TRACE_OPTIONS.keys()), index=0)
    hbm_mb = st.slider("HBM size (MB)", min_value=64, max_value=2048, step=64, value=256)
    lb_threshold = st.slider("LB threshold", min_value=0.50, max_value=0.85, step=0.01, value=0.65)
    ub_threshold = st.slider("UB threshold", min_value=0.75, max_value=0.95, step=0.01, value=0.85)
    thrash_budget = st.slider("Thrash budget", min_value=10, max_value=500, step=10, value=100)
    if selected_policy == "confidence":
        confidence_lb = st.slider(
            "Confidence LB",
            min_value=0.50,
            max_value=0.90,
            step=0.05,
            value=0.70,
        )
    else:
        confidence_lb = 0.70
    compare_all = st.checkbox("Compare All Policies", value=False)
    run_clicked = st.button("Run Simulation", type="primary")

if run_clicked:
    st.session_state["dashboard_run"] = True

if not st.session_state.get("dashboard_run"):
    st.info("Choose parameters in the sidebar, then click Run Simulation.")
    st.stop()

config = SimulationConfig(
    miss_mode="demand",
    capacity=hbm_mb * 1024 * 1024,
    reserve=0,
    epoch=20,
    max_migration_bytes=thrash_budget * 1024 * 1024,
    max_faults=max(1, thrash_budget // 20),
    admit_lb=confidence_lb,
    evict_ub=max(0.0, 1.0 - ub_threshold),
)
results = run_selected_policies(trace_key, config, compare_all, selected_policy)
primary = results[selected_policy] if selected_policy in results else next(iter(results.values()))

if not primary.timeline:
    st.warning("This simulation returned zero events, so there is nothing to chart yet.")
    st.stop()

metrics_columns = st.columns(6)
metrics_columns[0].metric("Total Faults", primary.stats["faults"])
metrics_columns[1].metric("Total Migrations", primary.stats["migrations"])
metrics_columns[2].metric("Bytes Moved", f"{primary.stats['bytes_moved']:,}")
metrics_columns[3].metric("Fallback Epochs", primary.stats["fallback_epochs"])
metrics_columns[4].metric("Final external_frag", f"{primary.fragmentation.external_frag:.3f}")
metrics_columns[5].metric("Final LFE", f"{primary.fragmentation.lfe:,}")

csv_payload = build_csv(results)
st.download_button(
    "Download Results as CSV",
    data=csv_payload,
    file_name=f"{trace_key}_simulation.csv",
    mime="text/csv",
)

left, right = st.columns(2)
left.plotly_chart(
    render_occupancy_chart(results, compare_all, selected_policy),
    use_container_width=True,
)
right.plotly_chart(
    render_fragmentation_chart(results, compare_all, selected_policy),
    use_container_width=True,
)

left, right = st.columns(2)
left.plotly_chart(
    render_fault_migration_chart(results, compare_all, selected_policy),
    use_container_width=True,
)
right.plotly_chart(
    render_free_extent_chart(results, compare_all, selected_policy),
    use_container_width=True,
)
