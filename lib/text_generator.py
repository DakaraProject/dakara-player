import os
import logging
import shutil
import tempfile
from string import Template
from codecs import open

SHARE_DIR = 'share'

TRANSITION_TEMPLATE_NAME = "transition.ass"
TRANSITION_TEMPLATE_PATH = os.path.join(SHARE_DIR, TRANSITION_TEMPLATE_NAME)

TRANSITION_TEXT_NAME = "transition.ass"

IDLE_TEMPLATE_NAME = "idle.ass"
IDLE_TEMPLATE_PATH = os.path.join(SHARE_DIR, IDLE_TEMPLATE_NAME)

IDLE_TEXT_NAME = "idle.ass"

class TextGenerator:

    def __init__(self, transition_template_path, idle_template_path):
        # create logger
        self.logger = logging.getLogger('TextGenerator')

        # load templates
        self.load_transition_template(transition_template_path)
        self.load_idle_template(idle_template_path)

        # create temporary directory
        self.create_temp_directory()

        # set text paths
        self.transition_text_path = os.path.join(
                self.tempdir,
                TRANSITION_TEXT_NAME
                )

        self.idle_text_path = os.path.join(
                self.tempdir,
                IDLE_TEXT_NAME
                )

    def with_temp_directory(fun):
        """ Decorator that checks there is a temporary
            directory created

            The decorator will create a temporary directory
            and then execute the given function.

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
    def create_idle_text(self, info):
        """ Create custom idle text and save it

            The acceptable placeholders in the template are:
                - `vlc_version`: version of VLC.

            Args:
                info: dictionnary of additionnal information.

            Returns:
                path of the text containing the idle screen content.
        """
        # using the template
        idle_text = self.idle_template.substitute(
                **info
                )

        with open(self.idle_text_path, 'w', encoding='utf8') as file:
            file.write(idle_text)

        self.logger.debug("Create idle screen text file in \
\"{}\"".format(self.idle_text_path))

        return self.idle_text_path


    @with_temp_directory
    def create_transition_text(self, playlist_entry):
        """ Create custom transition text and save it

            The accepted placeholders in the template are:
                - `title`: song title,
                - `artists`: list of artists,
                - `works`: list of works.

            Args:
                playlist_entry: dictionary containing keys for title,
                    artists and works.

            Returns:
                path of the text containing the transition screen
                content.
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

        transition_text = self.transition_template.substitute(
                title=song["title"],
                artists=artists_string,
                works=works_string
                )

        with open(self.transition_text_path, 'w', encoding='utf8') as file:
            file.write(transition_text)

        self.logger.debug("Create transition screen text file in \
\"{}\"".format(self.transition_text_path))

        return self.transition_text_path

    def load_transition_template(self, template_path):
        """ Load transition screen text template file

            Load the default or customized ASS template for
            transition screen.
        """
        if os.path.isfile(template_path):
            pass

        elif os.path.isfile(TRANSITION_TEMPLATE_PATH):
            self.logger.warning("Transition template file not found \"{}\", \
using default one".format(template_path))

            template_path = TRANSITION_TEMPLATE_PATH

        else:
            self.clean()
            raise IOError("No template file for transition screen found")

        with open(template_path, 'r', encoding='utf8') as file:
            transition_template = Template(file.read())

        self.transition_template = transition_template

        self.logger.debug("Loading transition template file \"{}\"".format(
            template_path
            ))

    def load_idle_template(self, template_path):
        """ Load idle screen text template file

            Load the default or customized ASS template for
            idle screen.
        """
        if os.path.isfile(template_path):
            pass

        elif os.path.isfile(IDLE_TEMPLATE_PATH):
            self.logger.warning("Idle template file not found \"{}\", \
using default one".format(template_path))

            template_path = IDLE_TEMPLATE_PATH

        else:
            self.clean()
            raise IOError("No template file for idle screen found")

        with open(template_path, 'r', encoding='utf8') as file:
            idle_template = Template(file.read())

        self.idle_template = idle_template

        self.logger.debug("Loading idle template file \"{}\"".format(
            template_path
            ))

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
