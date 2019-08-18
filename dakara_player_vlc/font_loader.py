import os
import sys
import logging
from abc import ABC, abstractmethod
from os.path import isfile, islink

from path import Path

from dakara_player_vlc.resources_manager import get_all_fonts, PATH_FONTS


logger = logging.getLogger(__name__)


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
    """

    GREETINGS = "Dummy font loader selected"

    def __init__(self):
        # show type of font loader
        logger.debug(self.GREETINGS)

    @abstractmethod
    def load(self):
        """Load the fonts
        """

    @abstractmethod
    def unload(self):
        """Unload the loaded fonts
        """

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.unload()


class FontLoaderLinux(FontLoader):
    """Font loader for Linux

    It symlinks fonts to load in the user fonts directory. On exit, it
    removes the created symlinks.
    """

    GREETINGS = "Font loader for Linux selected"
    FONT_DIR_SYSTEM = Path("/usr/share/fonts")
    FONT_DIR_USER = Path("~/.fonts")

    def __init__(self):
        # call parent constructor
        super().__init__()

        # create list of fonts
        self.fonts_loaded = []

    def load(self):
        """Load the fonts
        """
        # ensure that the user font directory exists
        try:
            os.mkdir(self.FONT_DIR_USER.expanduser())

        except OSError:
            pass

        # load fonts
        self.load_from_resources_directory()

    def load_from_resources_directory(self):
        """Load all the fonts situated in the resources font directory
        """
        logger.debug("Scanning fonts directory")
        font_file_path_list = get_all_fonts()

        logger.debug("Found %i font(s) to load", len(font_file_path_list))
        self.load_from_list(font_file_path_list)

    def load_from_list(self, font_file_path_list):
        """Load the provided list of fonts

        Args:
            font_file_path_list (list of path.Path): list of absolute path of
                the fonts to load.
        """
        # display list of fonts
        for font_file_path in font_file_path_list:
            font_file_name = font_file_path.basename()
            logger.debug("Font '%s' found to be loaded", font_file_name)

        # load the fonts
        for font_file_path in font_file_path_list:
            self.load_font(font_file_path)

    def load_font(self, font_file_path):
        """Load the provided font

        Args:
            font_file_path (str): absolute path of the font to load.
        """
        # get font file name
        font_file_name = font_file_path.basename()

        # check if the font is installed at system level
        if isfile(self.FONT_DIR_SYSTEM / font_file_name):
            logger.debug("Font '%s' found in system directory", font_file_name)
            return

        # check if the font is installed at user level
        font_file_user_path = self.FONT_DIR_USER.expanduser() / font_file_name

        if isfile(font_file_user_path) or islink(font_file_user_path):
            logger.debug("Font '%s' found in user directory", font_file_name)
            return

        # then, if the font is not installed, load it
        font_file_target_path = self.FONT_DIR_USER.expanduser() / font_file_name

        os.symlink(font_file_path, font_file_target_path)

        # register the font
        self.fonts_loaded.append(font_file_target_path)

        logger.debug(
            "Font '%s' loaded in user directory: '%s'",
            font_file_name,
            font_file_target_path,
        )

    def unload(self):
        """Remove loaded fonts
        """
        for font_path in self.fonts_loaded:
            self.unload_font(font_path)

    def unload_font(self, font_path):
        """Remove the provided font

        Args:
            font_path (str): absolute path of the font to unload.
        """
        try:
            os.unlink(font_path)
            self.fonts_loaded.remove(font_path)
            logger.debug("Font '%s' unloaded", font_path)

        except OSError:
            logger.error("Unable to unload '%s'", font_path)


class FontLoaderWindows(FontLoader):
    """Font loader for Windows

    It cannot do anything, since it is impossible to load fonts on Windows
    programatically, as for now. It simply asks the user to do so.
    """

    GREETINGS = "Font loader for Windows selected"

    def load(self):
        """Prompt the user to load the fonts
        """
        logger.debug("Scanning font directory")
        font_file_path_list = get_all_fonts()

        # since there seems to be no workable way to load fonts on Windows
        # through Python, we ask the user to do it by themselve
        print(
            (
                "Please install the following fonts located in the '{}' "
                "folder and press Enter:"
            ).format(PATH_FONTS)
        )

        for font_file_path in font_file_path_list:
            font_file_name = font_file_path_list.basename()
            print(font_file_name)

        input()

    def unload(self):
        """Promt the user to remove the fonts
        """
        print("You can now remove the installed fonts")
