from pkg_resources import resource_filename, resource_listdir, resource_exists

RESOURCES = "dakara_player_vlc.resources"

RESOURCES_IMAGES = "dakara_player_vlc.resources.images"
RESOURCES_SUBFILES = "dakara_player_vlc.resources.subfiles"
RESOURCES_FONTS = "dakara_player_vlc.resources.fonts"
RESOURCES_TEST_FIXTURES = "dakara_player_vlc.resources.tests"

PATH_IMAGES = resource_filename(RESOURCES_IMAGES, '')
PATH_SUBFILES = resource_filename(RESOURCES_SUBFILES, '')
PATH_FONTS = resource_filename(RESOURCES_FONTS, '')
PATH_TEST_FIXTURES = resource_filename(RESOURCES_TEST_FIXTURES, '')

LIST_IMAGES = resource_listdir(RESOURCES_IMAGES, '')
LIST_SUBFILES = resource_listdir(RESOURCES_SUBFILES, '')
LIST_FONTS = resource_listdir(RESOURCES_FONTS, '')
LIST_TEST_FIXTURES = resource_listdir(RESOURCES_TEST_FIXTURES, '')


def get_file(filename):
    """Get an arbitrary resource file

    Args:
        filename (str): name or path to the file.

    Returns:
        str: absolute path of the file.
    """
    if not resource_exists(RESOURCES, filename):
        raise IOError("File '{}' not found within resources".format(filename))

    return resource_filename(RESOURCES, filename)


def get_image(filename):
    """Get an image within the resource files

    Args:
        filename (str): name of the file to get.

    Returns:
        str: absolute path of the file.
    """
    if filename not in LIST_IMAGES:
        raise IOError(
            "Image file '{}' not found within resources".format(filename)
        )

    return resource_filename(RESOURCES_IMAGES, filename)


def get_all_fonts():
    """Get all font resource files

    Returns:
        list of str: list containing the absolute path to the files.
    """
    return [resource_filename(RESOURCES_FONTS, filename)
            for filename in LIST_FONTS]


def get_test_fixture(filename):
    """Get a test fixture within the resource files

    Args:
        filename (str): name of the file to get.

    Returns:
        str: absolute path of the file.
    """
    if filename not in LIST_TEST_FIXTURES:
        raise IOError(
            "Test fixture '{}' not found within resources".format(filename)
        )

    return resource_filename(RESOURCES_TEST_FIXTURES, filename)
