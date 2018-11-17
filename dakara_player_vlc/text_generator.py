import os
import logging
from codecs import open
from configparser import ConfigParser

from jinja2 import Environment, FileSystemLoader, ChoiceLoader

from dakara_player_vlc.resources_manager import get_file, PATH_TEMPLATES


TRANSITION_TEMPLATE_NAME = "transition.ass"
TRANSITION_TEXT_NAME = "transition.ass"


IDLE_TEMPLATE_NAME = "idle.ass"
IDLE_TEXT_NAME = "idle.ass"


ICON_MAP_FILE = "font-awesome.ini"


LINK_TYPE_NAMES = {
    'OP': "Opening",
    'ED': "Ending",
    'IN': "Insert song",
    'IS': "Image song"
}


logger = logging.getLogger("text_generator")


class TextGenerator:
    """Text generator

    This class creates custom ASS files that are used for idle or transition
    screens. It uses Jinja to populate ASS templates with various informations.
    """
    def __init__(self, config, tempdir):
        self.config = config
        self.tempdir = tempdir

        # load icon mapping
        self.load_icon_map()

        # load templates
        self.load_templates()

        # set text paths
        self.transition_text_path = os.path.join(
            self.tempdir,
            TRANSITION_TEXT_NAME
        )

        self.idle_text_path = os.path.join(
            self.tempdir,
            IDLE_TEXT_NAME
        )

    def load_templates(self):
        """Set up Jinja environment
        """
        # create Jinja2 environment
        self.environment = Environment(
            loader=ChoiceLoader([
                FileSystemLoader(self.config.get('directory', '')),
                FileSystemLoader(PATH_TEMPLATES)
            ])
        )

        # add filter for converting font icon name to character
        self.environment.filters['icon'] = self.convert_icon

        # add filter for work link type complete name
        self.environment.filters['link_type_name'] = (
            self.convert_link_type_name
        )

        # load templates
        self.load_transition_template(
            self.config.get('transition_template_name',
                            TRANSITION_TEMPLATE_NAME)
        )

        self.load_idle_template(
            self.config.get('idle_template_name',
                            IDLE_TEMPLATE_NAME)
        )

    def convert_icon(self, name):
        """Convert the name of an icon to its code

        Args:
            name (str): name of the icon.

        Returns:
            str: corresponding character.
        """
        if name is None:
            return ''

        return chr(int(self.icon_map.get(name, '0020'), 16))

    @staticmethod
    def convert_link_type_name(link_type):
        """Convert the short name of a link type to its long name

        Args:
            link_type (str): short name of the link type.

        Returns:
            str: long name of the link type.
        """
        return LINK_TYPE_NAMES[link_type]

    def create_idle_text(self, info):
        """Create custom idle text and save it

        Args:
            info: dictionnary of additionnal information.

        Returns:
            path of the text containing the idle screen content.
        """
        # using the template
        idle_text = self.idle_template.render(**info)

        with open(self.idle_text_path, 'w', encoding='utf8') as file:
            file.write(idle_text)

        logger.debug("Create idle screen text file in '{}'".
                     format(self.idle_text_path))

        return self.idle_text_path

    def create_transition_text(self, playlist_entry):
        """Create custom transition text and save it

        Args:
            playlist_entry: dictionary containing keys for the playlist
                entry.

        Returns:
            path of the text containing the transition screen content.
        """
        transition_text = self.transition_template.render(playlist_entry)

        with open(self.transition_text_path, 'w', encoding='utf8') as file:
            file.write(transition_text)

        logger.debug("Create transition screen text file in '{}'".
                     format(self.transition_text_path))

        return self.transition_text_path

    def load_icon_map(self):
        """Load the icon map
        """
        icon_map_path = get_file(ICON_MAP_FILE)

        icon_map = ConfigParser()
        icon_map.read(icon_map_path)
        self.icon_map = icon_map['map']

    def load_transition_template(self, transition_template_name):
        """Load transition screen text template file

        Load the default or customized ASS template for transition screen.
        """
        loader_custom, loader_default = self.environment.loader.loaders

        if transition_template_name in loader_custom.list_templates():
            logger.debug(
                "Loading custom transition template file '{}'".format(
                    transition_template_name
                )
            )

            self.transition_template = self.environment.get_template(
                transition_template_name)

            return

        if TRANSITION_TEMPLATE_NAME in loader_default.list_templates():
            logger.debug("Loading default transition template file")

            self.transition_template = self.environment.get_template(
                TRANSITION_TEMPLATE_NAME)

            return

        raise IOError("No template file for transition screen found")

    def load_idle_template(self, idle_template_name):
        """Load idle screen text template file

        Load the default or customized ASS template for idle screen.
        """
        loader_custom, loader_default = self.environment.loader.loaders

        if idle_template_name in loader_custom.list_templates():
            logger.debug(
                "Loading custom idle template file '{}'".format(
                    idle_template_name
                )
            )

            self.idle_template = self.environment.get_template(
                idle_template_name)

            return

        if IDLE_TEMPLATE_NAME in loader_default.list_templates():
            logger.debug("Loading default idle template file")

            self.idle_template = self.environment.get_template(
                IDLE_TEMPLATE_NAME)

            return

        raise IOError("No template file for idle screen found")
