import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
import os

# Page Configuration
st.set_page_config(
    page_title="Aegis Observability Platform",
    page_icon="shield",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Premium Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap');

    /* Global Typography and Background */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        font-family: 'Inter', sans-serif;
        background-color: #0b0e14 !important;
        color: #acb4c2;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', sans-serif;
        color: #f0f3f6 !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em;
    }
    
    /* Header layout styling */
    .title-container {
        padding: 1rem 0;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid #1a202c;
    }
    .platform-subtitle {
        color: #58a6ff;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        font-weight: 600;
        margin-bottom: 0.2rem;
    }
    
    /* Premium Metric Card Container */
    .metric-card {
        background: linear-gradient(135deg, #121721 0%, #0e121a 100%);
        border: 1px solid #1a2233;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: #388bfd;
        box-shadow: 0 8px 30px rgba(56, 139, 253, 0.1);
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #ffffff;
        font-family: 'Outfit', sans-serif;
        line-height: 1.2;
        margin-top: 5px;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #768390;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }
    
    /* Status Badge Styling */
    .badge {
        display: inline-block;
        padding: 4px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        border-radius: 20px;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    .badge-pass {
        background-color: rgba(46, 160, 67, 0.1);
        color: #46b856;
        border: 1px solid rgba(46, 160, 67, 0.25);
    }
    .badge-fail {
        background-color: rgba(244, 67, 54, 0.1);
        color: #f44336;
        border: 1px solid rgba(244, 67, 54, 0.25);
    }
    .badge-info {
        background-color: rgba(56, 139, 253, 0.1);
        color: #58a6ff;
        border: 1px solid rgba(56, 139, 253, 0.25);
    }

    /* Drilldown Expansion Styling */
    div.st-ae {
        background-color: #0f131a !important;
        border: 1px solid #1a202c !important;
        border-radius: 8px !important;
    }
    
    /* Code Blocks */
    code {
        color: #e6edf3 !important;
        background-color: #161b22 !important;
    }
</style>
""", unsafe_allow_html=True)

# Database Connection Pool
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/eval_db")
engine = create_engine(DATABASE_URL)

# Header Section
st.markdown("""
<div class="title-container">
    <div class="platform-subtitle">Aegis Observability Hub</div>
    <h1>System Evaluation Dashboard</h1>
</div>
""", unsafe_allow_html=True)

# === User Guide and Metrics Directory ===
with st.expander("📖 Dashboard User Guide & Metric Definitions", expanded=False):
    st.markdown("""
    ### How to Use This Dashboard
    1. **Context Selection**: Select a **Project** and **Test Suite** using the dropdowns above.
    2. **Multi-Tab Analysis**:
       - **Suite Overview**: Track version trendlines, select specific runs from the registry, and drill down into sentence output details and costs.
       - **A/B Comparison**: Select two evaluation runs side-by-side to view delta changes in score improvements or regressions.
       - **Regression Heatmap**: Look at the matrix plot visualizing the last 10 completed runs' scores case-by-case.
       - **Alert Configs**: Create and delete Slack/Discord/webhook alerts triggered on quality regressions.
    3. **Drill Down Case Tabs**: Switch between the **Case Tabs** in the Overview to inspect prompt inputs, actual outputs, and individual metric details.

    ---
    ### Metric Directory & Advanced Evaluators
    * **Quality Scores**: Aegis rating from `0.0` (fail/unsafe) to `1.0` (perfect/safe) calculated across:
      - **Rule Assertions**: Deterministic rule matches (regex, contains, not_contains, JSON).
      - **Semantic Similarity**: Cosine equivalence between actual and gold output using local `all-MiniLM-L6-v2`.
      - **LLM-As-Judge**: Multi-judge consensus rating averaging parallel judge completions to eliminate bias.
      - **Toxicity Check**: Safety rating leveraging local `unbiased-toxic-roberta` classification ($1.0 - \text{toxicity}$).
      - **RAG Grounding Score**: Cosine similarities of output sentences against retrieved source knowledge docs.
    * **Estimated Suite Cost**: Cumulative model API costs (in USD) derived from inputs/outputs tokens and database pricing rates.
    * **Pill Badges**:
      - <span class="badge badge-pass">PASS</span> Score $\ge$ 0.80 (Meets production quality standard).
      - <span class="badge badge-info">WARN</span> Score between 0.50 and 0.79 (Requires review).
      - <span class="badge badge-fail">FAIL</span> Score $<$ 0.50 (Regressed or violated safety policy).
    """, unsafe_allow_html=True)

# Load data helper functions
@st.cache_data(ttl=5)
def load_projects():
    with engine.connect() as conn:
        df = pd.read_sql_query("SELECT id, name FROM projects ORDER BY name", conn)
    return df

@st.cache_data(ttl=5)
def load_suites(project_id):
    with engine.connect() as conn:
        df = pd.read_sql_query(
            text("SELECT id, name FROM test_suites WHERE project_id = :proj_id ORDER BY name"),
            conn,
            params={"proj_id": project_id}
        )
    return df

def load_runs(suite_id):
    query = """
        SELECT r.id, r.model_name, r.prompt_version, r.status, r.created_at, r.completed_at,
               r.total_cost_usd,
               COUNT(res.id) as total_cases,
               COALESCE(AVG(sc.score), 0.0) as avg_score,
               COALESCE(AVG(res.latency_ms), 0.0) as avg_latency_ms,
               COALESCE(SUM(res.total_tokens), 0) as total_tokens
        FROM runs r
        LEFT JOIN test_results res ON r.id = res.run_id
        LEFT JOIN metric_scores sc ON res.id = sc.test_result_id
        WHERE r.suite_id = :suite_id
        GROUP BY r.id, r.total_cost_usd
        ORDER BY r.created_at DESC
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params={"suite_id": suite_id})
    return df

def load_run_results(run_id):
    query = """
        SELECT res.id as result_id, tc.input_prompt, tc.expected_output, res.actual_output,
               res.latency_ms, res.prompt_tokens, res.completion_tokens, res.total_tokens, 
               res.estimated_cost_usd, res.error_message
        FROM test_results res
        JOIN test_cases tc ON res.test_case_id = tc.id
        WHERE res.run_id = :run_id
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params={"run_id": run_id})
    return df

def load_result_scores(result_id):
    query = """
        SELECT metric_name, metric_type, score, explanation
        FROM metric_scores
        WHERE test_result_id = :result_id
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params={"result_id": result_id})
    return df

def load_ab_comparison(run_a_id, run_b_id):
    query = """
        SELECT tc.input_prompt, tc.expected_output,
               res_a.actual_output as actual_a, res_a.latency_ms as latency_a, res_a.estimated_cost_usd as cost_a,
               res_b.actual_output as actual_b, res_b.latency_ms as latency_b, res_b.estimated_cost_usd as cost_b,
               COALESCE(AVG(sc_a.score), 0.0) as score_a,
               COALESCE(AVG(sc_b.score), 0.0) as score_b
        FROM test_cases tc
        JOIN test_results res_a ON tc.id = res_a.test_case_id AND res_a.run_id = :run_a_id
        JOIN test_results res_b ON tc.id = res_b.test_case_id AND res_b.run_id = :run_b_id
        LEFT JOIN metric_scores sc_a ON res_a.id = sc_a.test_result_id
        LEFT JOIN metric_scores sc_b ON res_b.id = sc_b.test_result_id
        GROUP BY tc.id, tc.input_prompt, tc.expected_output,
                 res_a.actual_output, res_a.latency_ms, res_a.estimated_cost_usd,
                 res_b.actual_output, res_b.latency_ms, res_b.estimated_cost_usd
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params={"run_a_id": run_a_id, "run_b_id": run_b_id})
    return df

def load_heatmap_data(suite_id):
    runs_query = """
        SELECT id, prompt_version, model_name, created_at
        FROM runs
        WHERE suite_id = :suite_id AND status = 'COMPLETED'
        ORDER BY created_at ASC
        LIMIT 10
    """
    with engine.connect() as conn:
        runs_df = pd.read_sql(text(runs_query), conn, params={"suite_id": suite_id})
    
    if runs_df.empty:
        return pd.DataFrame()

    run_ids = list(runs_df["id"].values)
    run_ids_str = ", ".join([f"'{r}'" for r in run_ids])
    
    scores_query_formatted = f"""
        SELECT substring(tc.input_prompt from 1 for 40) || '...' as case_label, 
               r.prompt_version || ' (' || r.model_name || ')' as run_label, 
               COALESCE(AVG(sc.score), 0.0) as avg_score
        FROM test_results res
        JOIN runs r ON res.run_id = r.id
        JOIN test_cases tc ON res.test_case_id = tc.id
        LEFT JOIN metric_scores sc ON res.id = sc.test_result_id
        WHERE res.run_id IN ({run_ids_str})
        GROUP BY tc.id, tc.input_prompt, r.prompt_version, r.model_name, r.created_at
        ORDER BY r.created_at ASC
    """
    with engine.connect() as conn:
        scores_df = pd.read_sql(text(scores_query_formatted), conn)
        
    return scores_df

def load_alerts(suite_id):
    query = """
        SELECT id, channel, target_url, threshold, enabled
        FROM alert_configs
        WHERE suite_id = :suite_id
        ORDER BY created_at DESC
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params={"suite_id": suite_id})
    return df

def save_alert(suite_id, channel, url, threshold):
    query = """
        INSERT INTO alert_configs (suite_id, channel, target_url, threshold, enabled)
        VALUES (:suite_id, :channel, :url, :threshold, TRUE)
    """
    with engine.connect() as conn:
        conn.execute(text(query), {"suite_id": suite_id, "channel": channel, "url": url, "threshold": threshold})
        conn.commit()

def delete_alert(alert_id):
    query = "DELETE FROM alert_configs WHERE id = :alert_id"
    with engine.connect() as conn:
        conn.execute(text(query), {"alert_id": alert_id})
        conn.commit()

def load_prompt_versions(suite_id):
    query = """
        SELECT id, version_tag, template_body, description, created_at
        FROM prompt_versions
        WHERE suite_id = :suite_id
        ORDER BY created_at DESC
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params={"suite_id": suite_id})
    return df

def save_prompt_version(suite_id, version_tag, template_body, description):
    query = """
        INSERT INTO prompt_versions (suite_id, version_tag, template_body, description)
        VALUES (:suite_id, :version_tag, :template_body, :description)
    """
    with engine.connect() as conn:
        conn.execute(text(query), {"suite_id": suite_id, "version_tag": version_tag, "template_body": template_body, "description": description})
        conn.commit()

def delete_prompt_version(version_id):
    query = "DELETE FROM prompt_versions WHERE id = :version_id"
    with engine.connect() as conn:
        conn.execute(text(query), {"version_id": version_id})
        conn.commit()

# === Main Screen Context Selection (No Sidebar) ===
projects = load_projects()

if projects.empty:
    st.info("No projects found. Seed some data first.")
else:
    col_proj, col_suite = st.columns(2)
    
    with col_proj:
        selected_project_name = st.selectbox("Project Context", projects["name"])
        selected_project_id = projects[projects["name"] == selected_project_name]["id"].values[0]

    suites = load_suites(selected_project_id)
    if suites.empty:
        st.info("No test suites found for this project.")
    else:
        with col_suite:
            selected_suite_name = st.selectbox("Test Suite", suites["name"])
            selected_suite_id = suites[suites["name"] == selected_suite_name]["id"].values[0]

        # === Main Content ===
        runs = load_runs(selected_suite_id)
        
        if runs.empty:
            st.warning("No evaluation runs found.")
        else:
            completed_runs_df = runs[runs["status"] == "COMPLETED"].copy()
            total_runs_count = len(runs)
            completed_count = len(completed_runs_df)
            
            avg_score = completed_runs_df["avg_score"].mean() if completed_count > 0 else 0.0
            avg_latency = completed_runs_df["avg_latency_ms"].mean() if completed_count > 0 else 0.0
            total_cost = completed_runs_df["total_cost_usd"].sum() if completed_count > 0 else 0.0

            # Card grid layout
            col1, col2, col3, col4 = st.columns(4)
            
            col1.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Execution Count</div>
                <div class="metric-value">{total_runs_count}</div>
            </div>
            """, unsafe_allow_html=True)

            col2.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Mean Quality Score</div>
                <div class="metric-value">{avg_score:.3f}</div>
            </div>
            """, unsafe_allow_html=True)

            col3.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Mean Latency</div>
                <div class="metric-value">{avg_latency:.0f} ms</div>
            </div>
            """, unsafe_allow_html=True)

            col4.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Estimated Suite Cost</div>
                <div class="metric-value">${total_cost:.5f}</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # --- Multi-Tab Obervability Views ---
            st_tab_overview, st_tab_comparison, st_tab_heatmap, st_tab_alerts, st_tab_prompts = st.tabs([
                "📈 Suite Overview", "⚖️ A/B Comparison", "🎛️ Regression Heatmap", "🔔 Alert Configs", "📝 Prompt History"
            ])

            # TAB 1: OVERVIEW
            with st_tab_overview:
                st.subheader("Performance Trendline")
                if not completed_runs_df.empty:
                    completed_runs_df["date"] = pd.to_datetime(completed_runs_df["created_at"])
                    completed_runs_df = completed_runs_df.sort_values(by="date")
                    
                    fig = px.line(
                        completed_runs_df, 
                        x="date", 
                        y="avg_score", 
                        text="prompt_version",
                        labels={"avg_score": "Quality Score", "date": "Date"},
                        markers=True
                    )
                    fig.update_traces(line=dict(color="#388bfd", width=3, shape="spline"), marker=dict(size=8, color="#58a6ff"))
                    fig.update_layout(
                        template="plotly_dark",
                        plot_bgcolor="#0b0e14",
                        paper_bgcolor="#0b0e14",
                        margin=dict(l=40, r=40, t=20, b=40),
                        yaxis=dict(gridcolor="#1f242e", range=[0.0, 1.05]),
                        xaxis=dict(gridcolor="#1f242e")
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No completed run metrics to trend.")

                st.markdown("---")

                st.subheader("Run Registry")
                run_options = []
                for index, row in runs.iterrows():
                    label = f"Version: {row['prompt_version']} | Model: {row['model_name']} | Status: {row['status']} | Cost: ${row['total_cost_usd']:.5f}"
                    run_options.append((row["id"], label))

                selected_run_id = st.selectbox(
                    "Select run context to analyze:", 
                    run_options, 
                    key="run_reg_select",
                    format_func=lambda x: x[1]
                )[0]

                if selected_run_id:
                    results = load_run_results(selected_run_id)
                    if results.empty:
                        st.info("No results loaded for this run context.")
                    else:
                        st.markdown("<h4 style='margin-bottom:1.5rem;'>Evaluation Output Records</h4>", unsafe_allow_html=True)
                        tab_labels = [f"Case {i + 1}" for i in range(len(results))]
                        tabs = st.tabs(tab_labels)
                        
                        for idx, row in results.iterrows():
                            with tabs[idx]:
                                st.markdown(f"### Test Case Details")
                                col_case_a, col_case_b = st.columns([3, 2])
                                
                                with col_case_a:
                                    st.markdown("**Prompt Input**")
                                    st.code(row["input_prompt"], language="text")
                                    
                                    st.markdown("**Actual Response Output**")
                                    st.markdown(row["actual_output"])
                                    
                                    if row["expected_output"]:
                                        st.markdown("**Expected Output Reference**")
                                        st.markdown(row["expected_output"])
                                    
                                    st.markdown(
                                        f"<div style='font-size:0.8rem; color:#768390; margin-top:10px;'>Latency: {row['latency_ms']} ms | "
                                        f"Tokens: {row['total_tokens']} | Cost: ${row['estimated_cost_usd']:.5f}</div>",
                                        unsafe_allow_html=True
                                    )
                                    
                                with col_case_b:
                                    st.markdown("**Evaluations**")
                                    scores = load_result_scores(row["result_id"])
                                    if scores.empty:
                                        st.info("No scores resolved.")
                                    else:
                                        for _, score_row in scores.iterrows():
                                            score_val = score_row['score']
                                            if score_val >= 0.8:
                                                badge_class = "badge-pass"
                                                status_label = "PASS"
                                            elif score_val >= 0.5:
                                                badge_class = "badge-info"
                                                status_label = "WARN"
                                            else:
                                                badge_class = "badge-fail"
                                                status_label = "FAIL"
                                                
                                            st.markdown(
                                                f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;'>"
                                                f"<span>{score_row['metric_name']}</span>"
                                                f"<span class='badge {badge_class}'>{status_label} ({score_val:.2f})</span>"
                                                f"</div>",
                                                unsafe_allow_html=True
                                            )
                                            if score_row["explanation"]:
                                                st.markdown(f"<div style='font-size:0.85rem; color:#8b949e; margin-bottom:12px; font-style:italic;'>{score_row['explanation']}</div>", unsafe_allow_html=True)

            # TAB 2: A/B COMPARISON
            with st_tab_comparison:
                st.subheader("Side-by-Side Prompt Version Compare")
                
                # Check if we have at least 2 runs to compare
                if len(runs) < 2:
                    st.info("Requires at least 2 completed runs to perform comparison analysis.")
                else:
                    col_run_a, col_run_b = st.columns(2)
                    run_choices = [(row["id"], f"v: {row['prompt_version']} ({row['model_name']})") for _, row in runs.iterrows()]
                    
                    with col_run_a:
                        run_a_id = st.selectbox("Baseline Run (A)", run_choices, format_func=lambda x: x[1], key="comp_run_a")[0]
                    with col_run_b:
                        run_b_id = st.selectbox("Comparison Run (B)", run_choices, index=1, format_func=lambda x: x[1], key="comp_run_b")[0]
                    
                    if run_a_id and run_b_id:
                        comp_df = load_ab_comparison(run_a_id, run_b_id)
                        
                        if comp_df.empty:
                            st.info("No common test cases found between these run versions.")
                        else:
                            for idx, row in comp_df.iterrows():
                                with st.container():
                                    st.markdown(f"#### Case {idx+1}: {row['input_prompt'][:60]}...")
                                    
                                    # Render scores delta
                                    delta = row["score_b"] - row["score_a"]
                                    if delta > 0:
                                        delta_color = "#46b856"
                                        delta_txt = f"+{delta:.3f} Improvement"
                                    elif delta < 0:
                                        delta_color = "#f44336"
                                        delta_txt = f"{delta:.3f} Regression"
                                    else:
                                        delta_color = "#8b949e"
                                        delta_txt = "No change"
                                        
                                    st.markdown(
                                        f"Quality: **Run A**: {row['score_a']:.3f} | **Run B**: {row['score_b']:.3f} "
                                        f"(<span style='color:{delta_color}; font-weight:600;'>{delta_txt}</span>)",
                                        unsafe_allow_html=True
                                    )
                                    
                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        st.markdown("**Run A Output**")
                                        st.markdown(row["actual_a"])
                                        st.caption(f"Latency: {row['latency_a']}ms | Cost: ${row['cost_a']:.5f}")
                                    with col_b:
                                        st.markdown("**Run B Output**")
                                        st.markdown(row["actual_b"])
                                        st.caption(f"Latency: {row['latency_b']}ms | Cost: ${row['cost_b']:.5f}")
                                    st.markdown("---")

            # TAB 3: REGRESSION HEATMAP
            with st_tab_heatmap:
                st.subheader("Historical Quality Heatmap Matrix")
                heatmap_df = load_heatmap_data(selected_suite_id)
                
                if heatmap_df.empty:
                    st.info("Need completed runs metrics to generate heatmap.")
                else:
                    # Pivot into matrix
                    pivot_df = heatmap_df.pivot(index="case_label", columns="run_label", values="avg_score")
                    
                    fig_heat = px.imshow(
                        pivot_df,
                        labels=dict(x="Runs", y="Test Cases", color="Avg Score"),
                        color_continuous_scale="RdYlGn",
                        zmin=0.0,
                        zmax=1.0,
                        text_auto=".2f"
                    )
                    fig_heat.update_layout(
                        template="plotly_dark",
                        plot_bgcolor="#0b0e14",
                        paper_bgcolor="#0b0e14",
                        margin=dict(l=40, r=40, t=20, b=40)
                    )
                    st.plotly_chart(fig_heat, use_container_width=True)

            # TAB 4: ALERT CONFIGS
            with st_tab_alerts:
                st.subheader("Active Regression Webhooks alerting")
                
                # Render Add form
                with st.form("add_alert_form"):
                    st.markdown("**Create Webhook Alert**")
                    col_alert_a, col_alert_b = st.columns([1, 3])
                    with col_alert_a:
                        channel = st.selectbox("Alert Channel", ["Slack", "Discord", "Webhook"])
                    with col_alert_b:
                        target_url = st.text_input("Webhook target Destination URL", placeholder="https://hooks.slack.com/services/...")
                        
                    threshold_val = st.slider("Quality score Threshold Gating", 0.0, 1.0, 0.85, 0.05)
                    submit = st.form_submit_button("Register Alert Target")
                    
                    if submit:
                        if not target_url:
                            st.error("Target Webhook URL is required.")
                        else:
                            save_alert(selected_suite_id, channel, target_url, threshold_val)
                            st.success(f"Registered {channel} Alert Webhook successfully!")
                            st.rerun()

                st.markdown("---")
                
                # List active alerts
                alert_list = load_alerts(selected_suite_id)
                if alert_list.empty:
                    st.info("No alert targets configured for this test suite.")
                else:
                    for _, alert_row in alert_list.iterrows():
                        col_info, col_del = st.columns([5, 1])
                        with col_info:
                            st.markdown(
                                f"**Channel**: `{alert_row['channel']}` | **Threshold**: `{alert_row['threshold']:.2f}` | "
                                f"**Destination URL**: `{alert_row['target_url'][:50]}...`"
                            )
                        with col_del:
                            if st.button("Delete Target", key=f"del_{alert_row['id']}"):
                                delete_alert(alert_row["id"])
                                st.success("Alert target deleted successfully!")
                                st.rerun()

            # TAB 5: PROMPT HISTORY
            with st_tab_prompts:
                st.subheader("Prompt Template History & Version Diffs")
                
                # Render Register Prompt Version Form
                with st.form("register_prompt_form"):
                    st.markdown("**Register New Prompt Version**")
                    col_tag, col_desc = st.columns([1, 2])
                    with col_tag:
                        version_tag = st.text_input("Version Tag", placeholder="e.g. v1.4-rag")
                    with col_desc:
                        prompt_desc = st.text_input("Version Description", placeholder="Optional description of template adjustments")
                    
                    template_body = st.text_area("Prompt Template Body", height=150, placeholder="Write your system or user prompt template here...")
                    submit = st.form_submit_button("Register Prompt Version")
                    
                    if submit:
                        if not version_tag or not template_body:
                            st.error("Version Tag and Prompt Template Body are required.")
                        else:
                            save_prompt_version(selected_suite_id, version_tag, template_body, prompt_desc)
                            st.success(f"Registered prompt version {version_tag} successfully!")
                            st.rerun()

                st.markdown("---")

                # Comparison visualizer section
                versions_df = load_prompt_versions(selected_suite_id)
                if versions_df.empty:
                    st.info("No prompt versions registered for this test suite.")
                else:
                    st.markdown("### Compare Prompt Templates")
                    
                    # Choose A and B versions
                    col_v_a, col_v_b = st.columns(2)
                    version_choices = [(row["id"], f"{row['version_tag']} ({row['created_at'].strftime('%Y-%m-%d %H:%M')})") for _, row in versions_df.iterrows()]
                    
                    with col_v_a:
                        sel_v_a = st.selectbox("Baseline Version (A)", version_choices, format_func=lambda x: x[1], key="diff_v_a")[0]
                    with col_v_b:
                        sel_v_b = st.selectbox("Comparison Version (B)", version_choices, index=min(1, len(version_choices)-1), format_func=lambda x: x[1], key="diff_v_b")[0]
                    
                    if sel_v_a and sel_v_b:
                        row_a = versions_df[versions_df["id"] == sel_v_a].iloc[0]
                        row_b = versions_df[versions_df["id"] == sel_v_b].iloc[0]
                        
                        st.markdown(f"Comparing `{row_a['version_tag']}` (A) vs `{row_b['version_tag']}` (B):")
                        
                        # Generate and render colorized diff
                        import difflib
                        diff = list(difflib.ndiff(row_a["template_body"].splitlines(), row_b["template_body"].splitlines()))
                        html_diff = []
                        for line in diff:
                            if line.startswith("+ "):
                                html_diff.append(f"<div style='color: #46b856; background-color: rgba(46, 160, 67, 0.15); font-family: monospace; padding: 2px 4px; white-space: pre-wrap;'>{line}</div>")
                            elif line.startswith("- "):
                                html_diff.append(f"<div style='color: #f44336; background-color: rgba(244, 67, 54, 0.15); font-family: monospace; padding: 2px 4px; white-space: pre-wrap;'>{line}</div>")
                            elif line.startswith("? "):
                                continue
                            else:
                                html_diff.append(f"<div style='color: #8b949e; font-family: monospace; padding: 2px 4px; white-space: pre-wrap;'>{line}</div>")
                                
                        st.markdown(
                            f"<div style='background-color: #0b0e14; border: 1px solid #1f242e; border-radius: 6px; padding: 10px; max-height: 400px; overflow-y: auto; margin-bottom: 20px;'>{''.join(html_diff)}</div>",
                            unsafe_allow_html=True
                        )

                    st.markdown("---")
                    st.markdown("### Version Registry History")
                    for _, v_row in versions_df.iterrows():
                        col_v_info, col_v_del = st.columns([5, 1])
                        with col_v_info:
                            st.markdown(f"**Version**: `{v_row['version_tag']}` | **Date**: `{v_row['created_at'].strftime('%Y-%m-%d %H:%M')}`")
                            if v_row['description']:
                                st.caption(f"Description: {v_row['description']}")
                            with st.expander("View Template Body"):
                                st.code(v_row["template_body"], language="text")
                        with col_v_del:
                            if st.button("Delete Version", key=f"del_v_{v_row['id']}"):
                                delete_prompt_version(v_row["id"])
                                st.success("Prompt version deleted successfully!")
                                st.rerun()
