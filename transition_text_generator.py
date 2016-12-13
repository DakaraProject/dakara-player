import os
import logging
import shutil
import tempfile
from string import Template
from codecs import open

TRANSITION_TEXT_NAME = "transition.ass"

class TransitionTextGenerator:

    def __init__(self, template_path):
        # load template 
        self.load_text_template(template_path)

        # create temporary directory
        self.tempdir = tempfile.mkdtemp(suffix=".dakara")
        logging.debug("Creating temporary directory \"{}\"".format(self.tempdir))

        self.transition_text_path = os.path.join(
                self.tempdir,
                TRANSITION_TEXT_NAME
                )

    def create_transition_text(self, playlist_entry):
        """ Create custom transition text and save it

            Args:
                playlist_entry: dictionary containing keys for title,
                    artists and works.

            Returns:
                path of the text containing the transition data.
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

            works.append(work_str)

        works_string = ", ".join(works)

        transition_text = self.transition_text_template.substitute(
                title=song["title"],
                artists=artists_string,
                works=works_string
                )

        with open(self.transition_text_path, 'w', encoding='utf8') as file:
            file.write(transition_text)

        logging.debug("Create transition screen text file in \"{}\"".format(self.transition_text_path))

        return self.transition_text_path

    def load_text_template(self, template_path):
        """ Load transition text template file

            Load the default or customized ASS template for
            transition screen.
        """
        if os.path.isfile(template_path):
            transition_ass = template_path 

        else:
            raise IOError("No ASS file for loader found")

        with open(transition_ass, 'r', encoding='utf8') as file:
            transition_text_template = Template(file.read())

        self.transition_text_template = transition_text_template

#    def load_bg_path(self):
#        """ Load transition backgound file path
#
#            Load the default or customized background path for
#            transition screen.
#        """
#        if os.path.isfile(transition_BG_NAME):
#            transition_bg = transition_BG_NAME
#
#        elif os.path.isfile(transition_BG_DEFAULT_NAME):
#            transition_bg = transition_BG_DEFAULT_NAME
#
#        else:
#            raise IOError("No background file for loader found")
#
#        self.transition_bg_path = transition_bg

    def clean(self):
        """ Remove the temp directory
        """
        logging.debug("Deleting temporary directory \"{}\"".format(self.tempdir))
        shutil.rmtree(self.tempdir)
        self.tempdir = None
