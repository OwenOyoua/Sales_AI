import os

from openai import OpenAI

MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
_client = None


def chat(messages, max_tokens=600):
    global _client
    if _client is None:
        _client = OpenAI(base_url="https://integrate.api.nvidia.com/v1",
                         api_key=os.environ["NVIDIA_API_KEY"], timeout=45)
    r = _client.chat.completions.create(
        model=MODEL, messages=messages, temperature=0, max_tokens=max_tokens)
    return (r.choices[0].message.content or "").strip()