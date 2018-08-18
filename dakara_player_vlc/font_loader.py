import os
import sys
import logging
from abc import ABC, abstractmethod

from dakara_player_vlc.resources_manager import get_all_fonts, PATH_FONTS


logger = logging.getLogger("font_loader")


def get_font_loader_class():
    """Get the font loader associated to the current platform

    Returns:
        FontLoader: specialized version of the font loader class.
    """
    if 'linux' in sys.platform:
        return FontLoaderLinux

    if 'win' in sys.platform:
        return FontLoaderWindows

    raise NotImplementedError(
        "This operating system is not currently supported"
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

    It symlinks fonts to install in the user fonts directory. On exit, it
    removes the created symlinks.
    """
    GREETINGS = "Font loader for Linux selected"
    FONT_DIR_SYSTEM = "/usr/share/fonts"
    FONT_DIR_USER = "~/.fonts"

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
            os.mkdir(os.path.expanduser(self.FONT_DIR_USER))

        except OSError:
            pass

        # load fonts
        self.load_from_resources_directory()

    def load_from_resources_directory(self):
        """Load all the fonts situated in the resources font directory
        """
        logger.debug("Scanning font directory")
        font_file_path_list = get_all_fonts()

        for font_file_path in font_file_path_list:
            font_file_name = os.path.basename(font_file_path)
            logger.debug("Font '{}' found to install".format(font_file_name))

        self.load_from_list(font_file_path_list)

    def load_from_list(self, font_file_path_list):
        """Load the provided fonts

        Args:
            font_file_path_list (list of str): list of absolute path of the
                fonts to install.
        """
        for font_file_path in font_file_path_list:
            # get font file name
            font_file_name = os.path.basename(font_file_path)

            # check if the font is installed at system level
            if os.path.isfile(os.path.join(self.FONT_DIR_SYSTEM,
                                           font_file_name)):

                logger.debug(
                    "Font '{}' found in system directory".format(
                        font_file_name
                    )
                )

                continue

            # check if the font is installed at user level
            font_dir_user = os.path.expanduser(self.FONT_DIR_USER)
            font_file_user_path = os.path.join(font_dir_user,
                                               font_file_name)

            if os.path.isfile(font_file_user_path) or \
               os.path.islink(font_file_user_path):

                logger.debug("Font '{}' found in user directory".format(
                    font_file_name
                ))

                continue

            # then, if the font is not installed, install it
            font_file_target_path = os.path.join(
                font_dir_user,
                font_file_name
            )

            os.symlink(
                font_file_path,
                font_file_target_path
            )

            # register the font
            self.fonts_loaded.append(font_file_target_path)

            logger.debug("Font '{}' loaded in user directory: '{}'".format(
                font_file_path,
                font_file_target_path
            ))

    def unload(self):
        """Remove the installed fonts
        """
        for font_path in self.fonts_loaded:
            try:
                os.unlink(font_path)
                logger.debug("Font '{}' unloaded".format(
                    font_path
                ))

            except OSError:
                logger.error("Unable to unload '{}'".format(
                    font_path
                ))

        self.fonts_loaded = []


class FontLoaderWindows(FontLoader):
    """Font loader for Windows

    It cannot do anything, since it is impossible to install fonts on Windows
    programatically, as for now. It simply asks the user to do so.
    """
    GREETINGS = "Font loader for Windows selected"

    def load(self):
        """Prompt the user to install the fonts
        """
        logger.debug("Scanning font directory")
        font_file_path_list = get_all_fonts()

        # since there seems to be no workable way to install fonts on Windows
        # through Python, we ask the user to do it by themselve
        print(("Please install the following fonts located in the '{}' "
               "folder and press Enter:").format(PATH_FONTS))

        for font_file_path in font_file_path_list:
            font_file_name = os.path.basename(font_file_path)
            print(font_file_name)

        input()

    def unload(self):
        """Promt the user to remove the fonts
        """
        print("You can now remove the installed fonts")
