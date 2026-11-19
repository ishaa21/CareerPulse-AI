import os
import time
from pathlib import Path
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

# Try importing official Groq SDK
try:
    from groq import Groq
    _HAS_GROQ_SDK = True
except ImportError:
    _HAS_GROQ_SDK = False

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _get_api_key() -> str:
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
    return api_key


def generate_text(prompt: str) -> str:
    """
    Calls the Groq API using the official Groq SDK (with automatic connection retries)
    or an HTTPAdapter-backed requests session.
    Default model: openai/gpt-oss-120b.
    """
    api_key = _get_api_key()
    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    temperature = float(os.environ.get("GROQ_TEMPERATURE", "0.7"))
    max_tokens = int(os.environ.get("GROQ_MAX_TOKENS", "2048"))

    # Models to try in order of fallback
    models_to_try = [model]
    for m in ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
        if m not in models_to_try:
            models_to_try.append(m)

    # 1. Primary: Official Groq SDK with automatic retries and modern HTTP connection handling
    if _HAS_GROQ_SDK:
        client = Groq(api_key=api_key, max_retries=3, timeout=60.0)
        last_error = None
        for attempt_model in models_to_try:
            try:
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=attempt_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content
                if content and content.strip():
                    return content
            except Exception as e:
                err_str = str(e)
                last_error = e
                if "429" in err_str:
                    time.sleep(2)
                    continue
                if "404" in err_str:
                    continue
                # For connection drops, sleep 1s and try fallback model
                time.sleep(1)
                continue

    # 2. Fallback: Requests session with Retry adapter and Connection: close to prevent stale sockets
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)

    api_url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Connection": "close",
    }

    last_error = None
    for attempt_model in models_to_try:
        payload = {
            "model": attempt_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        for attempt in range(3):
            try:
                resp = session.post(api_url, headers=headers, json=payload, timeout=60)
                if resp.status_code == 404:
                    last_error = resp.text
                    break
                if resp.status_code == 429:
                    time.sleep(2 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as ce:
                time.sleep(1)
                last_error = ce
                continue
            except Exception as e:
                last_error = e
                break

    raise RuntimeError(f"Groq API call failed: {last_error}")
