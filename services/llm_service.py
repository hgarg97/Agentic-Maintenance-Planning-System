"""
LLM Service
============
OpenAI client wrapper for chat completions, classification, and text rephrasing.
Supports both streaming and non-streaming modes.
"""

import json
import logging
from typing import AsyncGenerator, Optional

from openai import AsyncOpenAI

from config.settings import MODELS

logger = logging.getLogger(__name__)

# Module-level client (initialized once)
_client: Optional[AsyncOpenAI] = None


def get_client() -> AsyncOpenAI:
    """Get or create the OpenAI async client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI()
    return _client


async def chat(
    messages: list[dict],
    model: Optional[str] = None,
    tools: Optional[list] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stream: bool = False,
) -> dict | AsyncGenerator:
    """
    Send a chat completion request.

    Args:
        messages: List of message dicts (role, content)
        model: Model to use (defaults to main model from settings)
        tools: Optional list of tool definitions
        temperature: Override temperature
        max_tokens: Override max tokens
        stream: If True, returns an async generator of chunks

    Returns:
        Full response dict or async generator for streaming
    """
    client = get_client()
    model = model or MODELS["main"]
    temperature = temperature if temperature is not None else MODELS["temperature"]
    max_tokens = max_tokens or MODELS["max_tokens"]

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    if stream:
        return await _stream_chat(client, **kwargs)
    else:
        response = await client.chat.completions.create(**kwargs)
        return {
            "content": response.choices[0].message.content,
            "role": response.choices[0].message.role,
            "tool_calls": (
                response.choices[0].message.tool_calls
                if hasattr(response.choices[0].message, "tool_calls")
                else None
            ),
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            },
        }


async def _stream_chat(client: AsyncOpenAI, **kwargs) -> AsyncGenerator[str, None]:
    """Internal streaming handler. Yields content tokens."""
    stream = await client.chat.completions.create(**kwargs)
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def classify(text: str, categories: list[str]) -> str:
    """
    Classify text into one of the given categories using the lightweight model.

    Args:
        text: Text to classify
        categories: List of category strings

    Returns:
        The classified category string
    """
    categories_str = "\n".join(f"- {cat}" for cat in categories)
    messages = [
        {
            "role": "system",
            "content": (
                f"Classify the following text into exactly ONE of these categories:\n"
                f"{categories_str}\n\n"
                f"Respond with ONLY the category name, nothing else."
            ),
        },
        {"role": "user", "content": text},
    ]

    response = await chat(
        messages=messages,
        model=MODELS["lightweight"],
        temperature=0.0,
        max_tokens=MODELS["max_tokens_classify"],
        stream=False,
    )

    result = response["content"].strip().lower()

    # Validate the result is one of the categories
    for cat in categories:
        if cat.lower() in result:
            return cat

    logger.warning(f"Classification returned unexpected result: {result}")
    return categories[-1]  # Default to last category (usually "general_qa")


async def rephrase(text: str, agent_name: str, agent_role: str) -> str:
    """
    Rephrase system-generated text into natural, conversational language.

    Args:
        text: The raw text to rephrase
        agent_name: Name of the agent speaking
        agent_role: Role of the agent

    Returns:
        Rephrased text
    """
    messages = [
        {
            "role": "system",
            "content": (
                f"You are {agent_name}, a {agent_role}. Rephrase the following text "
                f"into a natural, conversational response while keeping all factual "
                f"information intact. Be professional and concise."
            ),
        },
        {"role": "user", "content": f"Rephrase this:\n{text}"},
    ]

    response = await chat(
        messages=messages,
        model=MODELS["lightweight"],
        temperature=MODELS["temperature_creative"],
        max_tokens=MODELS["max_tokens"],
        stream=False,
    )

    return response["content"]


async def parse_json_response(text: str, instruction: str) -> dict:
    """
    Use the lightweight model to extract structured JSON from free-form text.

    Args:
        text: The text to parse (e.g., vendor email, technician input)
        instruction: What to extract and expected JSON format

    Returns:
        Parsed JSON as a dict
    """
    messages = [
        {
            "role": "system",
            "content": (
                f"{instruction}\n\n"
                f"Respond with valid JSON only. No additional text."
            ),
        },
        {"role": "user", "content": text},
    ]

    response = await chat(
        messages=messages,
        model=MODELS["lightweight"],
        temperature=0.0,
        max_tokens=512,
        stream=False,
    )

    try:
        return json.loads(response["content"])
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        content = response["content"]
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
        logger.error(f"Failed to parse JSON from LLM response: {content}")
        return {}
