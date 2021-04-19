import logging

try:
    from importlib.resources import path

except ImportError:
    from importlib_resources import path

from dakara_base.exceptions import DakaraError
from path import Path


logger = logging.getLogger(__name__)


class BackgroundLoader:
    """Loader for backgrounds

    It finds background files in a custom directory and fallbacks to a package
    resource. Each found background file is copied to a destination directory.
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
            "idle": "/destination/idle.png",
            "transition": "/destination/transition.png",
            "other": "/destination/something.png"
        }

    Args:
        destination (path.Path): where to copy found background files.
        package (str): package checked for backgrounds by default.
        directory (path.Path): custom directory checked for backgrounds.
        filenames (dict): dictionary of background filenames. The key is the
            background name, the value the background file name.

    Attributes:
        backgrounds (dict): dictionary of background file paths. The key is
            the background name, the value the background file path.
        destination (path.Path): where to copy found background files.
        package (str): package checked for backgrounds by default.
        directory (path.Path): custom directory checked for backgrounds.
        filenames (dict): dictionary of background filenames. The key is the
            background name, the value the background file name.
    """

    def __init__(
        self, destination, package, directory=None, filenames=None,
    ):
        self.destination = destination
        self.package = package
        self.directory = directory or Path()
        self.filenames = filenames or {}
        self.backgrounds = {}

    def load(self):
        """Load the backgrounds
        """
        logger.debug("Loading backgrounds")
        for name, file_name in self.filenames.items():
            self.backgrounds[name] = self.get_background_path(file_name)

    def get_background_path(self, file_name):
        """Get the accurate path of one background
        """
        # trying to load from custom directory
        if self.directory:
            file_path = self.directory / file_name
            if file_path.exists():
                return file_path.copy(self.destination)

        # trying to load from package by default
        try:
            with path(self.package, file_name) as file:
                file_path = Path(file)
                return file_path.copy(self.destination)

        except FileNotFoundError as error:
            raise BackgroundNotFoundError(
                "Unable to find background file '{}'".format(file_name)
            ) from error


class BackgroundNotFoundError(DakaraError, FileNotFoundError):
    """Error raised when a background cannot be found
    """
