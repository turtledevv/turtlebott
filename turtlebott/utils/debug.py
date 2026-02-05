import json
import ast

def debug_exception(e):
    print("Exception type:", type(e))
    print("Exception args:")
    print(e.args)

    # Try to find any dict inside args
    for i, arg in enumerate(e.args):
        if isinstance(arg, dict):
            print(f"\n[Found dict in args[{i}]]")
            print(json.dumps(arg, indent=2))
        else:
            print(f"\n[args[{i}] is not a dict]")
            print(arg)


import json
import re

def get_retry_and_code(e):
    if not e.args:
        return None, None

    data_str = e.args[0]

    # Extract the JSON-looking part after the status code
    match = re.search(r"\{.*\}", data_str, flags=re.DOTALL)
    if not match:
        return None, None

    json_like = match.group(0)

    # Convert single quotes to double quotes carefully
    # Also escape inner double quotes in the message
    json_like = json_like.replace("\\'", "'")  # un-escape any \'
    json_like = json_like.replace("'", '"')

    try:
        data = json.loads(json_like)
    except json.JSONDecodeError:
        return None, None

    error = data.get("error", {})
    code = error.get("code")

    # Drill down into details to find retryDelay
    retry_delay = None
    for detail in error.get("details", []):
        if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
            retry_delay = detail.get("retryDelay")
            break

    return code, retry_delay