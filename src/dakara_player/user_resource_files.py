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
    if "linux" in sys.platform:
        return Path("~") / ".local" / "share" / "dakara" / "player"

    if "win" in sys.platform:
        return Path("$APPDATA") / "Dakara" / "player"

    raise NotImplementedError("Operating system not supported")


def copy_resource(resource, destination, force):
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
    user_directory = get_user_directory().expand()
    user_directory.mkdir_p()

    for directory in ["backgrounds", "templates"]:
        copy_resource(
            f"dakara_player.resources.{directory}", user_directory / directory, force
        )

    logger.info(f"Resource files created in '{user_directory}'")
