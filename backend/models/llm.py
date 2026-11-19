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
]:
    if candidate.exists():
        load_dotenv(dotenv_path=candidate, override=False)
load_dotenv()


def generate_text(prompt: str) -> str:
    """
    Calls the Groq API using the OpenAI-compatible chat completions endpoint.
    Expects GROQ_API_KEY in environment or .env file.
    Default model: llama-3.3-70b-versatile (configurable via GROQ_MODEL).
    """

    # 1. Retrieve API key
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        # Fallback check for alternative naming
        api_key = os.environ.get("GROQ_KEY")

    if not api_key:
        raise ValueError(
            "Error: GROQ_API_KEY environment variable is not set.\n"
            "Please create a .env file with:\n"
            "GROQ_API_KEY=gsk_your_groq_api_key_here"
        )

    # 2. Configure model and endpoint
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    api_url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
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

    # 4. Send request
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        # 5. Extract generated text
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
