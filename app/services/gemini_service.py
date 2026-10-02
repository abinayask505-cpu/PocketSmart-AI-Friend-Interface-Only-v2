import json
import os
from pathlib import Path
from typing import Any

try:
    from google import genai
except ImportError:
    genai = None


def _client():
    """
    Create and return the Gemini API client.

    Returns:
        Gemini client if API key and package are available.
        None otherwise.
    """
    key = os.getenv("GEMINI_API_KEY")

    if not key or genai is None:
        return None

    try:
        return genai.Client(api_key=key)
    except Exception as exc:
        print(f"Gemini client initialization failed: {exc}")
        return None


def _clean_json(text: str) -> dict[str, Any] | None:
    """
    Clean Gemini's response and convert it into a Python dictionary.

    Handles:
    - Normal JSON
    - ```json ... ``` responses
    - Empty responses
    - Malformed JSON
    """
    if not text:
        return None

    text = text.strip()

    if not text:
        return None

    # Remove Markdown code fences if Gemini returns them.
    if text.startswith("```"):
        text = text.replace("```json", "", 1)
        text = text.replace("```", "", 1).strip()

    try:
        result = json.loads(text)

        # The application expects a JSON object/dictionary.
        if isinstance(result, dict):
            return result

        print("Gemini returned valid JSON, but it was not an object.")
        return None

    except json.JSONDecodeError as exc:
        print(f"Gemini returned invalid JSON: {exc}")
        return None

    except Exception as exc:
        print(f"Unexpected JSON parsing error: {exc}")
        return None


async def generate_json(
    prompt: str,
    image_path: str | None = None,
):
    """
    Generate structured JSON using Gemini.

    If Gemini is unavailable, returns None so the calling
    recommendation service can use its fallback recommendations.

    This function intentionally catches API failures such as:
    - 429 RESOURCE_EXHAUSTED
    - 401/403 authentication errors
    - 404 model errors
    - network/API failures
    - malformed Gemini responses
    """

    client = _client()

    if not client:
        print("Gemini client unavailable. Using fallback recommendations.")
        return None

    model = os.getenv(
        "GEMINI_MODEL",
        "gemini-2.5-flash",
    )

    contents = [prompt]

    # Add optional outfit image for the Jewelry Planner.
    if image_path:
        image_file = Path(image_path)

        if image_file.exists():
            try:
                from google.genai import types

                contents.append(
                    types.Part.from_bytes(
                        data=image_file.read_bytes(),
                        mime_type=_mime(image_path),
                    )
                )

            except Exception as exc:
                print(f"Unable to load Gemini image input: {exc}")

                # Image is optional according to the project requirements.
                # Continue with the text prompt instead of crashing.
                pass

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
        )

    except Exception as exc:
        error_text = str(exc)

        # Gemini free-tier quota/rate-limit error.
        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
            print(
                "Gemini quota exhausted. "
                "Using fallback recommendations."
            )
            print(f"Gemini quota details: {exc}")
            return None

        # Authentication/API-key errors.
        if "401" in error_text or "403" in error_text:
            print(
                "Gemini authentication/permission error. "
                "Using fallback recommendations."
            )
            print(f"Gemini authentication details: {exc}")
            return None

        # Model unavailable/not found.
        if "404" in error_text or "NOT_FOUND" in error_text:
            print(
                f"Gemini model '{model}' is unavailable. "
                "Using fallback recommendations."
            )
            print(f"Gemini model details: {exc}")
            return None

        # Any other Gemini/API failure.
        print(
            "Gemini API request failed. "
            "Using fallback recommendations."
        )
        print(f"Gemini API error: {exc}")

        return None

    # Safely read Gemini's response text.
    try:
        response_text = response.text or ""
    except Exception as exc:
        print(f"Unable to read Gemini response: {exc}")
        return None

    if not response_text.strip():
        print("Gemini returned an empty response. Using fallback.")
        return None

    return _clean_json(response_text)


def _mime(path: str) -> str:
    """
    Return the MIME type for a supported image file.
    """

    suffix = Path(path).suffix.lower()

    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "image/jpeg")