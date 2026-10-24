"""Reading what a form sent, without trusting it."""
from flask import abort, request

def wanted_state(name="to"):
    value = request.form.get(name)
    if value not in ("0", "1"):
        abort(400)
    return value == "1"

def confirmed():
    return request.form.get("sure") == "1"

def page_number(high, name="page"):
    return whole_number(request.args.get(name), 1, high, 1)

def whole_number(raw, low, high, default):
    try:
        number = int(raw)
    except (TypeError, ValueError):
        return default
    return number if low <= number <= high else default
