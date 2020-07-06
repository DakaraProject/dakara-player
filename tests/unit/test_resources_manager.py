from unittest import TestCase
from unittest.mock import ANY, call, patch

from path import Path
from dakara_base.resources_manager import get_file

from dakara_player_vlc.resources_manager import (
    get_all_fonts,
    get_background,
    get_template,
)


MODULE_PATH = get_file("dakara_player_vlc", "")


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

    @patch("dakara_player_vlc.resources_manager.resource_filename", autospec=True)
    @patch("dakara_player_vlc.resources_manager.LIST_FONTS", autospec=True)
    def test(self, mocked_list_fonts, mocked_resource_filename):
        """Test to get all the fonts
        """
        # mock the call
        mocked_list_fonts.__iter__.return_value = ["aa", "bb"]
        mocked_resource_filename.side_effect = ["path/to/aa", "path/to/bb"]

        # call the function
        result = get_all_fonts()

        # assert the call
        mocked_list_fonts.__iter__.assert_called_once_with()
        mocked_resource_filename.assert_has_calls([call(ANY, "aa"), call(ANY, "bb")])

        # assert the result
        self.assertListEqual(result, [Path("path/to/aa"), Path("path/to/bb")])

    def test_real(self):
        """Test there is at least a real font
        """
        # call the function
        result = get_all_fonts()

        # assert the result
        self.assertIn(
            MODULE_PATH / "resources" / "fonts" / "fontawesome-webfont.ttf", result
        )
