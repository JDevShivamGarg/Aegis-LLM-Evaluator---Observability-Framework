import argparse
import sys
import time
import requests

def main():
    parser = argparse.ArgumentParser(description="Aegis CI/CD Regression Gating Runner")
    parser.add_argument("--suite_id", required=True, help="Test Suite UUID")
    parser.add_argument("--model_name", required=True, help="Target LLM model name")
    parser.add_argument("--prompt_version", required=True, help="Prompt version string")
    parser.add_argument("--threshold", type=float, default=0.8, help="Quality gating threshold (0.0 to 1.0)")
    parser.add_argument("--api_url", default="http://127.0.0.1:8000", help="Aegis API server URL")
    parser.add_argument("--timeout", type=int, default=90, help="Gating timeout in seconds")

    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    print(f"[INFO] Connecting to Aegis API: {api_url}")
    
    # 1. Trigger the run
    payload = {
        "suite_id": args.suite_id,
        "model_name": args.model_name,
        "prompt_version": args.prompt_version
    }
    
    try:
        response = requests.post(f"{api_url}/v1/runs", json=payload)
        response.raise_for_status()
        run_data = response.json()
    except Exception as e:
        print(f"[ERROR] Error triggering evaluation run: {e}", file=sys.stderr)
        sys.exit(2)

    run_id = run_data["run_id"]
    print(f"[SUCCESS] Triggered Run ID: {run_id}")
    print(f"[INFO] Polling evaluation status (gating threshold: {args.threshold})...")

    # 2. Poll for status
    start_time = time.time()
    while True:
        if (time.time() - start_time) > args.timeout:
            print("[ERROR] Gating error: Evaluation run timed out.", file=sys.stderr)
            sys.exit(2)

        try:
            status_resp = requests.get(f"{api_url}/v1/runs/{run_id}")
            status_resp.raise_for_status()
            status_data = status_resp.json()
        except Exception as e:
            print(f"[WARNING] Polling connection warning: {e}. Retrying in 2 seconds...")
            time.sleep(2)
            continue

        status = status_data["status"]
        print(f"  Current Status: {status}")

        if status == "COMPLETED":
            avg_score = status_data["average_score"]
            print("\n================ Aegis Evaluation Summary ================")
            print(f"Prompt Version : {args.prompt_version}")
            print(f"Target Model   : {args.model_name}")
            print(f"Average Score  : {avg_score:.4f}")
            print(f"Gating Limit   : {args.threshold:.4f}")
            print("==========================================================")

            if avg_score >= args.threshold:
                print("[PASS] PASS: Prompt quality is above the required gating limit.")
                sys.exit(0)
            else:
                print("[FAIL] FAIL: Quality regression detected. Prompt quality is below the gating limit.")
                sys.exit(1)

        elif status == "FAILED":
            print(f"[ERROR] Run {run_id} failed on the background worker.", file=sys.stderr)
            sys.exit(2)

        time.sleep(2)

if __name__ == "__main__":
    main()
