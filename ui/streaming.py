"""
Streaming Helpers
==================
Manages token-by-token streaming to Chainlit messages.
Handles multi-agent message switching (different avatars per agent).
"""

import asyncio
from typing import Optional

import chainlit as cl

from config.settings import AGENTS, UI


class StreamManager:
    """Manages streaming state for the current chat session."""

    def __init__(self):
        self._current_message: Optional[cl.Message] = None
        self._current_agent: Optional[str] = None

    async def stream_token(self, token: str, agent_key: str = "james") -> None:
        """
        Stream a token to the current message.
        If the agent changes, start a new message with the new agent's avatar.

        Args:
            token: The text token to stream
            agent_key: The agent key from settings (e.g., 'james', 'mira')
        """
        agent = AGENTS.get(agent_key, AGENTS["system"])

        # If agent changed or no active message, create a new one
        if self._current_agent != agent_key or self._current_message is None:
            # Finalize previous message if exists
            if self._current_message is not None:
                await self._current_message.update()

            # Create new message for the new agent
            self._current_message = cl.Message(
                content="",
                author=agent["name"],
            )
            await self._current_message.send()
            self._current_agent = agent_key

        # Stream the token
        await self._current_message.stream_token(token)

        # Small delay for visual streaming effect
        delay = UI.get("streaming_delay_ms", 15) / 1000
        if delay > 0:
            await asyncio.sleep(delay)

    async def finalize(self) -> None:
        """Finalize the current streaming message."""
        if self._current_message is not None:
            await self._current_message.update()
            self._current_message = None
            self._current_agent = None

    async def send_message(
        self, content: str, agent_key: str = "james"
    ) -> cl.Message:
        """
        Send a non-streamed message as a specific agent.

        Args:
            content: Message content
            agent_key: Agent key from settings

        Returns:
            The sent Chainlit message
        """
        # Finalize any ongoing stream first
        await self.finalize()

        agent = AGENTS.get(agent_key, AGENTS["system"])
        msg = cl.Message(
            content=content,
            author=agent["name"],
        )
        await msg.send()
        return msg

    async def send_step(
        self, agent_key: str, step_name: str, content: str
    ) -> None:
        """
        Send a step/tool-call display under an agent.

        Args:
            agent_key: Agent key from settings
            step_name: Name of the step/tool
            content: Step content/output
        """
        async with cl.Step(name=step_name, type="tool") as step:
            step.output = content


def create_stream_callback(stream_manager: StreamManager):
    """
    Create a callback function that can be passed via LangGraph config
    to agent nodes for real-time streaming.

    Usage in agents:
        cl_callback = config.get("configurable", {}).get("cl_callback")
        if cl_callback:
            await cl_callback(token, "james")

    Args:
        stream_manager: The StreamManager instance for this session

    Returns:
        Async callback function (token: str, agent_key: str) -> None
    """

    async def callback(token: str, agent_key: str = "james") -> None:
        await stream_manager.stream_token(token, agent_key)

    return callback


def create_agent_callback(stream_manager: StreamManager):
    """
    Create a callback for agent status updates (thinking indicators).

    Usage in agents:
        agent_callback = config.get("configurable", {}).get("agent_callback")
        if agent_callback:
            await agent_callback("james", "thinking")

    Args:
        stream_manager: The StreamManager instance

    Returns:
        Async callback function
    """

    async def callback(agent_key: str, status: str) -> None:
        agent = AGENTS.get(agent_key, AGENTS["system"])
        if status == "thinking":
            # Show a thinking indicator as a step
            pass  # The streaming itself serves as the indicator

    return callback
