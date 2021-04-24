import logging
import sys
from distutils.util import strtobool

try:
    from importlib.resources import path, contents

except ImportError:
    from importlib_resources import path, contents

from path import Path


logger = logging.getLogger(__name__)


def get_user_directory():
    """Get the user directory for resource files

    Returns:
        path.Path: path to the user directory, must be expanded to be used.
    """
    if "linux" in sys.platform:
        return Path("~") / ".local" / "share" / "dakara" / "player"

    if "win" in sys.platform:
        return Path("$APPDATA") / "Dakara" / "player"

    raise NotImplementedError("Operating system not supported")


def copy_resource(resource, destination, force):
    """Copy the content of one resource directory

    Args:
        resource (str): resource to copy.
        destination (path.Path): directory where to copy the resource.
        force (bool): if the destination exists and this flag is set to True,
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

    destination.mkdir_p()

    for file_name in contents(resource):
        # ignore Python files
        if file_name.startswith("__"):
            continue

        with path(resource, file_name) as file:
            Path(file).copyfile(destination)


def create_resource_files(force=False):
    """Copy the resource files to user directory

    Args:
        force (bool): if the user directory already contains the resource
            directories and this flag is set, overwrite the directories.
    """
    user_directory = get_user_directory().expand()
    user_directory.mkdir_p()

    for directory in ["backgrounds", "templates"]:
        copy_resource(
            f"dakara_player.resources.{directory}", user_directory / directory, force
        )

    logger.info(f"Resource files created in '{user_directory}'")
