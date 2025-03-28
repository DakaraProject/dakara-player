"""Manage the user resource directory and files."""

import logging
from importlib.resources import files
from shutil import copy

from dakara_base.directory import directories
from dakara_base.utils import strtobool

logger = logging.getLogger(__name__)


def copy_resource(package, destination, force):
    """Copy the content of one resource directory.

    Args:
        package (str): Package of resources to copy.
        destination (pathlib.Path): Directory where to copy the resource.
        force (bool): If the destination exists and this flag is set to `True`,
            overwrite the destination.
    """
    if not force and destination.exists():
        result = strtobool(
            input(
                f"Directory {destination} already exists, "
                "overwrite it with its content? [y/N] "
            )
        )

        if not result:
            return

    destination.mkdir(parents=True, exist_ok=True)

    for resource in files(package).iterdir():
        # ignore Python files
        if resource.name.startswith("__"):
            continue

        copy(resource, destination)


def create_resource_files(force=False):
    """Copy the resource files to user directory.

    Args:
        force (bool): If the user directory already contains the resource
            directories and this flag is set, overwrite the directories.
    """
    user_directory = directories.user_data_path
    user_directory.mkdir(parents=True, exist_ok=True)

    for directory in ["backgrounds", "templates"]:
        copy_resource(
            f"dakara_player.resources.{directory}", user_directory / directory, force
        )

    logger.info(f"Resource files created in '{user_directory}'")
