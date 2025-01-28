"""Load fonts on user level for the media players."""

import ctypes
import logging
import platform
from abc import ABC, abstractmethod
from importlib.resources import contents, path
from pathlib import Path

from dakara_base.exceptions import DakaraError

logger = logging.getLogger(__name__)

FONT_EXTENSIONS = (".ttf", ".otf")


def get_font_loader_class():
    """Get the font loader associated to the current platform.

    Returns:
        FontLoader: Specialized version of the font loader class.
    """
    system = platform.system()

    if system == "Linux":
        return FontLoaderLinux

    if system == "Windows":
        return FontLoaderWindows

    raise NotImplementedError(
        "This operating system ({}) is not currently supported".format(system)
    )


class FontLoader(ABC):
    """Abstract font loader.

    Must be specialized for a given OS.

    Args:
        package (str): Package checked for font files.

    Attributes:
        package (str): Package checked for font files.
    """

    GREETINGS = "Abstract font loader selected"

    def __init__(self, package):
        self.package = package

        # show type of font loader
        logger.debug(self.GREETINGS)

    @abstractmethod
    def load(self):
        """Load the fonts."""

    @abstractmethod
    def unload(self):
        """Unload the loaded fonts."""

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.unload()

    def get_font_name_list(self):
        """Give name of package fonts.

        Returns:
            list of str: List of font names.
        """
        logger.debug("Scanning fonts directory")
        font_file_name_list = [
            file
            for file in contents(self.package)
            if Path(file).suffix.lower() in FONT_EXTENSIONS
        ]
        logger.debug("Found %i font(s) to load", len(font_file_name_list))

        return font_file_name_list

    def get_font_path_iterator(self):
        """Give font paths in font package.

        Yields:
            pathlib.Path: Absolute path to the font, from the package.
        """
        for font_file_name in self.get_font_name_list():
            with path(self.package, font_file_name) as font_file_path:
                yield Path(font_file_path)


class FontLoaderLinux(FontLoader):
    """Font loader for Linux.

    It copies fonts to load in the user fonts directory and removes them on
    exit. Using symbolic links is not safe as the location of the package fonts
    may not be permanent (see `importlib.resources.path` for more info).

    See:
        https://docs.python.org/3/library/importlib.html#importlib.resources.path

    Example of use:

    >>> with FontLoaderLinux() as loader:
    ...     loader.load()
    ...     # do stuff while fonts are loaded
    >>> # now fonts are unloaded

    Args:
        package (str): Package checked for font files.

    Attributes:
        package (str): Package checked for font files.
        font_loaded (dict of pathlib.Path): List of loaded fonts. The key is
            the font file name and the value is the path of the installed font
            in user directory.
    """

    GREETINGS = "Font loader for Linux selected"
    FONT_DIR_SYSTEM = Path("/") / "usr" / "share" / "fonts"
    FONT_DIR_USER = Path("~") / ".fonts"

    def __init__(self, *args, **kwargs):
        # call parent constructor
        super().__init__(*args, **kwargs)

        # create list of fonts
        self.fonts_loaded = {}

    def get_system_font_path_list(self):
        """Retrieve the list of system fonts.

        Returns:
            list of pathlib.Path: List of font paths.
        """
        return list(self.FONT_DIR_SYSTEM.walkfiles())

    def get_user_font_path_list(self):
        """Retrieve the list of user fonts.

        Returns:
            list of pathlib.Path: List of font paths.
        """
        return list(self.FONT_DIR_USER.expanduser().walkfiles())

    def load(self):
        """Load the fonts."""
        # ensure that the user font directory exists
        self.FONT_DIR_USER.expanduser().mkdir_p()

        # get system and user font files
        system_font_path_list = self.get_system_font_path_list()
        user_font_path_list = self.get_user_font_path_list()

        # load fonts
        for font_file_path in self.get_font_path_iterator():
            self.load_font(font_file_path, system_font_path_list, user_font_path_list)

    def load_font(self, font_file_path, system_font_path_list, user_font_path_list):
        """Load the provided font.

        Args:
            font_file_path (pathlib.Path): Absolute path of the font to load.
            system_font_path_list (list of pathlib.Path): List of absolute
                paths of system fonts.
            user_font_path_list (list of pathlib.Path): List of absolute paths
                of user fonts.
        """
        # get font file name
        font_file_name = font_file_path.basename()

        # check if the font is installed at system level
        if any(font_file_name in path for path in system_font_path_list):
            logger.debug("Font '%s' found in system directory", font_file_name)
            return

        # check if the font is installed at user level
        if any(font_file_name in path for path in user_font_path_list):
            logger.debug("Font '%s' found in user directory", font_file_name)
            return

        # check if the font exists as broken link at user level
        # in this case remove it and continue execution
        font_file_user_path = self.FONT_DIR_USER.expanduser() / font_file_name
        if font_file_user_path.is_link():
            logger.debug(
                "Dead symbolic link found for font '%s' in user directory, "
                "removing it",
                font_file_name,
            )
            font_file_user_path.unlink_p()

        # then, if the font is not installed, load by copying it
        font_file_path.copy(font_file_user_path)

        # register the font
        self.fonts_loaded[font_file_name] = font_file_user_path

        logger.debug(
            "Font '%s' loaded in user directory: '%s'",
            font_file_name,
            font_file_user_path,
        )

    def unload(self):
        """Remove loaded fonts."""
        for font_file_name in self.fonts_loaded.copy():
            self.unload_font(font_file_name)

    def unload_font(self, font_file_name):
        """Remove the provided font.

        Args:
            font_file_name (str): Name of the font to unload.
        """
        try:
            font_file_path = self.fonts_loaded.pop(font_file_name)
            font_file_path.unlink()
            logger.debug("Font '%s' unloaded", font_file_name)

        except OSError as error:
            logger.error(
                "Font '%s' in '%s' cannot be unloaded: %s",
                font_file_name,
                font_file_path,
                error,
            )


class FontLoaderWindows(FontLoader):
    """Font loader for Windows.

    It uses the gdi32 library to dynamically load and unload fonts for the
    current session.

    Example of use:

    >>> with FontLoaderWindows() as loader:
    ...     loader.load()
    ...     # do stuff while fonts are loaded
    >>> # fonts are unloaded

    Args:
        package (str): Package checked for font files.

    Attributes:
        package (str): Package checked for font files.
        font_loaded (dict of pathlib.Path): List of loaded fonts. The key is
            the font file name and the value is the path of font used at
            installation.
    """

    GREETINGS = "Font loader for Windows selected"

    def __init__(self, *args, **kwargs):
        # call parent constructor
        super().__init__(*args, **kwargs)

        # create list of fonts
        self.fonts_loaded = {}

        # check we can use gdi32 library
        if not hasattr(ctypes, "windll"):
            raise FontLoaderNotAvailableError(
                "FontLoaderWindows can only be used on Windows"
            )

    def load(self):
        """Load the fonts."""
        for font_file_path in self.get_font_path_iterator():
            self.load_font(font_file_path)

    def load_font(self, font_file_path):
        """Load the provided font.

        Args:
            font_file_path (pathlib.Path): Absolute path of the font to load.
        """
        success = ctypes.windll.gdi32.AddFontResourceW(font_file_path)
        if success:
            self.fonts_loaded[font_file_path.name] = font_file_path
            logger.debug("Font '%s' loaded", font_file_path.name)
            return

        logger.warning("Font '%s' cannot be loaded", font_file_path.name)

    def unload(self):
        """Remove loaded fonts."""
        for font_file_name in self.fonts_loaded.copy():
            self.unload_font(font_file_name)

    def unload_font(self, font_file_name):
        """Remove the provided font.

        Args:
            font_file_name (str): Name of the font to unload.
        """
        font_file_path = self.fonts_loaded.pop(font_file_name)
        success = ctypes.windll.gdi32.RemoveFontResourceW(font_file_path)
        if success:
            logger.debug("Font '%s' unloaded", font_file_name)
            return

        logger.warning("Font '%s' cannot be unloaded", font_file_name)


class FontLoaderNotAvailableError(DakaraError):
    """Error raised when a font loader cannot be used."""
