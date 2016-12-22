import os
import logging
import shutil
import tempfile
from string import Template
from codecs import open

TRANSITION_TEXT_NAME = "transition.ass"

class TransitionTextGenerator:

    def __init__(self, template_path):
        # create logger
        self.logger = logging.getLogger('TransitionTextGenerator')

        # load template
        self.load_text_template(template_path)

        # create temporary directory
        self.create_temp_directory()

        self.transition_text_path = os.path.join(
                self.tempdir,
                TRANSITION_TEXT_NAME
                )

    def with_temp_directory(fun):
        """ Decorator that checks there is a temporary directory created

            The decorator will create a temporary directory and then
            execute the given function.

            Args:
                fun: the function to decorate.

            Returns:
                the decorated function.
        """
        def call(self, *args, **kwargs):
            if self.tempdir is None:
                self.create_temp_directory()

            return fun(self, *args, **kwargs)

        return call

    def create_temp_directory(self):
        """ Create a temporary directory for text generation
        """
        self.tempdir = tempfile.mkdtemp(suffix=".dakara")
        self.logger.debug("Creating temporary directory \"{}\"".format(
            self.tempdir
            ))

    @with_temp_directory
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

        self.logger.debug("Create transition screen text file in \
\"{}\"".format(self.transition_text_path))

        return self.transition_text_path

    def load_text_template(self, template_path):
        """ Load transition text template file

            Load the default or customized ASS template for
            transition screen.
        """
        if os.path.isfile(template_path):
            transition_ass = template_path 

        else:
            self.clean()
            raise IOError("No ASS file for loader found")

        with open(transition_ass, 'r', encoding='utf8') as file:
            transition_text_template = Template(file.read())

        self.transition_text_template = transition_text_template

    def clean(self):
        """ Remove the temp directory
        """
        self.logger.debug("Deleting temporary directory \"{}\"".format(
            self.tempdir
            ))
        try:
            shutil.rmtree(self.tempdir)
            self.tempdir = None

        except OSError:
            self.logger.error("Unable to delete temporary directory")
