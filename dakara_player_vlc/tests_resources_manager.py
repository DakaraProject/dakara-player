from unittest import TestCase
from unittest.mock import patch, ANY, call
import os

from dakara_player_vlc.resources_manager import (
    resource_listdir,
    get_file,
    get_background,
    get_test_fixture,
    get_all_fonts,
)


MODULE_PATH = os.path.dirname(os.path.abspath(__file__))


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
        self.assertEqual(result, os.path.join(
            MODULE_PATH,
            "resources/font-awesome.ini"
        ))


class GetBacgkroundTestCase(TestCase):
    """Test the `get_background` function
    """

    @patch('dakara_player_vlc.resources_manager.resource_filename')
    @patch('dakara_player_vlc.resources_manager.LIST_BACKGROUNDS')
    def test_sucess(self, mock_list_background, mock_resource_filename):
        """Test to get a background successfuly
        """
        # mock the call
        mock_list_background.__contains__.return_value = True
        mock_resource_filename.return_value = 'path to bg'

        # call the function
        result = get_background('some bg')

        # assert the call
        mock_list_background.__contains__.assert_called_once_with('some bg')
        mock_resource_filename.assert_called_once_with(ANY, 'some bg')

        # assert the result
        self.assertEqual(result, 'path to bg')

    @patch('dakara_player_vlc.resources_manager.resource_filename')
    @patch('dakara_player_vlc.resources_manager.LIST_BACKGROUNDS')
    def test_fail(self, mock_list_background, mock_resource_filename):
        """Test to get a background that does not exist
        """
        # mock the call
        mock_list_background.__contains__.return_value = False

        # call the function
        with self.assertRaises(IOError):
            get_background('some bg')

        # assert the call
        mock_list_background.__contains__.assert_called_once_with('some bg')
        mock_resource_filename.assert_not_called()

    def test_real(self):
        """Test to access a real background
        """
        # call the function
        result = get_background('idle.png')

        # assert the result
        self.assertEqual(result, os.path.join(
            MODULE_PATH,
            "resources/backgrounds/idle.png"
        ))


class GetTestFixtureTestCase(TestCase):
    """Test the `get_test_fixture` function
    """

    @patch('dakara_player_vlc.resources_manager.resource_filename')
    @patch('dakara_player_vlc.resources_manager.LIST_TEST_FIXTURES')
    def test_sucess(self, mock_list_test_fixture, mock_resource_filename):
        """Test to get a test fixture successfuly
        """
        # mock the call
        mock_list_test_fixture.__contains__.return_value = True
        mock_resource_filename.return_value = 'path to fixture'

        # call the function
        result = get_test_fixture('some fixture')

        # assert the call
        mock_list_test_fixture.__contains__.assert_called_once_with(
            'some fixture')
        mock_resource_filename.assert_called_once_with(ANY, 'some fixture')

        # assert the result
        self.assertEqual(result, 'path to fixture')

    @patch('dakara_player_vlc.resources_manager.resource_filename')
    @patch('dakara_player_vlc.resources_manager.LIST_TEST_FIXTURES')
    def test_fail(self, mock_list_test_fixture, mock_resource_filename):
        """Test to get a test fixture that does not exist
        """
        # mock the call
        mock_list_test_fixture.__contains__.return_value = False

        # call the function
        with self.assertRaises(IOError):
            get_test_fixture('some fixture')

        # assert the call
        mock_list_test_fixture.__contains__.assert_called_once_with(
            'some fixture')
        mock_resource_filename.assert_not_called()

    def test_real(self):
        """Test to access a real test fixture
        """
        # call the function
        result = get_test_fixture('song.ass')

        # assert the result
        self.assertEqual(result, os.path.join(
            MODULE_PATH,
            "resources/tests/song.ass"
        ))


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
            os.path.join(MODULE_PATH,
                         "resources/fonts/fontawesome-webfont.ttf"),
            result
        )
