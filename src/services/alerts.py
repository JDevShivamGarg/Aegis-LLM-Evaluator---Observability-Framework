import json
import requests
from sqlalchemy.orm import Session
from src.core.models import Run, AlertConfig, TestSuite

def check_and_dispatch_alerts(db: Session, run_id: str, average_score: float) -> list[str]:
    """
    Checks if a completed run's average score has dropped below
    configured alert thresholds for the suite, and dispatches webhooks.
    """
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        return []

    suite = db.query(TestSuite).filter(TestSuite.id == run.suite_id).first()
    if not suite:
        return []

    # Get active alert configurations for this suite
    alerts = db.query(AlertConfig).filter(
        AlertConfig.suite_id == run.suite_id,
        AlertConfig.enabled == True
    ).all()

    dispatched = []
    for alert in alerts:
        if average_score < alert.threshold:
            try:
                # Format payload details
                message_title = f"🚨 Aegis Quality Regression Alert: {suite.name}"
                message_body = (
                    f"**Run ID**: `{run.id}`\n"
                    f"**Prompt Version**: `{run.prompt_version}`\n"
                    f"**Target Model**: `{run.model_name}`\n"
                    f"**Triggered By**: `{run.triggered_by or 'System'}`\n\n"
                    f"**Quality Score**: `{average_score:.4f}` (Threshold: `{alert.threshold:.2f}`)\n"
                    f"⚠️ **Regression detected!** Quality is below set standard."
                )

                if alert.channel.lower() in ("slack", "discord", "webhook"):
                    # Format as JSON webhook payload
                    if alert.channel.lower() == "slack":
                        payload = {
                            "text": f"{message_title}\n{message_body}"
                        }
                    elif alert.channel.lower() == "discord":
                        payload = {
                            "content": f"**{message_title}**\n{message_body}"
                        }
                    else:
                        # Generic webhook payload
                        payload = {
                            "event": "aegis_regression",
                            "suite_id": str(suite.id),
                            "suite_name": suite.name,
                            "run_id": str(run.id),
                            "model_name": run.model_name,
                            "prompt_version": run.prompt_version,
                            "average_score": average_score,
                            "threshold": alert.threshold
                        }

                    # Post to URL
                    response = requests.post(
                        alert.target_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=5
                    )
                    
                    log_msg = f"Dispatched alert to {alert.channel} URL: {alert.target_url}. Response code: {response.status_code}"
                    print(log_msg)
                    dispatched.append(log_msg)
            except Exception as e:
                err_msg = f"Failed to dispatch {alert.channel} alert: {e}"
                print(err_msg)
                dispatched.append(err_msg)
                
    return dispatched
