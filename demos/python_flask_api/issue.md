# Implement /add endpoint in Flask app

In `repo/app.py`, implement a route `/add` that accepts query parameters `a` and `b` (integers) and returns JSON `{ "result": a + b }` with status 200. If params are missing or invalid, return 400 with JSON `{ "error": "bad_request" }`.

Ensure tests pass with `python -m pytest`.
