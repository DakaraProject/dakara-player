from pkg_resources import resource_filename

from dakara_base.resources_manager import resource_listdir, generate_get_resource


RESOURCES = "dakara_player_vlc.resources"
RESOURCES_BACKGROUNDS = "dakara_player_vlc.resources.backgrounds"
RESOURCES_TEMPLATES = "dakara_player_vlc.resources.templates"
RESOURCES_FONTS = "dakara_player_vlc.resources.fonts"
RESOURCES_TEST_MATERIALS = "dakara_player_vlc.resources.tests"

PATH_BACKGROUNDS = resource_filename(RESOURCES_BACKGROUNDS, "")
PATH_TEMPLATES = resource_filename(RESOURCES_TEMPLATES, "")
PATH_FONTS = resource_filename(RESOURCES_FONTS, "")
PATH_TEST_MATERIALS = resource_filename(RESOURCES_TEST_MATERIALS, "")

LIST_BACKGROUNDS = resource_listdir(RESOURCES_BACKGROUNDS, "")
LIST_TEMPLATES = resource_listdir(RESOURCES_TEMPLATES, "")
LIST_FONTS = resource_listdir(RESOURCES_FONTS, "")
LIST_TEST_MATERIALS = resource_listdir(RESOURCES_TEST_MATERIALS, "")


get_background = generate_get_resource(
    RESOURCES_BACKGROUNDS, LIST_BACKGROUNDS, "background"
)


get_template = generate_get_resource(RESOURCES_TEMPLATES, LIST_TEMPLATES, "template")


get_test_material = generate_get_resource(
    RESOURCES_TEST_MATERIALS, LIST_TEST_MATERIALS, "test material"
)


def get_all_fonts():
    """Get all font resource files

    Returns:
        list of str: list containing the absolute path to the files.
    """
    return [resource_filename(RESOURCES_FONTS, filename) for filename in LIST_FONTS]
