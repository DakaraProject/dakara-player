from pkg_resources import resource_filename

from dakara_base.resources_manager import generate_get_resource, resource_listdir
from path import Path


RESOURCES = "dakara_player_vlc.resources"
RESOURCES_BACKGROUNDS = "dakara_player_vlc.resources.backgrounds"
RESOURCES_TEMPLATES = "dakara_player_vlc.resources.templates"
RESOURCES_FONTS = "dakara_player_vlc.resources.fonts"

PATH_BACKGROUNDS = resource_filename(RESOURCES_BACKGROUNDS, "")
PATH_TEMPLATES = resource_filename(RESOURCES_TEMPLATES, "")
PATH_FONTS = resource_filename(RESOURCES_FONTS, "")

LIST_BACKGROUNDS = resource_listdir(RESOURCES_BACKGROUNDS, "")
LIST_TEMPLATES = resource_listdir(RESOURCES_TEMPLATES, "")
LIST_FONTS = resource_listdir(RESOURCES_FONTS, "")


get_background = generate_get_resource(
    RESOURCES_BACKGROUNDS, LIST_BACKGROUNDS, "background"
)


get_template = generate_get_resource(RESOURCES_TEMPLATES, LIST_TEMPLATES, "template")


def get_all_fonts():
    """Get all font resource files

    Returns:
        list of path.Path: list containing the absolute path to the files.
    """
    return [
        Path(resource_filename(RESOURCES_FONTS, filename)) for filename in LIST_FONTS
    ]
