import os
from pathlib import Path
import requests
from dotenv import load_dotenv

# Search and load .env from multiple potential locations
current_dir = Path(__file__).resolve().parent
for candidate in [
    current_dir / ".env",
    current_dir.parent / ".env",
    current_dir.parent.parent / ".env",
    Path.cwd() / ".env",
    current_dir / ".env.example",
    current_dir.parent / ".env.example",
]:
    if candidate.exists():
        load_dotenv(dotenv_path=candidate, override=False)
load_dotenv()


def generate_text(prompt: str) -> str:
    """
    Calls the Groq API using the OpenAI-compatible chat completions endpoint.
    Expects GROQ_API_KEY in environment or .env file.
    Default model: openai/gpt-oss-120b (fast, highly capable, configurable via GROQ_MODEL).
    """

    # 1. Retrieve API key
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_KEY")
    if api_key:
        api_key = api_key.strip()
        if api_key == "gsk_your_groq_api_key_here":
            api_key = None

    if not api_key:
        raise ValueError(
            "Error: GROQ_API_KEY environment variable is not set.\n"
            "Please create a .env file with:\n"
            "GROQ_API_KEY=gsk_your_groq_api_key_here"
        )

    # 2. Configure model and endpoint
    # Default to high-performance openai/gpt-oss-120b available on Groq
    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    api_url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # 3. Build payload
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": float(os.environ.get("GROQ_TEMPERATURE", "0.7")),
        "max_tokens": int(os.environ.get("GROQ_MAX_TOKENS", "2048")),
    }

    # 4. Send request with automatic fallback if chosen model is unavailable
    models_to_try = [model]
    for fallback in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    last_error = None
    for attempt_model in models_to_try:
        payload["model"] = attempt_model
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)
            if response.status_code == 404:
                # Model not found on this account, try next available model
                last_error = response.text
                continue
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError as errh:
            error_detail = ""
            try:
                error_json = response.json()
                error_detail = error_json.get("error", {}).get("message", response.text)
            except Exception:
                error_detail = response.text
            raise RuntimeError(f"Groq API HTTP Error ({response.status_code}): {error_detail}") from errh
        except requests.exceptions.RequestException as err:
            raise RuntimeError(f"Groq API Request Error: {err}") from err
        except (KeyError, IndexError) as err:
            raise RuntimeError(f"Unexpected Groq API response format: {data}") from err

    raise RuntimeError(f"None of the configured Groq models were accessible: {last_error}")
