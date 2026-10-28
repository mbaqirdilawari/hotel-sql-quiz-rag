"""Generate SQL with the Google Gemini API from the retrieved context."""

import re

# Tried in order until one works. gemini-3.1-flash-lite is fast (about one
# second) and on the free tier; "gemini-flash-latest" always points at
# Google's current Flash model and is the fallback. A specific model can be
# put first with the GEMINI_MODEL setting.
DEFAULT_MODELS = ["gemini-3.1-flash-lite", "gemini-flash-latest", "gemini-3-flash-preview"]

SYSTEM_INSTRUCTION = (
    "You are a PostgreSQL expert who turns questions about a hotel bookings "
    "database into SQL. Use ONLY the tables, columns, values and rules given in "
    "the retrieved context. Write exactly one read-only SELECT statement for "
    "PostgreSQL. Do not explain. Reply with the SQL inside a ```sql code block."
)

KIND_TITLES = {
    "schema": "Database schema",
    "semantics": "Business rules and data facts",
    "example": "Similar example questions with their SQL",
}


class GenerationError(Exception):
    pass


def build_prompt(question, retrieved):
    """Combine the retrieved documents and the question into one prompt."""
    sections = []
    for kind in ("schema", "semantics", "example"):
        texts = [r["text"] for r in retrieved if r["kind"] == kind]
        if texts:
            sections.append(f"## {KIND_TITLES[kind]}\n\n" + "\n\n".join(texts))
    context = "\n\n".join(sections)
    return (
        "# Retrieved context\n\n"
        f"{context}\n\n"
        "# Question\n\n"
        f"{question.strip()}\n\n"
        "Write the PostgreSQL query that answers the question."
    )


def extract_sql(text):
    """Pull the SQL out of the model reply (inside a code block if there is one)."""
    if not text:
        return ""
    match = re.search(r"```(?:sql|postgresql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    sql = match.group(1) if match else text
    sql = sql.strip()
    if sql and not sql.endswith(";"):
        sql += ";"
    return sql


REQUEST_TIMEOUT_MS = 45_000  # give up on one model after 45 seconds


def _make_client(genai, types, api_key):
    """Gemini client with a timeout and at most one retry, so a busy model
    fails fast and the next model is tried instead of waiting for minutes."""
    try:
        options = types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=2)
        )
        return genai.Client(api_key=api_key, http_options=options)
    except (AttributeError, TypeError):  # older or newer SDK without these options
        return genai.Client(api_key=api_key)


def generate_sql(api_key, question, retrieved, models=None):
    """Ask Gemini for SQL. Returns (sql, model_used, prompt, seconds)."""
    if not api_key:
        raise GenerationError("GEMINI_API_KEY is not set, so SQL cannot be generated.")

    import time

    from google import genai
    from google.genai import errors, types

    client = _make_client(genai, types, api_key)
    prompt = build_prompt(question, retrieved)
    config = types.GenerateContentConfig(temperature=0.0, system_instruction=SYSTEM_INSTRUCTION)

    last_error = None
    for model in [m for m in (models or DEFAULT_MODELS) if m]:
        started = time.monotonic()
        try:
            response = client.models.generate_content(model=model, contents=prompt, config=config)
        except errors.APIError as exc:
            code = getattr(exc, "code", None)
            print(f"[gemini] {model} failed after {time.monotonic() - started:.1f}s: {code}", flush=True)
            if code in (400, 401, 403) and "API key" in str(exc):
                raise GenerationError(f"Gemini rejected the API key: {exc}") from exc
            last_error = exc  # model missing, busy or rate-limited: try the next one
            continue
        except Exception as exc:  # timeout or network problem: try the next one
            print(f"[gemini] {model} error after {time.monotonic() - started:.1f}s: {exc}", flush=True)
            last_error = exc
            continue
        seconds = time.monotonic() - started
        print(f"[gemini] {model} answered in {seconds:.1f}s", flush=True)
        sql = extract_sql(response.text or "")
        if sql:
            return sql, model, prompt, seconds
        last_error = GenerationError(f"{model} returned an empty answer.")
    if getattr(last_error, "code", None) == 429:
        raise GenerationError("The Gemini free tier limit was reached. Wait a minute and try again.")
    raise GenerationError(f"No Gemini model could generate SQL. Last error: {last_error}")
