"""Manage background images for media players."""

import logging
from importlib.resources import as_file, files
from pathlib import Path
from shutil import copy

from dakara_base.exceptions import DakaraError

logger = logging.getLogger(__name__)


class BackgroundLoader:
    """Loader for backgrounds.

    It finds background files in a custom directory and fallbacks to a package
    resource. Each background file found is copied to a destination directory.
    If the loader cannot find a file, an exception is raised.

    By instance, given you have the following directory structure:

    - `package.default`
        - `idle.png`
        - `transition.png`
        - `other.png`
    - `/directory/custom`
        - `transition.png`
        - `something.png`

    and you use the following configuration:
    >>> from pathlib import Path
    >>> loader = BackgroundLoader(
    ...        destination=Path("/destination"),
    ...        directory=Path("/directory/custom"),
    ...        package="package.default",
    ...        filenames={
    ...            "idle": "idle.png",
    ...            "transition": "transition.png",
    ...            "other": "something.png"
    ...        }
    ...    )

    you will have the following result:
    >>> loader.load()
    >>> loader.backgrounds
        {
            "idle": Path("/destination/idle.png"),
            "transition": Path("/destination/transition.png"),
            "other": Path("/destination/something.png")
        }

    Args:
        destination (pathlib.Path): Where to copy found background files.
        package (str): Package checked for backgrounds by default.
        directory (pathlib.Path): Custom directory checked for backgrounds.
        filenames (dict): Dictionary of background filenames. The key is the
            background name, the value the background file name.

    Attributes:
        backgrounds (dict): Dictionary of background file paths. The key is
            the background name, the value the background file path.
        destination (pathlib.Path): Where to copy found background files.
        package (str): Package checked for backgrounds by default.
        directory (pathlib.Path): Custom directory checked for backgrounds.
        filenames (dict): Dictionary of background filenames. The key is the
            background name, the value the background file name.
    """

    def __init__(
        self,
        destination,
        package,
        directory=None,
        filenames=None,
    ):
        self.destination = destination
        self.package = package
        self.directory = directory
        self.filenames = filenames or {}
        self.backgrounds = {}

    def load(self):
        """Load the backgrounds."""
        logger.debug("Loading backgrounds")
        for name, file_name in self.filenames.items():
            self.backgrounds[name] = self.get_background_path(name, file_name)

    def get_background_path(self, background_name, file_name):
        """Get the accurate path of one background

        Args:
            background_name (str): Name of the background.
            file_name (str): Name of the background file.

        Returns:
            pathlib.Path: Absolute path to the background file.
        """
        # trying to load from custom directory
        if self.directory is not None:
            try:
                return self.copy_custom_background(background_name, file_name)

            except FileNotFoundError:
                pass

        # trying to load from package by default
        try:
            return self.copy_default_background(background_name, file_name)

        except FileNotFoundError as error:
            raise BackgroundNotFoundError(
                f"No {background_name} background file found for '{file_name}'"
            ) from error

    def copy_custom_background(self, background_name, file_name):
        """Copy a custom background.

        Args:
            background_name (str): Name of the background.
            file_name (str): Name of the background file.

        Returns:
            pathlib.Path: Absolute path to the background file.

        Raises:
            FileNotFoundError: If the custom file does not exist (by
                `shuti.copy`).
        """
        file_path = self.directory / file_name
        output_path = Path(copy(file_path, self.destination))
        logger.debug(
            "Loading custom %s background file '%s'", background_name, file_name
        )
        return output_path

    def copy_default_background(self, background_name, file_name):
        """Copy a default background.

        Args:
            background_name (str): Name of the background.
            file_name (str): Name of the background file.

        Returns:
            pathlib.Path: Absolute path to the background file.

        Raises:
            FileNotFoundError: If the custom file does not exist (by
                `shuti.copy`).
        """
        with as_file(files(self.package).joinpath(file_name)) as file_path:
            output_path = Path(copy(file_path, self.destination))
            logger.debug(
                "Loading default %s background file '%s'",
                background_name,
                file_name,
            )
            return output_path


class BackgroundNotFoundError(DakaraError, FileNotFoundError):
    """Error raised when a background cannot be found"""
