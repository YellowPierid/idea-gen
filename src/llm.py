import json
import logging
from typing import TypeVar, Type

from openai import OpenAI
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("idea_gen")

T = TypeVar("T", bound=BaseModel)


def create_client(base_url: str, api_key: str) -> OpenAI:
    """Create OpenAI-compatible client for OpenRouter."""
    return OpenAI(base_url=base_url, api_key=api_key)


def call_llm(
    client: OpenAI,
    model: str,
    temperature: float,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Make a single LLM call and return the raw text response."""
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""


def call_llm_structured(
    client: OpenAI,
    model: str,
    temperature: float,
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    repair_model: str | None = None,
    repair_temperature: float = 0.0,
) -> T | None:
    """Call LLM and parse response into a Pydantic model.

    On validation failure, attempts schema repair with the repair model.
    Returns None if both primary and repair fail.
    """
    raw = call_llm(client, model, temperature, system_prompt, user_prompt)

    # Try to parse the response
    parsed = _try_parse(raw, schema)
    if parsed is not None:
        return parsed

    # Primary parse failed -- attempt repair if repair model is configured
    if repair_model is None:
        logger.warning("Schema parse failed and no repair model configured")
        return None

    logger.info("Attempting schema repair with %s", repair_model)
    repaired = _attempt_repair(client, repair_model, repair_temperature, raw, schema)
    return repaired


def _try_parse(raw: str, schema: Type[T]) -> T | None:
    """Try to parse raw LLM output as JSON into the given schema."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        # Remove first line (```json or ```) and last line (```)
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
        return schema.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        logger.debug("Parse failed: %s", e)
        return None


def _attempt_repair(
    client: OpenAI,
    repair_model: str,
    repair_temperature: float,
    malformed: str,
    schema: Type[T],
) -> T | None:
    """Send malformed output to repair model with target schema."""
    schema_json = json.dumps(schema.model_json_schema(), indent=2)

    system_prompt = (
        "You are a JSON repair assistant. You receive malformed JSON output and a target "
        "JSON schema. Fix the JSON to match the schema exactly. Return ONLY valid JSON, "
        "no explanation, no markdown fences."
    )
    user_prompt = (
        f"Target schema:\n{schema_json}\n\n"
        f"Malformed output:\n{malformed}\n\n"
        "Fix this to match the schema. Return only valid JSON."
    )

    raw = call_llm(client, repair_model, repair_temperature, system_prompt, user_prompt)
    return _try_parse(raw, schema)


def call_llm_structured_list(
    client: OpenAI,
    model: str,
    temperature: float,
    system_prompt: str,
    user_prompt: str,
    item_schema: Type[T],
    repair_model: str | None = None,
    repair_temperature: float = 0.0,
) -> list[T]:
    """Call LLM expecting a JSON array, parse each item into schema.

    Attempts repair on the full response if initial parse fails.
    Skips individual items that fail validation.
    """
    raw = call_llm(client, model, temperature, system_prompt, user_prompt)

    # Strip markdown fences
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try repair on entire response
        if repair_model:
            logger.info("JSON array parse failed, attempting repair")
            # Build a list schema description
            repair_system = (
                "You are a JSON repair assistant. Fix the following to be a valid JSON array "
                "where each element matches the given schema. Return ONLY the JSON array."
            )
            schema_json = json.dumps(item_schema.model_json_schema(), indent=2)
            repair_user = (
                f"Item schema:\n{schema_json}\n\nMalformed output:\n{raw}\n\n"
                "Fix this to be a valid JSON array. Return only the array."
            )
            repaired_raw = call_llm(client, repair_model, repair_temperature, repair_system, repair_user)
            repaired_text = repaired_raw.strip()
            if repaired_text.startswith("```"):
                repaired_lines = repaired_text.split("\n")
                repaired_text = "\n".join(
                    repaired_lines[1:-1] if repaired_lines[-1].strip() == "```" else repaired_lines[1:]
                )
            try:
                data = json.loads(repaired_text)
            except json.JSONDecodeError:
                logger.error("Repair also failed to produce valid JSON")
                return []
        else:
            return []

    if not isinstance(data, list):
        data = [data]

    results = []
    for item in data:
        try:
            results.append(item_schema.model_validate(item))
        except ValidationError as e:
            logger.debug("Skipping invalid item: %s", e)

    return results
