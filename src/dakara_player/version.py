"""Version of the program.

The version and date module variables are automatically updated by
`bump_version.sh`.
"""

import logging

from packaging.version import parse

__version__ = "1.9.0-dev"
__date__ = "2022-12-18"

logger = logging.getLogger(__name__)


def check_version():
    """Display version number and check if on release."""
    # log player versio
    logger.info("Dakara player %s (%s)", __version__, __date__)

    # check version is a release
    version = parse(__version__)
    if version.is_prerelease:
        logger.warning("You are running a dev version, use it at your own risks!")
