
from openai import AsyncOpenAI

from app.core.config import settings


_client: AsyncOpenAI | None = None


def get_grok_client() -> AsyncOpenAI:
    """Create and reuse the Groq API client."""
    global _client

    api_key = settings.groq_api_key.get_secret_value().strip()

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Check your backend/.env file."
        )

    if _client is None:
        _client = AsyncOpenAI(
            api_key=api_key,
            base_url=settings.groq_base_url,
            timeout=30.0,
            max_retries=1,
        )

    return _client


async def generate_grok_response(
    prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 200,
) -> str:
    """Send a prompt to Groq and return its text response."""
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    client = get_grok_client()

    response = await client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful AI assistant for an HR management "
                    "system. Answer clearly and concisely. Do not invent "
                    "company data or claim to have accessed records."
                ),
            },
            {
                "role": "user",
                "content": prompt.strip(),
            },
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    answer = response.choices[0].message.content

    if not answer or not answer.strip():
        raise RuntimeError("Groq returned an empty response.")

    return answer.strip()
