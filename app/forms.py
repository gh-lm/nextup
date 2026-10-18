"""Reading what a form sent, without trusting it."""
from flask import abort, request


def wanted_state(name="to"):
    """The state a toggle button asks for: True for "1", False for "0".

    Buttons say which state they want rather than "flip it", so a double click
    or a second tab repeats the same request instead of undoing it.
    """
    value = request.form.get(name)
    if value not in ("0", "1"):
        abort(400)
    return value == "1"


def page_number(high, name="page"):
    """The ?page= value, 1 when it is missing, odd or out of range."""
    return whole_number(request.args.get(name), 1, high, 1)


def whole_number(raw, low, high, default):
    """An integer from text, or `default` if it is not one or is out of range.

    str.isdigit() accepts characters such as a superscript two that int()
    then refuses, so the conversion itself is what is tried.
    """
    try:
        number = int(raw)
    except (TypeError, ValueError):
        return default
    return number if low <= number <= high else default
