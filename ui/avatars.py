"""
Avatar Registration
====================
Registers all agent avatars with Chainlit at chat start.
Maps agent names to their avatar image files.
"""

import chainlit as cl

from config.settings import AGENTS


async def register_all_avatars() -> None:
    """Register all agent avatars with Chainlit for display in messages."""
    for key, agent in AGENTS.items():
        avatar_path = agent.get("avatar")
        if avatar_path:
            await cl.Avatar(
                name=agent["name"],
                path=avatar_path,
            ).send()
