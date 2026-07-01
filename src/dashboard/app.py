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
    1. **Context Selection**: Use the **Project** and **Test Suite** dropdowns at the top of the screen.
    2. **Track Regression Trends**: Observe the **Performance Trendline** to monitor if prompt/model updates caused quality drops.
    3. **Run Analysis**: Select a specific run version from the **Run Registry** dropdown to drill down into case outcomes.
    4. **Inspect Test Cases**: Switch between the horizontal **Case Tabs** below to isolate individual outputs and scoring metrics.

    ---
    ### Metric Directory
    * **Execution Count**: Total enqueued evaluation tasks initiated.
    * **Completed Runs**: Evaluation suites successfully completed by Celery.
    * **Mean Quality Score**: The aggregated quality rating (0.0 to 1.0) averaged across all completed cases.
    * **Mean Latency**: Average roundtrip time (in milliseconds) of target LLM and evaluator API execution.
    * **Pill Badges**:
      - <span class="badge badge-pass">PASS</span> Score $\ge$ 0.80 (Matches expected standards).
      - <span class="badge badge-info">WARN</span> Score between 0.50 and 0.79 (Requires attention).
      - <span class="badge badge-fail">FAIL</span> Score $<$ 0.50 (Violates rules or assertion limits).
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
               COUNT(res.id) as total_cases,
               COALESCE(AVG(sc.score), 0.0) as avg_score,
               COALESCE(AVG(res.latency_ms), 0.0) as avg_latency_ms,
               COALESCE(SUM(res.total_tokens), 0) as total_tokens
        FROM runs r
        LEFT JOIN test_results res ON r.id = res.run_id
        LEFT JOIN metric_scores sc ON res.id = sc.test_result_id
        WHERE r.suite_id = :suite_id
        GROUP BY r.id
        ORDER BY r.created_at DESC
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params={"suite_id": suite_id})
    return df

def load_run_results(run_id):
    query = """
        SELECT res.id as result_id, tc.input_prompt, tc.expected_output, res.actual_output,
               res.latency_ms, res.prompt_tokens, res.completion_tokens, res.total_tokens, res.error_message
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
            # 1. Premium Custom Cards Layout
            completed_runs_df = runs[runs["status"] == "COMPLETED"].copy()
            total_runs_count = len(runs)
            completed_count = len(completed_runs_df)
            
            avg_score = completed_runs_df["avg_score"].mean() if completed_count > 0 else 0.0
            avg_latency = completed_runs_df["avg_latency_ms"].mean() if completed_count > 0 else 0.0
            total_tokens = completed_runs_df["total_tokens"].sum() if completed_count > 0 else 0

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
                <div class="metric-label">Completed Runs</div>
                <div class="metric-value">{completed_count}</div>
            </div>
            """, unsafe_allow_html=True)

            col3.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Mean Quality Score</div>
                <div class="metric-value">{avg_score:.3f}</div>
            </div>
            """, unsafe_allow_html=True)

            col4.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Mean Latency</div>
                <div class="metric-value">{avg_latency:.0f} ms</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")

            # 2. Charts Section
            st.subheader("Performance Trendline")
            if not completed_runs_df.empty:
                completed_runs_df["date"] = pd.to_datetime(completed_runs_df["created_at"])
                completed_runs_df = completed_runs_df.sort_values(by="date")
                
                # Make curve line chart
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
                    plot_bgcolor="#0c0f16",
                    paper_bgcolor="#0c0f16",
                    margin=dict(l=40, r=40, t=20, b=40),
                    yaxis=dict(gridcolor="#1f242e", range=[0.0, 1.05]),
                    xaxis=dict(gridcolor="#1f242e")
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No completed run metrics to trend.")

            st.markdown("---")

            # 3. Drill Down Selector
            st.subheader("Run Registry")
            run_options = []
            for index, row in runs.iterrows():
                label = f"Version: {row['prompt_version']} | Model: {row['model_name']} | Status: {row['status']} | Date: {row['created_at'].strftime('%Y-%m-%d %H:%M')}"
                run_options.append((row["id"], label))

            selected_run_id, _ = st.selectbox(
                "Select run context to analyze:", 
                run_options, 
                format_func=lambda x: x[1]
            )

            # 4. Tab-Based Case drill down
            if selected_run_id:
                results = load_run_results(selected_run_id)

                if results.empty:
                    st.info("No results loaded for this run context.")
                else:
                    st.markdown("<h4 style='margin-bottom:1.5rem;'>Evaluation Output Records</h4>", unsafe_allow_html=True)
                    
                    # Create Tabs dynamically for each test case
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
                                st.code(row["actual_output"], language="text")
                                
                                if row["expected_output"]:
                                    st.markdown("**Expected Output Reference**")
                                    st.code(row["expected_output"], language="text")
                                
                                st.markdown(
                                    f"<div style='font-size:0.8rem; color:#768390; margin-top:10px;'>Latency: {row['latency_ms']} ms | "
                                    f"Prompt Tokens: {row['prompt_tokens']} | Completion Tokens: {row['completion_tokens']}</div>",
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
                                        
                                        # Clean badge selection
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
