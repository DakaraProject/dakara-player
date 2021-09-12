"""Version of the program."""

import logging

import importlib_metadata
from pkg_resources import parse_version

__version__ = importlib_metadata.version("dakaraplayer")
__date__ = "2021-06-20"

logger = logging.getLogger(__name__)


def check_version():
    """Display version number and check if on release."""
    # log player versio
    logger.info("Dakara player %s (%s)", __version__, __date__)

    # check version is a release
    version = parse_version(__version__)
    if version.is_prerelease:
        logger.warning("You are running a dev version, use it at your own risks!")
