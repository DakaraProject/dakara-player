"""Load fonts on user level for the media players."""

import ctypes
import logging
import platform
from abc import ABC, abstractmethod
from importlib.resources import as_file, files
from pathlib import Path
from shutil import copy

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
            file.name
            for file in files(self.package).iterdir()
            if file.is_file() and file.suffix.lower() in FONT_EXTENSIONS
        ]
        logger.debug("Found %i font(s) to load", len(font_file_name_list))

        return font_file_name_list

    def get_font_path_iterator(self):
        """Give font paths in font package.

        Yields:
            pathlib.Path: Absolute path to the font, from the package.
        """
        for font_file_name in self.get_font_name_list():
            with as_file(
                files(self.package).joinpath(font_file_name)
            ) as font_file_path:
                yield font_file_path


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

    def get_system_font_name_list(self):
        """Retrieve the list of system fonts.

        Returns:
            list of pathlib.Path: List of font paths.
        """
        return [path.name for path in self.FONT_DIR_SYSTEM.rglob("*")]

    def get_user_font_name_list(self):
        """Retrieve the list of user fonts.

        Returns:
            list of pathlib.Path: List of font paths.
        """
        return [path.name for path in self.FONT_DIR_USER.expanduser().rglob("*")]

    def load(self):
        """Load the fonts."""
        # ensure that the user font directory exists
        self.FONT_DIR_USER.expanduser().mkdir(parents=True, exist_ok=True)

        # get system and user font files
        system_font_name_list = self.get_system_font_name_list()
        user_font_name_list = self.get_user_font_name_list()

        # load fonts
        for font_file_path in self.get_font_path_iterator():
            self.load_font(font_file_path, system_font_name_list, user_font_name_list)

    def load_font(self, font_file_path, system_font_name_list, user_font_name_list):
        """Load the provided font.

        Args:
            font_file_path (pathlib.Path): Absolute path of the font to load.
            system_font_name_list (list of pathlib.Path): List of system fonts
                name.
            user_font_name_list (list of pathlib.Path): List of user fonts
                name.
        """
        # get font file name
        font_file_name = font_file_path.name

        # check if the font is installed at system level
        if font_file_name in system_font_name_list:
            logger.debug("Font '%s' found in system directory", font_file_name)
            return

        # check if the font is installed at user level
        if font_file_name in user_font_name_list:
            logger.debug("Font '%s' found in user directory", font_file_name)
            return

        # check if the font exists as broken link at user level
        # in this case remove it and continue execution
        font_file_user_path = self.FONT_DIR_USER.expanduser() / font_file_name
        if font_file_user_path.is_symlink():
            logger.debug(
                "Dead symbolic link found for font '%s' in user directory, "
                "removing it",
                font_file_name,
            )
            font_file_user_path.unlink(missing_ok=True)

        # then, if the font is not installed, load by copying it
        copy(font_file_path, font_file_user_path)

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
