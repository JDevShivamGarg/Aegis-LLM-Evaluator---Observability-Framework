import re
import json
import jsonschema

def evaluate_rule(rule_type: str, rule_value: any, actual_output: str) -> tuple[float, str]:
    """
    Evaluates a single rule assertion on the actual output text.
    Returns:
        (score, explanation) -> score is 1.0 (pass) or 0.0 (fail).
    """
    if actual_output is None:
        return 0.0, "Actual output is missing/null."

    rule_type = rule_type.lower()
    
    try:
        if rule_type == "contains":
            target = str(rule_value)
            if target in actual_output:
                return 1.0, f"Passed: Output contains '{target}'."
            return 0.0, f"Failed: Output does not contain '{target}'."

        elif rule_type == "not_contains":
            target = str(rule_value)
            if target not in actual_output:
                return 1.0, f"Passed: Output does not contain '{target}'."
            return 0.0, f"Failed: Output contains '{target}'."

        elif rule_type == "regex":
            pattern = str(rule_value)
            if re.search(pattern, actual_output, re.IGNORECASE | re.DOTALL):
                return 1.0, f"Passed: Output matches regex pattern '{pattern}'."
            return 0.0, f"Failed: Output does not match regex pattern '{pattern}'."

        elif rule_type == "is_json":
            try:
                json.loads(actual_output)
                return 1.0, "Passed: Output is valid JSON."
            except json.JSONDecodeError as e:
                return 0.0, f"Failed: Output is not valid JSON. Error: {str(e)}"

        elif rule_type == "json_schema":
            try:
                data = json.loads(actual_output)
                jsonschema.validate(instance=data, schema=rule_value)
                return 1.0, "Passed: Output conforms to the JSON schema."
            except json.JSONDecodeError:
                return 0.0, "Failed: Output is not valid JSON, cannot validate schema."
            except jsonschema.ValidationError as e:
                return 0.0, f"Failed: Output JSON schema validation failed: {e.message}"

        else:
            return 0.0, f"Unknown rule type: '{rule_type}'."

    except Exception as e:
        return 0.0, f"Error executing rule check: {str(e)}"
