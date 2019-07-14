from unittest import TestCase
from unittest.mock import patch, ANY, call

from path import Path

from dakara_player_vlc.resources_manager import (
    get_background,
    get_test_material,
    get_template,
    get_all_fonts,
)


MODULE_PATH = Path(__file__).abspath().parent.parent


class GetBackgroundTestCase(TestCase):
    """Test the `get_background` function
    """

    def test_real(self):
        """Test to access a real background
        """
        # call the function
        result = get_background("idle.png")

        # assert the result
        self.assertEqual(result, MODULE_PATH / "resources" / "backgrounds" / "idle.png")


class GetTestMaterialTestCase(TestCase):
    """Test the `get_test_material` function
    """

    def test_real(self):
        """Test to access a real test material
        """
        # call the function
        result = get_test_material("song.ass")

        # assert the result
        self.assertEqual(result, MODULE_PATH / "resources" / "tests" / "song.ass")


class GetTemplateTestCase(TestCase):
    """Test the `get_template` function
    """

    def test_real(self):
        """Test to access a real template
        """
        # call the function
        result = get_template("idle.ass")

        # assert the result
        self.assertEqual(result, MODULE_PATH / "resources" / "templates" / "idle.ass")


class GetAllFontsTestCase(TestCase):
    """Test the `get_all_fonts` function
    """

    @patch("dakara_player_vlc.resources_manager.resource_filename")
    @patch("dakara_player_vlc.resources_manager.LIST_FONTS")
    def test(self, mock_list_fonts, mock_resource_filename):
        """Test to get all the fonts
        """
        # mock the call
        mock_list_fonts.__iter__.return_value = ["aa", "bb"]
        mock_resource_filename.side_effect = ["path to aa", "path to bb"]

        # call the function
        result = get_all_fonts()

        # assert the call
        mock_list_fonts.__iter__.assert_called_once_with()
        mock_resource_filename.assert_has_calls([call(ANY, "aa"), call(ANY, "bb")])

        # assert the result
        self.assertListEqual(result, ["path to aa", "path to bb"])

    def test_real(self):
        """Test there is at least a real font
        """
        # call the function
        result = get_all_fonts()

        # assert the result
        self.assertIn(
            MODULE_PATH / "resources" / "fonts" / "fontawesome-webfont.ttf", result
        )
