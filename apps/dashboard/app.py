"""AI-Native Software Delivery Control Tower — Streamlit Dashboard.

Provides a visual interface for:
- Run timeline and status tracking
- Validation reports
- Risk assessments
- Canary monitoring
- Incident summaries
"""

from __future__ import annotations

import json
import sys
import os
from datetime import datetime
from pathlib import Path

import streamlit as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.database import Database

# ── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="AI-Native Delivery Control Tower",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
    }
    .status-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: bold;
    }
    .badge-completed { background: #c6f6d5; color: #22543d; }
    .badge-failed { background: #fed7d7; color: #9b2c2c; }
    .badge-running { background: #bee3f8; color: #2a4365; }
    .badge-blocked { background: #fefcbf; color: #744210; }
    .risk-low { color: #38a169; font-weight: bold; }
    .risk-medium { color: #d69e2e; font-weight: bold; }
    .risk-high { color: #e53e3e; font-weight: bold; }
    .stage-card {
        border-left: 4px solid #667eea;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        background: #f7fafc;
        border-radius: 0 8px 8px 0;
    }
</style>
""", unsafe_allow_html=True)


# ── Initialize Database ──────────────────────────────────────
@st.cache_resource
def get_db():
    db_path = os.environ.get("DB_PATH", "control_tower.db")
    if not Path(db_path).exists():
        st.warning(f"Database not found at {db_path}. Create tasks via the API first.")
        return None
    db = Database(db_path)
    return db


db = get_db()


# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.title("🏗️ Control Tower")
    st.markdown("---")

    page = st.radio(
        "Navigation",
        ["📊 Dashboard", "📋 Tasks", "🔄 Runs", "📈 Metrics", "⚙️ Policy"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.caption("AI-Native Software Delivery")
    st.caption("v0.1.0")

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()


# ── Dashboard Page ────────────────────────────────────────────
if page == "📊 Dashboard":
    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0">🏗️ AI-Native Software Delivery Control Tower</h1>
        <p style="margin:0; opacity:0.9">
            Agentic Code Changes • Risk-Aware CI/CD Gating • Observability-Driven Rollbacks
        </p>
    </div>
    """, unsafe_allow_html=True)

    if db:
        tasks = db.list_tasks()
        runs = db.list_runs()

        # Metrics row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Tasks", len(tasks))
        with col2:
            st.metric("Total Runs", len(runs))
        with col3:
            completed = sum(1 for r in runs if r.status == "completed")
            st.metric("Completed", completed)
        with col4:
            failed = sum(1 for r in runs if r.status == "failed")
            st.metric("Failed / Blocked", failed)

        st.markdown("---")

        # Recent runs
        st.subheader("🔄 Recent Runs")
        if runs:
            for run in runs[:10]:
                status_class = {
                    "completed": "badge-completed",
                    "failed": "badge-failed",
                    "blocked": "badge-blocked",
                }.get(run.status, "badge-running")

                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.markdown(f"**Run** `{run.id[:12]}...`")
                with col2:
                    st.markdown(f"State: `{run.current_state}`")
                with col3:
                    st.markdown(
                        f'<span class="status-badge {status_class}">{run.status}</span>',
                        unsafe_allow_html=True,
                    )
        else:
            st.info("No runs yet. Create a task and start a run via the API.")
    else:
        st.info("Database not connected. Start the API server first.")


# ── Tasks Page ────────────────────────────────────────────────
elif page == "📋 Tasks":
    st.header("📋 Engineering Tasks")

    if db:
        tasks = db.list_tasks()
        if tasks:
            for task in tasks:
                with st.expander(f"📌 {task.title}", expanded=False):
                    st.markdown(f"**ID:** `{task.id}`")
                    st.markdown(f"**Status:** {task.status}")
                    st.markdown(f"**Repository:** `{task.repo_path}`")
                    st.markdown(f"**Created:** {task.created_at}")
                    st.markdown("---")
                    st.markdown(f"**Description:**\n{task.description}")
        else:
            st.info("No tasks created yet.")
    else:
        st.warning("Database not available.")


# ── Runs Page ─────────────────────────────────────────────────
elif page == "🔄 Runs":
    st.header("🔄 Pipeline Runs")

    if db:
        runs = db.list_runs()
        if runs:
            selected_run_id = st.selectbox(
                "Select a run",
                [r.id for r in runs],
                format_func=lambda x: f"{x[:12]}... ({next((r.status for r in runs if r.id == x), 'unknown')})"
            )

            if selected_run_id:
                run = db.get_run(selected_run_id)
                if run:
                    st.subheader(f"Run: `{run.id[:12]}...`")

                    # Status and timeline
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Status", run.status.upper())
                    with col2:
                        st.metric("Current State", run.current_state)
                    with col3:
                        if run.started_at and run.finished_at:
                            duration = (run.finished_at - run.started_at).total_seconds()
                            st.metric("Duration", f"{duration:.1f}s")
                        else:
                            st.metric("Duration", "In progress..." if run.started_at else "Not started")

                    if run.error_message:
                        st.error(f"Error: {run.error_message}")

                    # Validation results
                    st.markdown("---")
                    st.subheader("✅ Validation Results")
                    validations = db.get_validation_results(selected_run_id)
                    if validations:
                        for v in validations:
                            icon = "✅" if v.passed else "❌"
                            st.markdown(
                                f"{icon} **{v.tool_name}**: {v.summary} "
                                f"({v.duration_seconds:.1f}s)"
                            )
                    else:
                        st.info("No validation results yet.")

                    # Artifacts
                    st.markdown("---")
                    st.subheader("📦 Artifacts")
                    artifacts_list = db.get_artifacts(selected_run_id)
                    if artifacts_list:
                        for a in artifacts_list:
                            with st.expander(f"📄 {a.artifact_type} — {Path(a.file_path).name}"):
                                try:
                                    if a.file_path.endswith(".json"):
                                        with open(a.file_path) as f:
                                            content = json.load(f)
                                        st.json(content)
                                    else:
                                        with open(a.file_path) as f:
                                            content = f.read()
                                        st.code(content)
                                except FileNotFoundError:
                                    st.warning("Artifact file not found on disk")
                    else:
                        st.info("No artifacts yet.")
        else:
            st.info("No runs yet.")
    else:
        st.warning("Database not available.")


# ── Metrics Page ──────────────────────────────────────────────
elif page == "📈 Metrics":
    st.header("📈 System Metrics & KPIs")

    if db:
        runs = db.list_runs(limit=1000)
        total = len(runs)

        if total > 0:
            completed = sum(1 for r in runs if r.status == "completed")
            failed = sum(1 for r in runs if r.status == "failed")
            blocked = sum(1 for r in runs if r.status == "blocked")
            awaiting = sum(1 for r in runs if r.status == "awaiting_approval")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Completion Rate", f"{completed/total*100:.1f}%")
            with col2:
                st.metric("Failure Rate", f"{failed/total*100:.1f}%")
            with col3:
                st.metric("Block Rate", f"{blocked/total*100:.1f}%")
            with col4:
                st.metric("Awaiting Review", awaiting)

            st.markdown("---")

            # Status distribution
            st.subheader("Run Status Distribution")
            status_counts = {}
            for r in runs:
                status_counts[r.status] = status_counts.get(r.status, 0) + 1

            st.bar_chart(status_counts)

        else:
            st.info("No runs to analyze yet.")
    else:
        st.warning("Database not available.")


# ── Policy Page ───────────────────────────────────────────────
elif page == "⚙️ Policy":
    st.header("⚙️ Policy Configuration")

    policy_path = "configs/policy.yaml"
    if Path(policy_path).exists():
        with open(policy_path) as f:
            policy_content = f.read()

        st.code(policy_content, language="yaml")

        st.markdown("---")
        st.subheader("Policy Sections")

        import yaml
        policy = yaml.safe_load(policy_content)

        for section, content in policy.items():
            with st.expander(f"📋 {section}", expanded=False):
                st.json(content)
    else:
        st.warning("Policy file not found.")
