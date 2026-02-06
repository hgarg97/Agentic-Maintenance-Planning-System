"""
Avatar Registration
====================
Registers all agent avatars with Chainlit at chat start.
Maps agent names to their avatar image files.

Note: In Chainlit 2.x, avatars are handled via the `author` parameter
in messages. Custom avatars can be set via chainlit.toml or by using
Element with images. For simplicity, we rely on the author name.
"""

import logging
from pathlib import Path

import chainlit as cl

from config.settings import AGENTS

logger = logging.getLogger(__name__)


async def register_all_avatars() -> None:
    """
    Register all agent avatars with Chainlit for display in messages.

    In Chainlit 2.x, we use cl.user_session to store avatar mappings,
    and avatars are displayed based on the 'author' field in messages.
    """
    # Store avatar paths in session for reference
    avatar_map = {}
    for key, agent in AGENTS.items():
        avatar_path = agent.get("avatar")
        if avatar_path:
            # Check if file exists
            if Path(avatar_path).exists():
                avatar_map[agent["name"]] = avatar_path
            else:
                logger.warning(f"Avatar file not found: {avatar_path}")

    cl.user_session.set("avatar_map", avatar_map)
    logger.info(f"Registered {len(avatar_map)} agent avatars")
