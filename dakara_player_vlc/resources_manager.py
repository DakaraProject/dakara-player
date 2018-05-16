from pkg_resources import (
    resource_filename,
    resource_listdir as resource_listdir_orig,
    resource_exists,
)

RESOURCES = "dakara_player_vlc.resources"

RESOURCES_BACKGROUNDS = "dakara_player_vlc.resources.backgrounds"
RESOURCES_TEMPLATES = "dakara_player_vlc.resources.templates"
RESOURCES_FONTS = "dakara_player_vlc.resources.fonts"
RESOURCES_TEST_FIXTURES = "dakara_player_vlc.resources.tests"

PATH_BACKGROUNDS = resource_filename(RESOURCES_BACKGROUNDS, '')
PATH_TEMPLATES = resource_filename(RESOURCES_TEMPLATES, '')
PATH_FONTS = resource_filename(RESOURCES_FONTS, '')
PATH_TEST_FIXTURES = resource_filename(RESOURCES_TEST_FIXTURES, '')


def resource_listdir(*args, **kwargs):
    """List resources without special files
    """
    return [filename for filename in resource_listdir_orig(*args, **kwargs)
            if not filename.startswith('__')]


LIST_BACKGROUNDS = resource_listdir(RESOURCES_BACKGROUNDS, '')
LIST_TEMPLATES = resource_listdir(RESOURCES_TEMPLATES, '')
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


def generate_get_resource(resource, resource_list, resource_name):
    """Function factory for resource getter

    Args:
        resource (str): requirement.
        resource_list (list of str): list of files within the requirement.
        resource_name (str): human readable name of the resource.

    Returns:
        function: resource getter.
    """

    def get_resource(filename):
        """Get a resource within the resource files

        Args:
            filename (str): name of the file to get.

        Returns:
            str: absolute path of the file.
        """
        if filename not in resource_list:
            raise IOError(
                "{} file '{}' not found within resources".format(
                    resource_name.capitalize(),
                    filename
                )
            )

        return resource_filename(resource, filename)

    return get_resource


get_background = generate_get_resource(RESOURCES_BACKGROUNDS, LIST_BACKGROUNDS,
                                       'background')
get_template = generate_get_resource(RESOURCES_TEMPLATES, LIST_TEMPLATES,
                                     'template')
get_test_fixture = generate_get_resource(RESOURCES_TEST_FIXTURES,
                                         LIST_TEST_FIXTURES,
                                         'test fixture')


def get_all_fonts():
    """Get all font resource files

    Returns:
        list of str: list containing the absolute path to the files.
    """
    return [resource_filename(RESOURCES_FONTS, filename)
            for filename in LIST_FONTS]
