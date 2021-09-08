import ctypes
import logging
import sys
from abc import ABC, abstractmethod

from path import Path

try:
    from importlib.resources import contents, path

except ImportError:
    from importlib_resources import contents, path


logger = logging.getLogger(__name__)

FONT_EXTENSIONS = (".ttf", ".otf")


def get_font_loader_class():
    """Get the font loader associated to the current platform

    Returns:
        FontLoader: specialized version of the font loader class.
    """
    if "linux" in sys.platform:
        return FontLoaderLinux

    if "win" in sys.platform:
        return FontLoaderWindows

    raise NotImplementedError(
        "This operating system ({}) is not currently supported".format(sys.platform)
    )


class FontLoader(ABC):
    """Abstract font loader

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
        """Load the fonts"""

    @abstractmethod
    def unload(self):
        """Unload the loaded fonts"""

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.unload()

    def get_font_name_list(self):
        """Give font names in font package

        Returns:
            list of str: list of font names.
        """
        logger.debug("Scanning fonts directory")
        font_file_name_list = [
            file
            for file in contents(self.package)
            if Path(file).ext.lower() in FONT_EXTENSIONS
        ]
        logger.debug("Found %i font(s) to load", len(font_file_name_list))

        return font_file_name_list

    def get_font_path_iterator(self):
        """Give font paths in font package.

        Yields:
            path.Path: Absolute path to the font, from the package.
        """
        for font_file_name in self.get_font_name_list():
            with path(self.package, font_file_name) as font_file_path:
                yield Path(font_file_path)


class FontLoaderLinux(FontLoader):
    """Font loader for Linux

    It symlinks fonts to load in the user fonts directory. On exit, it
    removes the created symlinks.

    Example of use:

    >>> with FontLoaderLinux() as loader:
    ...     loader.load()
    ...     # do stuff while fonts are loaded
    >>> # now fonts are unloaded

    Args:
        package (str): Package checked for font files.

    Attributes:
        package (str): Package checked for font files.
        font_loader (dict of path.Path): List of loaded fonts. The key is the
            font file name and the value is the path of the installed font in
            user directory.
    """

    GREETINGS = "Font loader for Linux selected"
    FONT_DIR_SYSTEM = Path("/usr/share/fonts")
    FONT_DIR_USER = Path("~/.fonts")

    def __init__(self, *args, **kwargs):
        # call parent constructor
        super().__init__(*args, **kwargs)

        # create list of fonts
        self.fonts_loaded = {}

    def load(self):
        """Load the fonts"""
        # ensure that the user font directory exists
        self.FONT_DIR_USER.expanduser().mkdir_p()

        # load fonts
        for font_file_path in self.get_font_path_iterator():
            self.load_font(font_file_path)

    def load_font(self, font_file_path):
        """Load the provided font

        Args:
            font_file_path (path.Path): absolute path of the font to load.
        """
        # get font file name
        font_file_name = font_file_path.basename()

        # check if the font is installed at system level
        if (self.FONT_DIR_SYSTEM / font_file_name).exists():
            logger.debug("Font '%s' found in system directory", font_file_name)
            return

        # check if the font is installed at user level
        font_file_user_path = self.FONT_DIR_USER.expanduser() / font_file_name

        if font_file_user_path.exists():
            logger.debug("Font '%s' found in user directory", font_file_name)
            return

        # check if the font exists as broken link at user level
        # in this case remove it and continue execution
        if font_file_user_path.islink():
            logger.debug(
                "Dead symbolic link found for font '%s' in user directory, "
                "removing it",
                font_file_name,
            )
            font_file_user_path.unlink()

        # then, if the font is not installed, load it
        font_file_target_path = self.FONT_DIR_USER.expanduser() / font_file_name

        font_file_path.symlink(font_file_target_path)

        # register the font
        self.fonts_loaded[font_file_name] = font_file_target_path

        logger.debug(
            "Font '%s' loaded in user directory: '%s'",
            font_file_name,
            font_file_target_path,
        )

    def unload(self):
        """Remove loaded fonts"""
        for font_file_name in self.fonts_loaded.copy():
            self.unload_font(font_file_name)

    def unload_font(self, font_file_name):
        """Remove the provided font

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
    """Font loader for Windows

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
        gdi32 (ctypes.WinDLL): Handle to the gdi32 library.
        font_loader (dict of path.Path): List of loaded fonts. The key is the
            font file name and the value is the path of font used at
            installation.
    """

    GREETINGS = "Font loader for Windows selected"

    def __init__(self, *args, **kwargs):
        # call parent constructor
        super().__init__(*args, **kwargs)

        # create handle to gdi32 library
        self.gdi32 = ctypes.WinDLL("gdi32.dll")

        # create list of fonts
        self.fonts_loaded = {}

    def load(self):
        """Load the fonts"""
        for font_file_path in self.get_font_path_iterator():
            self.load_font(font_file_path)

    def load_font(self, font_file_path):
        """Load the provided font

        Args:
            font_file_path (path.Path): absolute path of the font to load.
        """
        success = self.gdi32.AddFontResourceW(font_file_path)
        if success:
            self.fonts_loaded[font_file_path.name] = font_file_path
            logger.debug("Font '%s' loaded", font_file_path.name)
            return

        logger.warning("Font '%s' cannot be loaded", font_file_path.name)

    def unload(self):
        """Remove loaded fonts"""
        for font_file_name in self.fonts_loaded.copy():
            self.unload_font(font_file_name)

    def unload_font(self, font_file_name):
        """Remove the provided font

        Args:
            font_file_name (str): Name of the font to unload.
        """
        font_file_path = self.fonts_loaded.pop(font_file_name)
        success = self.gdi32.RemoveFontResourceW(font_file_path)
        if success:
            logger.debug("Font '%s' unloaded", font_file_name)
            return

        logger.warning("Font '%s' cannot be unloaded", font_file_name)
