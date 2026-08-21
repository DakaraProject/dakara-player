"""
Dakara player.

Interface between the Dakara server and a media player, for the Dakara project.
"""

from dakara_player import (
    background,
    font,
    manager,
    media_player,
    player,
    text,
    user_resources,
    version,
    web_client,
    window,
)
from dakara_player.version import __date__, __version__

__all__ = [
    "manager",
    "text",
    "version",
    "window",
    "background",
    "font",
    "player",
    "user_resources",
    "web_client",
    "media_player",
    "__version__",
    "__date__",
]
