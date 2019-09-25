import logging
import json

from jinja2 import Environment, FileSystemLoader, ChoiceLoader
from dakara_base.resources_manager import get_file
from dakara_base.exceptions import DakaraError
from path import Path

from dakara_player_vlc.resources_manager import PATH_TEMPLATES


TRANSITION_TEMPLATE_NAME = "transition.ass"
IDLE_TEMPLATE_NAME = "idle.ass"

ICON_MAP_FILE = "font-awesome.json"

LINK_TYPE_NAMES = {
    "OP": "Opening",
    "ED": "Ending",
    "IN": "Insert song",
    "IS": "Image song",
}

logger = logging.getLogger(__name__)


class TextGenerator:
    """Text generator

    This class creates custom ASS contents that are used for idle or transition
    screens. It uses Jinja to populate ASS templates with various informations.

    Example of use:

    >>> from path import Path
    >>> config = {
    ...     "directory": Path("my/directory")
    ... }
    >>> generator = TextGenerator(config)
    >>> generator.load()
    >>> idle_screen_content = generator.create_idle_text({
    ...     "notes": [
    ...         "line1",
    ...         "line2",
    ...     ]
    ... })

    Args:
        config (dict): config dictionary, which may contain the keys
            "directory", "transition_template_name" and "idle_template_name".

    Attributes:
        config (dict): config dictionary.
        directory (path.Path): path to custom templates directory.
        environment (jinja2.Environment): environment for Jinja2.
        transition_template_name (jinja2.Template): template to generate the
            transition text.
        idle_template_name (jinja2.Template): template to generate the idle
            text.
        icon_map (dict): map of icons. Keys are icon name, values are icon character.
    """

    def __init__(self, config):
        self.config = config
        self.directory = Path(config.get("directory", ""))

        # Jinja2 elements
        self.environment = None
        self.transition_template = None
        self.idle_template = None

        # icon map
        self.icon_map = {}

    def load(self):
        """Load the different parts of the class

        Here are the actions with side effect.
        """
        # load icon mapping
        self.load_icon_map()

        # load templates
        self.load_templates()

    def load_icon_map(self):
        """Load the icon map
        """
        icon_map_path = get_file("dakara_player_vlc.resources", ICON_MAP_FILE)
        with icon_map_path.open() as file:
            self.icon_map = json.load(file)

    def load_templates(self):
        """Set up Jinja environment
        """
        # create loaders
        loaders = [FileSystemLoader(self.directory), FileSystemLoader(PATH_TEMPLATES)]

        # create Jinja2 environment
        self.environment = Environment(loader=ChoiceLoader(loaders))

        # add filter for converting font icon name to character
        self.environment.filters["icon"] = self.convert_icon

        # add filter for work link type complete name
        self.environment.filters["link_type_name"] = self.convert_link_type_name

        # load templates
        self.load_transition_template(
            self.config.get("transition_template_name", TRANSITION_TEMPLATE_NAME)
        )

        self.load_idle_template(
            self.config.get("idle_template_name", IDLE_TEMPLATE_NAME)
        )

    def load_transition_template(self, transition_template_name):
        """Load transition screen text template file

        Load the default or customized ASS template for transition screen.

        Args:
            transition_template_name (str): name of the transition template to
                use.
        """
        loader_custom, loader_default = self.environment.loader.loaders

        if transition_template_name in loader_custom.list_templates():
            logger.debug(
                "Loading custom transition template file '%s'", transition_template_name
            )

            self.transition_template = self.environment.get_template(
                transition_template_name
            )

            return

        if TRANSITION_TEMPLATE_NAME in loader_default.list_templates():
            logger.debug("Loading default transition template file")

            self.transition_template = self.environment.get_template(
                TRANSITION_TEMPLATE_NAME
            )

            return

        raise TemplateNotFoundError("No template file for transition screen found")

    def load_idle_template(self, idle_template_name):
        """Load idle screen text template file

        Load the default or customized ASS template for idle screen.

        Args:
            transition_template_name (str): name of the idle template to use.
        """
        loader_custom, loader_default = self.environment.loader.loaders

        if idle_template_name in loader_custom.list_templates():
            logger.debug("Loading custom idle template file '%s'", idle_template_name)

            self.idle_template = self.environment.get_template(idle_template_name)

            return

        if IDLE_TEMPLATE_NAME in loader_default.list_templates():
            logger.debug("Loading default idle template file")

            self.idle_template = self.environment.get_template(IDLE_TEMPLATE_NAME)

            return

        raise TemplateNotFoundError("No template file for idle screen found")

    def convert_icon(self, name):
        """Convert the name of an icon to its code

        Args:
            name (str): name of the icon.

        Returns:
            str: corresponding character.
        """
        if name is None:
            return ""

        return chr(int(self.icon_map.get(name, "0020"), 16))

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
            info (dict): dictionnary of additionnal information.

        Returns:
            str: text containing the idle screen content.
        """
        return self.idle_template.render(**info)

    def create_transition_text(self, playlist_entry):
        """Create custom transition text and save it

        Args:
            playlist_entry (dict): dictionary containing keys for the playlist
                entry.

        Returns:
            str: text containing the transition screen content.
        """
        return self.transition_template.render(playlist_entry)


class TemplateNotFoundError(DakaraError, FileNotFoundError):
    """Error raised when a template cannot be found
    """
