"""Thin LLM provider abstraction — dispatches to the correct SDK."""

from __future__ import annotations

import time
from dataclasses import dataclass

from src.llm.config import LLMProvidersConfig


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    provider: str
    model: str


async def call_llm(
    config: LLMProvidersConfig,
    provider: str,
    model: str,
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 4096,
) -> LLMResponse:
    """Call the appropriate LLM provider and return a unified response."""
    api_key = config.get_api_key(provider)
    if not api_key:
        prov = config.providers.get(provider)
        env_var = prov.api_key_env if prov else "unknown"
        raise ValueError(
            f"No API key found for provider '{provider}' (env var: {env_var})"
        )

    start = time.monotonic()

    if provider == "google":
        text, in_tok, out_tok = await _call_google(
            api_key, model, prompt, system_prompt, max_tokens
        )
    elif provider == "anthropic":
        text, in_tok, out_tok = await _call_anthropic(
            api_key, model, prompt, system_prompt, max_tokens
        )
    elif provider == "openai":
        text, in_tok, out_tok = await _call_openai(
            api_key, model, prompt, system_prompt, max_tokens
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    elapsed_ms = int((time.monotonic() - start) * 1000)

    return LLMResponse(
        text=text,
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=elapsed_ms,
        provider=provider,
        model=model,
    )


async def _call_google(
    api_key: str, model: str, prompt: str, system_prompt: str, max_tokens: int
) -> tuple[str, int, int]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt or None,
        max_output_tokens=max_tokens,
    )
    response = await client.aio.models.generate_content(
        model=model, contents=prompt, config=config
    )
    usage = response.usage_metadata
    return (
        response.text,
        usage.prompt_token_count,
        usage.candidates_token_count,
    )


async def _call_anthropic(
    api_key: str, model: str, prompt: str, system_prompt: str, max_tokens: int
) -> tuple[str, int, int]:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)
    message = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt or "You are a helpful assistant.",
        messages=[{"role": "user", "content": prompt}],
    )
    return (
        message.content[0].text,
        message.usage.input_tokens,
        message.usage.output_tokens,
    )


async def _call_openai(
    api_key: str, model: str, prompt: str, system_prompt: str, max_tokens: int
) -> tuple[str, int, int]:
    import openai

    client = openai.AsyncOpenAI(api_key=api_key)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
    )
    choice = response.choices[0]
    usage = response.usage
    return (
        choice.message.content,
        usage.prompt_tokens,
        usage.completion_tokens,
    )
