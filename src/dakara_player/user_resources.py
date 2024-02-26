"""Manage the user resource directory and files."""

import logging
from distutils.util import strtobool
from importlib.resources import contents, path

from dakara_base.directory import directories
from path import Path

logger = logging.getLogger(__name__)


def copy_resource(resource, destination, force):
    """Copy the content of one resource directory.

    Args:
        resource (str): Resource to copy.
        destination (path.Path): Directory where to copy the resource.
        force (bool): If the destination exists and this flag is set to `True`,
            overwrite the destination.
    """
    if not force and destination.exists():
        try:
            result = strtobool(
                input(
                    f"Directory {destination} already exists, "
                    "overwrite it with its content? [y/N] "
                )
            )

        except ValueError:
            result = False

        if not result:
            return

    destination.makedirs_p()

    for file_name in contents(resource):
        # ignore Python files
        if file_name.startswith("__"):
            continue

        with path(resource, file_name) as file:
            Path(file).copy(destination)


def create_resource_files(force=False):
    """Copy the resource files to user directory.

    Args:
        force (bool): If the user directory already contains the resource
            directories and this flag is set, overwrite the directories.
    """
    user_directory = directories.user_data_dir
    user_directory.makedirs_p()

    for directory in ["backgrounds", "templates"]:
        copy_resource(
            f"dakara_player.resources.{directory}", user_directory / directory, force
        )

    logger.info(f"Resource files created in '{user_directory}'")
