"""Generate SQL with the Google Gemini API from the retrieved context."""

import re

# Tried in order until one works. The first entry can be overridden with
# the GEMINI_MODEL setting; "gemini-flash-latest" always points at Google's
# current Flash model, and the others are fallbacks with a free tier.
DEFAULT_MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-3.1-flash-lite"]

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


def generate_sql(api_key, question, retrieved, models=None):
    """Ask Gemini for SQL. Returns (sql, model_used, prompt)."""
    if not api_key:
        raise GenerationError("GEMINI_API_KEY is not set, so SQL cannot be generated.")

    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=api_key)
    prompt = build_prompt(question, retrieved)
    config = types.GenerateContentConfig(temperature=0.0, system_instruction=SYSTEM_INSTRUCTION)

    last_error = None
    for model in [m for m in (models or DEFAULT_MODELS) if m]:
        try:
            response = client.models.generate_content(model=model, contents=prompt, config=config)
        except errors.APIError as exc:
            code = getattr(exc, "code", None)
            if code == 429:
                raise GenerationError(
                    "The Gemini free tier limit was reached. Wait a minute and try again."
                ) from exc
            if code in (400, 401, 403) and "API key" in str(exc):
                raise GenerationError(f"Gemini rejected the API key: {exc}") from exc
            last_error = exc  # for example, model not found: try the next one
            continue
        sql = extract_sql(response.text or "")
        if sql:
            return sql, model, prompt
        last_error = GenerationError(f"{model} returned an empty answer.")
    raise GenerationError(f"No Gemini model could generate SQL. Last error: {last_error}")
