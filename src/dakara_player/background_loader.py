import logging
from os.path import exists

from dakara_base.exceptions import DakaraError
from path import Path


logger = logging.getLogger(__name__)


class BackgroundLoader:
    """Loader for backgrounds

    It finds background file path based on a default directory and a default
    collection of background files, plus a custom directory and a collection of
    custom background files.

    By instance, given you have the following directory structure:
        - `/default`
            - `idle.png`
            - `transition.png`
            - `other.png`
        - `/custom`
            - `transition.png`
            - `something.png`

    and you use the following configuration:
    >>> loader = BackgroundLoader(
    ...        directory=Path("/custom"),
    ...        default_directory=Path("/default"),
    ...        background_filenames={
    ...            "idle": None,
    ...            "other": "something.png"
    ...        },
    ...        default_background_filenames={
    ...            "idle": "idle.png",
    ...            "transition": "transition.png",
    ...            "other": "other.png"
    ...        }
    ...    )

    you will have the following result:
    >>> loader.load()
    >>> loader.backgrounds
        {
            "idle": "/default/idle.png",
            "transition": "/custom/transition.png",
            "other": "/custom/something.png"
        }

    Args:
        default_directory (path.Path): default lookup directory.
        default_background_filenames (dict): dictionary of default background
            filenames. The key is the background name, the value the background
            file name.
        directory (path.Path): custom lookup directory.
        background_filenames (dict): dictionary of custom background filenames.

    Attributes:
        backgrounds (dict): dictionary of background file paths. The key is
            the background name, the value the background file path.
        default_directory (path.Path): default lookup directory.
        default_background_filenames (dict): dictionary of default background
            filenames.
        directory (path.Path): custom lookup directory.
        background_filenames (dict): dictionary of custom background filenames.
    """

    def __init__(
        self,
        default_directory,
        default_background_filenames,
        directory=None,
        background_filenames=None,
    ):
        self.default_directory = default_directory
        self.default_background_filenames = default_background_filenames
        self.directory = directory or Path()
        background_filenames = background_filenames or {}
        self.background_filenames = dict(
            (k, v) for k, v in background_filenames.items() if v
        )
        self.backgrounds = {}

    def load(self):
        """Load the backgrounds
        """
        logger.debug("Loading backgrounds")
        for name in self.default_background_filenames:
            self.backgrounds[name] = self.get_background_path(name)

    def get_background_path(self, name):
        """Get the accurate path of one background
        """
        # trying to load from custom name and custom directory
        if name in self.background_filenames and self.directory:
            filename = self.background_filenames[name]
            path = self.directory / filename
            if exists(path):
                logger.debug("Loading custom %s background file '%s'", name, path)
                return path

        # trying to load from default name and custom directory
        default_filename = self.default_background_filenames[name]
        if self.directory:
            path = self.directory / default_filename
            if exists(path):
                logger.debug("Loading default %s background file '%s'", name, path)
                return path

        # trying to load from default name and default directory
        path = self.default_directory / default_filename
        if exists(path):
            logger.debug("Loading default %s background file '%s'", name, path)
            return path

        raise BackgroundNotFoundError(
            "Unable to find a background file for {}".format(name)
        )


class BackgroundNotFoundError(DakaraError, FileNotFoundError):
    """Error raised when a background cannot be found
    """
