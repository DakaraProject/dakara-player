import os
import sys
import logging
from .daemon import Daemon, stop_on_error


FONT_DIRECTORY = "share"
FONT_FILE_NAME_LIST = (
        "fontawesome-webfont.ttf",
        )


logger = logging.getLogger("font_loader")


def get_font_loader_class():
    if 'linux' in sys.platform:
        return FontLoaderLinux

    if 'win' in sys.platform:
        return FontLoaderWindows

    else:
        raise NotImplementedError(
                "This operating system is not currently supported"
                )


class FontLoader(Daemon):
    GREETINGS = "Dummy font loader selected"

    def init_daemon(self):
        # show type of font loader
        logger.debug(self.GREETINGS)

        # call child init
        self.init_custom()

    def init_custom(self):
        pass

    @stop_on_error
    def load(self):
        pass

    @stop_on_error
    def unload(self):
        pass

    def enter_daemon(self):
        self.load()

    def exit_daemon(self, type, value, traceback):
        self.unload()


class FontLoaderLinux(FontLoader):
    GREETINGS = "Font loader for Linux selected"
    FONT_DIRECTORY_SYSTEM = "/usr/share/fonts"
    FONT_DIRECTORY_USER = os.path.join(os.environ['HOME'], ".fonts")

    @stop_on_error
    def init_custom(self):
        # create list of fonts
        self.fonts_loaded = []

        # ensure that the user font directory exists
        if not os.path.isdir(self.FONT_DIRECTORY_USER):
            os.mkdir(self.FONT_DIRECTORY_USER)

    @stop_on_error
    def load(self):
        for font_file_name in FONT_FILE_NAME_LIST:
            # check if font is in the project font directory
            font_source_path = os.path.join(FONT_DIRECTORY, font_file_name)
            if not os.path.isfile(font_source_path):
                raise IOError("Font '{}' not found in project directories".format(
                    font_file_name
                    ))

            # check if the font is installed at system level
            if os.path.isfile(os.path.join(self.FONT_DIRECTORY_SYSTEM, font_file_name)):
                logger.debug("Font '{}' found in system directory".format(
                    font_file_name
                    ))

                continue

            # check if the font is installed at user level
            if os.path.isfile(os.path.join(self.FONT_DIRECTORY_USER, font_file_name)):
                logger.debug("Font '{}' found in user directory".format(
                    font_file_name
                    ))

                continue

            # if the font is not installed
            font_target_path = os.path.join(self.FONT_DIRECTORY_USER, font_file_name)
            os.symlink(
                    os.path.join(os.getcwd(), font_source_path),
                    font_target_path
                    )

            self.fonts_loaded.append(font_target_path)
            logger.debug("Font '{}' loaded in user directory: '{}'".format(
                font_file_name,
                font_target_path
                ))

    def unload(self):
        for font_path in self.fonts_loaded:
            os.unlink(font_path)
            logger.debug("Font '{}' unloaded".format(
                font_path
                ))

        self.fonts_loaded = []


class FontLoaderWindows(FontLoader):
    GREETINGS = "Font loader for Windows selected"

    @stop_on_error
    def load(self):
        # since there seems to be no workable way to install fonts on Windows
        # through Python, we ask the user to do it by themselve
        print("Please install the following fonts located in the '{}' folder \
and press Enter:".format(FONT_DIRECTORY))

        for font in FONT_FILE_NAME_LIST:
            print(font)

        input()
