from unittest import TestCase
from unittest.mock import patch, ANY, call

from path import Path

from dakara_player_vlc.resources_manager import (
    resource_listdir,
    get_file,
    get_background,
    get_test_material,
    get_template,
    get_all_fonts,
    generate_get_resource,
)


MODULE_PATH = Path(__file__).abspath().parent.parent


class ResourceListdirTestCase(TestCase):
    """Test the `resource_listdir` function
    """

    @patch('dakara_player_vlc.resources_manager.resource_listdir_orig')
    def test_no_dunderscore(self, mock_resource_listdir_orig):
        """Test the function does not output entries with dunderscore
        """
        # mock the call
        mock_resource_listdir_orig.return_value = [
            'aaaa.file',
            '__init__.py'
        ]

        # call the function
        result = resource_listdir('some path', '')

        # assert the call
        mock_resource_listdir_orig.assert_called_once_with('some path', '')

        # assert the result
        self.assertListEqual(result, ['aaaa.file'])


class GetFileTestCase(TestCase):
    """Test the `get_file` function
    """

    @patch('dakara_player_vlc.resources_manager.resource_filename')
    @patch('dakara_player_vlc.resources_manager.resource_exists')
    def test_success(self, mock_resource_exists, mock_resource_filename):
        """Test to get a file successfuly
        """
        # mock the call
        mock_resource_exists.return_value = True
        mock_resource_filename.return_value = 'path to resource'

        # call the function
        result = get_file('some resource')

        # assert the call
        mock_resource_exists.assert_called_once_with(ANY, 'some resource')
        mock_resource_filename.assert_called_once_with(ANY, 'some resource')

        # assert the result
        self.assertEqual(result, 'path to resource')

    @patch('dakara_player_vlc.resources_manager.resource_filename')
    @patch('dakara_player_vlc.resources_manager.resource_exists')
    def test_fail(self, mock_resource_exists, mock_resource_filename):
        """Test to get a file that does not exist
        """
        # mock the call
        mock_resource_exists.return_value = False

        # call the function
        with self.assertRaises(IOError):
            get_file('some resource')

        # assert the call
        mock_resource_exists.assert_called_once_with(ANY, 'some resource')
        mock_resource_filename.assert_not_called()

    def test_real(self):
        """Test to access a real file
        """
        # call the function
        result = get_file('font-awesome.ini')

        # assert the result
        self.assertEqual(
            result,
            MODULE_PATH / Path("resources/font-awesome.ini")
        )


class GenerateGetResourceTestCase(TestCase):
    """Test the `generate_get_resource` function factory
    """

    def setUp(self):
        # set up resource type
        self.resource_type = "resource type"

        # set up resource name
        self.resource_name = "some resource"

        # set up resource path
        self.resource_path = "path to some resource"

        # set up resource getter
        self.get_resource = generate_get_resource(
            "resources requirement",
            [self.resource_name],
            self.resource_type
        )

    def test_docstring(self):
        """Test the docstring of the generated function exists
        """
        self.assertIsNotNone(self.get_resource.__doc__)

    @patch('dakara_player_vlc.resources_manager.resource_filename')
    def test_sucess(self, mock_resource_filename):
        """Test to get a resource successfuly
        """
        # mock the call
        mock_resource_filename.return_value = self.resource_path

        # call the function
        result = self.get_resource(self.resource_name)

        # assert the call
        mock_resource_filename.assert_called_once_with(ANY, self.resource_name)

        # assert the result
        self.assertEqual(result, self.resource_path)

    @patch('dakara_player_vlc.resources_manager.resource_filename')
    def test_fail(self, mock_resource_filename):
        """Test to get a resource that does not exist
        """
        # call the function
        with self.assertRaises(IOError) as error:
            get_background("some non-existent resource")
            self.assertEqual(
                str(error),
                "{} file '{}' not found within resources".format(
                    self.resource_type,
                    self.resource_name
                )
            )

        # assert the call
        mock_resource_filename.assert_not_called()


class GetBackgroundTestCase(TestCase):
    """Test the `get_background` function
    """

    def test_real(self):
        """Test to access a real background
        """
        # call the function
        result = get_background('idle.png')

        # assert the result
        self.assertEqual(
            result,
            MODULE_PATH / Path("resources/backgrounds/idle.png")
        )


class GetTestFixtureTestCase(TestCase):
    """Test the `get_test_material` function
    """

    def test_real(self):
        """Test to access a real test material
        """
        # call the function
        result = get_test_material('song.ass')

        # assert the result
        self.assertEqual(
            result,
            MODULE_PATH / Path("resources/tests/song.ass")
        )


class GetTemplateTestCase(TestCase):
    """Test the `get_template` function
    """

    def test_real(self):
        """Test to access a real template
        """
        # call the function
        result = get_template('idle.ass')

        # assert the result
        self.assertEqual(
            result,
            MODULE_PATH / Path("resources/templates/idle.ass")
        )


class GetAllFontsTestCase(TestCase):
    """Test the `get_all_fonts` function
    """

    @patch('dakara_player_vlc.resources_manager.resource_filename')
    @patch('dakara_player_vlc.resources_manager.LIST_FONTS')
    def test(self, mock_list_fonts, mock_resource_filename):
        """Test to get all the fonts
        """
        # mock the call
        mock_list_fonts.__iter__.return_value = ['aa', 'bb']
        mock_resource_filename.side_effect = ['path to aa', 'path to bb']

        # call the function
        result = get_all_fonts()

        # assert the call
        mock_list_fonts.__iter__.assert_called_once_with()
        mock_resource_filename.assert_has_calls([
            call(ANY, 'aa'),
            call(ANY, 'bb')
        ])

        # assert the result
        self.assertListEqual(result, ['path to aa', 'path to bb'])

    def test_real(self):
        """Test there is at least a real font
        """
        # call the function
        result = get_all_fonts()

        # assert the result
        self.assertIn(
            MODULE_PATH / Path("resources/fonts/fontawesome-webfont.ttf"),
            result
        )
