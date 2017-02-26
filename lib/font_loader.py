import os
import sys
import logging

FONT_FILE_NAME_LIST = (
        "fontawesome-webfont.ttf",
        )

FONT_DIRECTORY = "share"
FONT_DIRECTORY_SYSTEM = "/usr/share/fonts"
FONT_DIRECTORY_USER = os.path.join(os.environ['HOME'], ".local/share/fonts")

class FontLoader:
    def __init__(self):
        self.fonts_loaded = []
        self.logger = logging.getLogger('FontLoader')

    def load(self):
        for font_file_name in FONT_FILE_NAME_LIST:
            # check if font is in the project font directory
            font_source_path = os.path.join(FONT_DIRECTORY, font_file_name)
            if not os.path.isfile(font_source_path):
                raise IOError("Font '{}' not found in project directories".format(
                    font_file_name
                    ))

            # check if the font is installed at system level
            if os.path.isfile(os.path.join(FONT_DIRECTORY_SYSTEM, font_file_name)):
                self.logger.debug("Font '{}' found in system directory".format(
                    font_file_name
                    ))

                continue

            # check if the font is installed at user level
            if os.path.isfile(os.path.join(FONT_DIRECTORY_USER, font_file_name)):
                self.logger.debug("Font '{}' found in user directory".format(
                    font_file_name
                    ))

                continue

            # if the font is not installed
            font_target_path = os.path.join(FONT_DIRECTORY_USER, font_file_name)
            os.symlink(
                    os.path.join(os.getcwd(), font_source_path),
                    font_target_path
                    )

            self.fonts_loaded.append(font_target_path)
            self.logger.debug("Font '{}' loaded in user directory: '{}'".format(
                font_file_name,
                font_target_path
                ))

    def unload(self):
        for font_path in self.fonts_loaded:
            os.unlink(font_path)
            self.logger.debug("Font '{}' unloaded".format(
                font_path
                ))

        self.fonts_loaded = []


