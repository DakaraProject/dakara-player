"""Generate text screens."""

import json
import logging

from dakara_base.exceptions import DakaraError
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PackageLoader
from path import Path

try:
    from importlib.resources import path

except ImportError:
    from importlib_resources import path


ICON_MAP_FILE = "font-awesome.json"

LINK_TYPE_NAMES = {
    "OP": "Opening",
    "ED": "Ending",
    "IN": "Insert song",
    "IS": "Image song",
}

logger = logging.getLogger(__name__)


class TextGenerator:
    """Generator for text screens.

    It populates text contents that are used for idle or transition screens. It
    uses Jinja under the hood, and can use templates from a custom directory,
    or from a fallback package.

    Example of use:

    >>> from path import Path
    >>> generator = TextGenerator(
    ...     package="package",
    ...     directory=Path("directory"),
    ...     filenames={
    ...         "idle": "idle.ass",
    ...         "transition": "transition.ass",
    ...     },
    ... )
    >>> generator.load()
    >>> idle_screen_content = generator.get_text(
    ...     "idle",
    ...     {
    ...         "notes": [
    ...             "line1",
    ...             "line2",
    ...         ],
    ...     },
    ... )

    Args:
        package (str): Package checked for text templates by default.
        directory (path.Path): Custom directory checked for text templates.
        filenames (dict): Dictionary of text templates filenames. The key is the
            template name, the value the template file name.

    Attributes:
        package (str): Package checked for text templates by default.
        directory (path.Path): Custom directory checked for text templates.
        filenames (dict): Dictionary of text templates filenames. The key is the
            template name, the value the template file name.
        environment (jinja2.Environment): Environment for Jinja2.
        icon_map (dict): Map of icons. Keys are icon name, values are icon character.
    """

    def __init__(self, package, directory=None, filenames=None):
        self.package = package
        self.directory = directory or Path()
        self.filenames = filenames or {}

        # Jinja2 elements
        self.environment = None

        # icon map
        self.icon_map = {}

    def load(self):
        """Load the different parts of the class.

        Here are the actions with side effect.
        """
        # load icon mapping
        self.load_icon_map()

        # load templates
        self.load_templates()

    def load_icon_map(self):
        """Load the icon map."""
        with path("dakara_player.resources", ICON_MAP_FILE) as file:
            self.icon_map = json.loads(file.read_text())

    def load_templates(self):
        """Set up Jinja environment."""
        logger.debug("Loading text templates")

        # create loaders
        loaders = [
            FileSystemLoader(self.directory),
            PackageLoader(*separate_package_last_directory(self.package)),
        ]

        # create Jinja2 environment
        self.environment = Environment(loader=ChoiceLoader(loaders))

        # add filter for converting font icon name to character
        self.environment.filters["icon"] = self.convert_icon

        # add filter for work link type complete name
        self.environment.filters["link_type_name"] = self.convert_link_type_name

        # check loaded templates
        for name, file_name in self.filenames.items():
            self.check_template(name, file_name)

    def get_environment_loaders(self):
        """Return the different loaders used by Jinja.

        Returns:
            list: List of the different loaders.
        """
        return self.environment.loader.loaders

    def check_template(self, template_name, file_name):
        """Check if a template is accessible either custom or default.

        Args:
            template_name (str): Name of the text template.
            file_name (str): Name of the text template file.

        Raises:
            TemplateNotFoundError: If the template can neither be found on
            custom loader, nor default loader.
        """
        loader_custom, loader_default = self.get_environment_loaders()

        if file_name in loader_custom.list_templates():
            logger.debug(
                "Loading custom %s text template file '%s'", template_name, file_name
            )
            return

        if file_name in loader_default.list_templates():
            logger.debug(
                "Loading default %s text template file '%s'", template_name, file_name
            )
            return

        raise TemplateNotFoundError(
            f"No {template_name} text template file found for '{file_name}'"
        )

    def convert_icon(self, name):
        """Convert the name of an icon to its code.

        Args:
            name (str): Name of the icon.

        Returns:
            str: Corresponding character.
        """
        if name is None:
            return ""

        return chr(int(self.icon_map.get(name, "0020"), 16))

    @staticmethod
    def convert_link_type_name(link_type):
        """Convert the short name of a link type to its long name.

        Args:
            link_type (str): Short name of the link type.

        Returns:
            str: Long name of the link type.
        """
        return LINK_TYPE_NAMES[link_type]

    def get_text(self, template_name, data):
        """Generate the text for the desired template.

        Args:
            template_name (str): Name of the text template.
            data (dict): Values to pass to the template.

        Returns:
            str: Generated text from the template with provided values.
        """
        return self.environment.get_template(self.filenames[template_name]).render(
            **data
        )


def separate_package_last_directory(package):
    """Separate last directory from package.

    Args:
        package (str): Package.

    Returns:
        tuple:
            str: Package without last directory.
            str: Last directory.
    """
    *package_list, package_directory = package.split(".")
    return ".".join(package_list), package_directory


class TemplateNotFoundError(DakaraError, FileNotFoundError):
    """Error raised when a template cannot be found."""
