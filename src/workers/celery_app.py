import time
import uuid
import json
import hashlib
import redis
from celery import Celery
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from src.core.config import settings
from src.core.database import SessionLocal
from sqlalchemy import func, Column
from src.core.models import Run, TestResult, MetricScore, TestCase, TestSuite
from src.services.rules import evaluate_rule
from src.services.similarity import EmbeddingSimilarityEvaluator
from src.services.judge import LLMJudgeEvaluator
from src.services.plugin_registry import load_custom_plugins
from src.services.cost_tracker import calculate_token_cost
from src.services.alerts import check_and_dispatch_alerts
from src.core.otel_tracer import trace_span

celery = Celery(
    "aegis_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=settings.CELERY_CONCURRENCY,
)

_similarity_evaluator = None

def get_similarity_evaluator():
    global _similarity_evaluator
    if _similarity_evaluator is None:
        try:
            print("Loading SentenceTransformer model lazily...")
            similarity_model = SentenceTransformer(settings.EMBEDDING_MODEL_PATH)
            _similarity_evaluator = EmbeddingSimilarityEvaluator(similarity_model)
            print("SentenceTransformer model loaded successfully.")
        except Exception as e:
            print(f"Error loading SentenceTransformer: {e}")
            _similarity_evaluator = None
    return _similarity_evaluator

def call_target_llm(model_name: str, prompt: str) -> tuple[str, int, int, int, int]:
    """
    Calls the target LLM model.
    Returns: (actual_output, prompt_tokens, completion_tokens, total_tokens, latency_ms)
    """
    # Decide client based on model prefix
    is_openai = model_name.lower().startswith("gpt")
    
    if is_openai:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
    else:
        # Default to Groq using the OpenAI SDK client mapping
        client = OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )
        # Fallback to standard Groq model if the name is generic
        if not model_name or model_name == "default":
            model_name = "llama-3.1-8b-instant"

    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1000
        )
        latency_ms = int((time.time() - start_time) * 1000)
        
        actual_output = response.choices[0].message.content
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0
        
        return actual_output, prompt_tokens, completion_tokens, total_tokens, latency_ms
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        return f"Error executing target LLM: {str(e)}", 0, 0, 0, latency_ms

@celery.task(name="src.workers.celery_app.run_evaluation")
def run_evaluation(run_id_str: str) -> str:
    """
    Main evaluation pipeline:
    1. Fetches run configuration and test cases.
    2. Runs target LLM prompts.
    3. Calculates assertions, similarity, and judge scores.
    4. Persists outcomes to PostgreSQL database.
    """
    db = SessionLocal()
    run_id = uuid.UUID(run_id_str)
    
    try:
        # Fetch the run details
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return f"Run {run_id_str} not found in database."
        
        run.status = "RUNNING"
        db.commit()

        # Fetch cases for the test suite
        cases = db.query(TestCase).filter(TestCase.suite_id == run.suite_id).all()
        if not cases:
            run.status = "COMPLETED"
            import datetime
            run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            db.commit()
            return f"No test cases found for suite {run.suite_id}."

        # Fetch test suite configuration
        suite = db.query(TestSuite).filter(TestSuite.id == run.suite_id).first()

        # Setup LLM Judges (Multi-Judge Consensus support)
        judges = []
        judge_config = getattr(suite, "judge_config", []) or []
        if isinstance(judge_config, list) and len(judge_config) > 0:
            for j_cfg in judge_config:
                judges.append(LLMJudgeEvaluator(
                    provider=j_cfg.get("provider", "groq"),
                    model=j_cfg.get("model"),
                    api_key=j_cfg.get("api_key"),
                    base_url=j_cfg.get("base_url")
                ))
        else:
            judge_provider = "groq" if settings.GROQ_API_KEY != "gsk-placeholder" else "openai"
            judges.append(LLMJudgeEvaluator(provider=judge_provider))

        # Load Custom Evaluator Plugins
        custom_plugins = load_custom_plugins()

        # Setup Redis Client for result caching
        r_client = None
        try:
            r_client = redis.from_url(settings.REDIS_URL)
        except Exception as r_err:
            print(f"[Aegis Cache] Failed to connect to Redis cache: {r_err}")

        for case in cases:
            # Check Caching & Deduplication
            cache_hit = False
            actual_output = None
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            latency_ms = 0
            cost_usd = 0.0

            cache_key = None
            if r_client:
                try:
                    rules_str = json.dumps(case.assertion_rules or [], sort_keys=True)
                    cache_input = f"{run.model_name}:{run.prompt_version}:{case.input_prompt}:{rules_str}"
                    cache_key = f"aegis:cache:{hashlib.sha256(cache_input.encode('utf-8')).hexdigest()}"
                    
                    cached_val = r_client.get(cache_key)
                    if cached_val:
                        cache_data = json.loads(cached_val.decode("utf-8"))
                        actual_output = cache_data.get("actual_output")
                        prompt_tokens = cache_data.get("prompt_tokens", 0)
                        completion_tokens = cache_data.get("completion_tokens", 0)
                        total_tokens = cache_data.get("total_tokens", 0)
                        latency_ms = cache_data.get("latency_ms", 0)
                        cost_usd = cache_data.get("estimated_cost_usd", 0.0)
                        cache_hit = True
                        print(f"[Aegis Cache] Cache Hit for prompt: {case.input_prompt[:30]}...")
                except Exception as c_err:
                    print(f"[Aegis Cache] Read error: {c_err}")

            if not cache_hit:
                # 1. Execute Target LLM Call
                actual_output, prompt_tokens, completion_tokens, total_tokens, latency_ms = call_target_llm(
                    model_name=run.model_name,
                    prompt=case.input_prompt
                )

                # Calculate token cost
                cost_usd = calculate_token_cost(db, run.model_name, prompt_tokens, completion_tokens)

                # Write to Redis Cache (24h TTL)
                if r_client and cache_key:
                    try:
                        cache_payload = {
                            "actual_output": actual_output,
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                            "latency_ms": latency_ms,
                            "estimated_cost_usd": cost_usd
                        }
                        r_client.setex(cache_key, 86400, json.dumps(cache_payload))
                    except Exception as c_err:
                        print(f"[Aegis Cache] Write error: {c_err}")

            # 2. Create Test Result record
            result = TestResult(
                id=uuid.uuid4(),
                run_id=run.id,
                test_case_id=case.id,
                actual_output=actual_output,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=cost_usd,
                cache_hit=cache_hit
            )
            db.add(result)
            db.flush()  # Generate result.id for foreign keys

            # 3. Evaluate Rule-based Assertions
            assertion_rules = case.assertion_rules
            if isinstance(assertion_rules, list):
                with trace_span("aegis.rule_assertion", {"rule_count": len(assertion_rules)}):
                    for rule in assertion_rules:
                        rule_type = rule.get("type")
                        rule_value = rule.get("value")
                        if rule_type:
                            score, explanation = evaluate_rule(rule_type, rule_value, actual_output)
                            metric_score = MetricScore(
                                id=uuid.uuid4(),
                                test_result_id=result.id,
                                metric_name=f"Rule: {rule_type}",
                                metric_type="RULE_ASSERTION",
                                score=score,
                                explanation=explanation
                            )
                            db.add(metric_score)

            # 4. Evaluate Semantic Embedding Similarity (if expected output matches)
            if case.expected_output:
                with trace_span("aegis.embedding_similarity"):
                    evaluator = get_similarity_evaluator()
                    if evaluator:
                        similarity = evaluator.score(case.expected_output, actual_output)
                        metric_score = MetricScore(
                            id=uuid.uuid4(),
                            test_result_id=result.id,
                            metric_name="Semantic Similarity",
                            metric_type="EMBEDDING_SIMILARITY",
                            score=similarity,
                            explanation=f"Cosine similarity between expected and actual output is {similarity:.4f}."
                        )
                        db.add(metric_score)

            # 5. Evaluate Custom Plugins (Toxicity, Grounding, etc.)
            enabled_custom_evals = getattr(suite, "custom_evaluators", []) or []
            for plugin in custom_plugins:
                run_plugin = False
                if isinstance(enabled_custom_evals, list) and len(enabled_custom_evals) > 0:
                    if plugin.metric_name in enabled_custom_evals:
                        run_plugin = True
                else:
                    # Default/Fallback heuristic if test suite custom_evaluators is empty:
                    if plugin.metric_name == "RAG Grounding Score":
                        # Only run grounding check if case context_documents are populated
                        context_docs = getattr(case, "context_documents", None)
                        if isinstance(context_docs, list) and len(context_docs) > 0:
                            run_plugin = True
                    else:
                        # Enable general safety checkers (like Toxicity) by default
                        run_plugin = True

                if run_plugin:
                    with trace_span(f"aegis.plugin.{plugin.metric_name}"):
                        try:
                            context_docs = getattr(case, "context_documents", None) or []
                            plugin_score, plugin_explanation = plugin.score(
                                prompt=case.input_prompt,
                                expected=case.expected_output or "",
                                actual=actual_output,
                                context_documents=context_docs
                            )
                            metric_score = MetricScore(
                                id=uuid.uuid4(),
                                test_result_id=result.id,
                                metric_name=plugin.metric_name,
                                metric_type=plugin.metric_type,
                                score=plugin_score,
                                explanation=plugin_explanation
                            )
                            db.add(metric_score)
                        except Exception as plugin_err:
                            print(f"Error running custom plugin {plugin.metric_name}: {plugin_err}")

            # 6. Evaluate via LLM-As-Judge (Multi-Judge Consensus support)
            with trace_span("aegis.llm_judge", {"judges_count": len(judges)}):
                judge_scores = []
                judge_explanations = []
                for j_idx, j_evaluator in enumerate(judges):
                    j_score, j_explanation = j_evaluator.judge(
                        prompt=case.input_prompt,
                        expected=case.expected_output,
                        actual=actual_output
                    )
                    judge_scores.append(j_score)
                    judge_explanations.append(f"Judge {j_idx + 1} ({j_evaluator.model}): Score={j_score}. {j_explanation}")

                consensus_score = sum(judge_scores) / len(judge_scores)
                combined_explanation = "\n\n".join(judge_explanations)

                metric_score = MetricScore(
                    id=uuid.uuid4(),
                    test_result_id=result.id,
                    metric_name="LLM-As-Judge",
                    metric_type="LLM_JUDGE",
                    score=consensus_score,
                    explanation=combined_explanation
                )
                db.add(metric_score)

        db.flush()

        # Sum up all result costs and update run total cost
        total_cost = db.query(func.sum(TestResult.estimated_cost_usd)).filter(TestResult.run_id == run.id).scalar()
        run.total_cost_usd = float(total_cost) if total_cost is not None else 0.0

        # Get average quality score for alerting evaluation
        avg_score_query = db.query(func.avg(MetricScore.score))\
                            .join(TestResult, MetricScore.test_result_id == TestResult.id)\
                            .filter(TestResult.run_id == run.id)\
                            .scalar()
        avg_score = float(avg_score_query) if avg_score_query is not None else 0.0

        # Update run status
        import datetime
        run.status = "COMPLETED"
        run.completed_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()

        # Dispatch regression webhooks alerting
        try:
            check_and_dispatch_alerts(db, str(run.id), avg_score)
        except Exception as alert_err:
            print(f"Alerting dispatch failed: {alert_err}")

        return f"Run {run_id_str} completed successfully."

    except Exception as e:
        db.rollback()
        try:
            run = db.query(Run).filter(Run.id == run_id).first()
            if run:
                run.status = "FAILED"
                db.commit()
        except Exception:
            pass
        return f"Run {run_id_str} failed with error: {str(e)}"
    finally:
        db.close()

# Keep placeholder for backwards compatibility
@celery.task(name="src.workers.celery_app.test_task")
def test_task(x: int, y: int) -> int:
    return x + y
