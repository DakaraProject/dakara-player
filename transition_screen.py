import os
import logging
import shutil
import tempfile
from string import Template
from codecs import open
from settings import LOADER_TEXT_TEMPLATE_NAME, \
                     LOADER_TEXT_TEMPLATE_DEFAULT_NAME, \
                     LOADER_TEXT_NAME, \
                     LOADER_BG_NAME, \
                     LOADER_BG_DEFAULT_NAME


class TransitionScreen:

    def __init__(self):
        # load elements
        self.load_bg_path()
        self.load_text_template()

        # create temporary directory
        self.tempdir = tempfile.mkdtemp(suffix=".dakara")
        logging.debug("Creating temporary directory \"{}\"".format(self.tempdir))

        self.loader_text_path = os.path.join(
                self.tempdir,
                LOADER_TEXT_NAME
                )

    def create_loader(self, playlist_entry):
        """ Create custom loader text and save it

            Args:
                playlist_entry: dictionary containing keys for title,
                    artists and works.

            Returns:
                tuple containing two values:

                `load_bg_path`: path of the background image or video.
                `loader_text_path`: path of the text containing the transition data.
        """
        song = playlist_entry["song"]

        # artists
        artists_string = ", ".join((a["name"] for a in song["artists"]))

        # works
        works_list = song["works"]
        works = []
        for work in works_list:
            work_str = work["work"]["title"]
            subtitle = work["work"]["subtitle"]
            if subtitle:
                work_str += " ({})".format(subtitle)

            work_str += " - {}{}".format(
                    work["link_type"],
                    work["link_type_number"] or ""
                    )

        works_string = ", ".join(works)

        loader_text = self.loader_text_template.substitute(
                title=song["title"],
                artists=artists_string,
                works=works_string
                )

        with open(self.loader_text_path, 'w', encoding='utf8') as file:
            file.write(loader_text)

        logging.debug("Create transition screen text file in \"{}\"".format(self.loader_text_path))

        return self.loader_bg_path, self.loader_text_path

    def load_text_template(self):
        """ Load transition text template file

            Load the default or customized ASS template for
            transition screen.
        """
        if os.path.isfile(LOADER_TEXT_TEMPLATE_NAME):
            loader_ass = LOADER_TEXT_TEMPLATE_NAME

        elif os.path.isfile(LOADER_TEXT_TEMPLATE_DEFAULT_NAME):
            loader_ass = LOADER_TEXT_TEMPLATE_DEFAULT_NAME

        else:
            raise IOError("No ASS file for loader found")

        with open(loader_ass, 'r', encoding='utf8') as file:
            loader_text_template = Template(file.read())

        self.loader_text_template = loader_text_template

    def load_bg_path(self):
        """ Load transition backgound file path

            Load the default or customized background path for
            transition screen.
        """
        if os.path.isfile(LOADER_BG_NAME):
            loader_bg = LOADER_BG_NAME

        elif os.path.isfile(LOADER_BG_DEFAULT_NAME):
            loader_bg = LOADER_BG_DEFAULT_NAME

        else:
            raise IOError("No background file for loader found")

        self.loader_bg_path = loader_bg

    def clean(self):
        """ Remove the temp directory
        """
        logging.debug("Deleting temporary directory \"{}\"".format(self.tempdir))
        shutil.rmtree(self.tempdir)
        self.tempdir = None
