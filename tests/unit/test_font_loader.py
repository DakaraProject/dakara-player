import sys
from io import StringIO
from unittest import TestCase, skipUnless
from unittest.mock import call, patch

from path import Path

from dakara_player.font_loader import (
    FontLoaderLinux,
    FontLoaderWindows,
    get_font_loader_class,
)


class GetFontLoaderClassTestCase(TestCase):
    """Test font loader class getter."""

    def test(self):
        """Test to get the correct font loader class for the platform."""
        # call for Linux
        with patch("dakara_player.font_loader.sys.platform", "linux"):
            FontLoaderClass = get_font_loader_class()
            self.assertEqual(FontLoaderClass, FontLoaderLinux)

        # call for Windows
        with patch("dakara_player.font_loader.sys.platform", "win32"):
            FontLoaderClass = get_font_loader_class()
            self.assertEqual(FontLoaderClass, FontLoaderWindows)

        # call for uniplemented OS
        with patch("dakara_player.font_loader.sys.platform", "other"):
            with self.assertRaisesRegex(
                NotImplementedError,
                r"This operating system \(other\) is not currently supported",
            ):
                get_font_loader_class()


@skipUnless(sys.platform.startswith("linux"), "Can be tested on Linux only")
class FontLoaderLinuxTestCase(TestCase):
    """Test the Linux font loader."""

    def setUp(self):
        # create directory
        self.directory = Path("directory")

        # create font file list
        self.font_name = "font_file.ttf"
        self.font_name_list = [self.font_name]
        self.font_path = self.directory / self.font_name
        self.font_path_list = [self.font_path]

        # save user directory
        self.user_directory = Path("~").expanduser()

        # create a font loader object
        with self.assertLogs("dakara_player.font_loader", "DEBUG"):
            self.font_loader = FontLoaderLinux()

    @patch.object(FontLoaderLinux, "unload")
    def test_context_manager(self, mocked_unload):
        """Test the font loader context manager."""
        with FontLoaderLinux():
            pass

        mocked_unload.assert_called_with()

    @patch.object(FontLoaderLinux, "load_from_list")
    @patch("dakara_player.font_loader.contents", autospec=True)
    def test_load_from_resources_directory(
        self, mocked_contents, mocked_load_from_list
    ):
        """Test to load fonts from the resources directory."""
        # mock system calls
        mocked_contents.return_value = [self.font_name, "__init__.py"]

        # call the method
        with self.assertLogs("dakara_player.font_loader", "DEBUG") as logger:
            self.font_loader.load_from_resources_directory()

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.font_loader:Scanning fonts directory",
                "DEBUG:dakara_player.font_loader:Found 1 font(s) to load",
            ],
        )

        # call assertions
        mocked_contents.assert_called_once_with("dakara_player.resources.fonts")
        mocked_load_from_list.assert_called_once_with(self.font_name_list)

    @patch("dakara_player.font_loader.path")
    @patch.object(FontLoaderLinux, "load_font")
    def test_load_from_list(self, mocked_load_font, mocked_path):
        """Test to load fonts from list."""
        mocked_path.return_value.__enter__.return_value = (
            self.directory / self.font_name
        )

        # call the method
        with self.assertLogs("dakara_player.font_loader", "DEBUG") as logger:
            self.font_loader.load_from_list(self.font_name_list)

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            ["DEBUG:dakara_player.font_loader:Font 'font_file.ttf' found to be loaded"],
        )

        # assert the call
        mocked_load_font.assert_called_once_with(self.font_path)

    @patch.object(Path, "unlink", autospec=True)
    @patch.object(Path, "symlink", autospec=True)
    @patch.object(Path, "islink", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_load_font_system(
        self, mocked_exists, mocked_islink, mocked_symlink, mocked_unlink
    ):
        """Test to load one font which is in system directory."""
        # prepare the mock
        mocked_exists.return_value = True

        # pre assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player.font_loader", "DEBUG") as logger:
            self.font_loader.load_font(self.font_path)

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.font_loader:Font 'font_file.ttf' "
                "found in system directory"
            ],
        )

        # assert the call
        mocked_exists.assert_called_once_with("/usr/share/fonts/font_file.ttf")
        mocked_islink.assert_not_called()
        mocked_unlink.assert_not_called()
        mocked_symlink.assert_not_called()

        # post assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

    @patch.object(Path, "unlink", autospec=True)
    @patch.object(Path, "symlink", autospec=True)
    @patch.object(Path, "islink", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_load_font_user(
        self, mocked_exists, mocked_islink, mocked_symlink, mocked_unlink
    ):
        """Test to load one font which is in user directory."""
        # prepare the mock
        mocked_exists.side_effect = [False, True]

        # pre assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player.font_loader", "DEBUG") as logger:
            self.font_loader.load_font(self.font_path)

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.font_loader:Font 'font_file.ttf' "
                "found in user directory"
            ],
        )

        # assert the call
        mocked_exists.assert_has_calls(
            [
                call("/usr/share/fonts/font_file.ttf"),
                call(self.user_directory / ".fonts/font_file.ttf"),
            ]
        )
        mocked_islink.assert_not_called()
        mocked_unlink.assert_not_called()
        mocked_symlink.assert_not_called()

        # post assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

    @patch.object(Path, "unlink", autospec=True)
    @patch.object(Path, "symlink", autospec=True)
    @patch.object(Path, "islink", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_load_font_user_link_dead_install(
        self,
        mocked_exists,
        mocked_islink,
        mocked_symlink,
        mocked_unlink,
    ):
        """Test to load one font which is in user directory as dead link."""
        # prepare the mock
        mocked_exists.return_value = False
        mocked_islink.return_value = True

        # pre assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player.font_loader", "DEBUG") as logger:
            self.font_loader.load_font(self.font_path)

        # assert effect on logs
        font_path = self.user_directory / ".fonts/font_file.ttf"
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.font_loader:Dead symbolic link found for "
                "font 'font_file.ttf' in user directory, removing it",
                "DEBUG:dakara_player.font_loader:Font 'font_file.ttf' "
                "loaded in user directory: '{}'".format(font_path),
            ],
        )

        # assert the call
        mocked_exists.assert_has_calls(
            [
                call("/usr/share/fonts/font_file.ttf"),
                call(self.user_directory / ".fonts/font_file.ttf"),
            ]
        )
        mocked_islink.assert_called_with(font_path)
        mocked_unlink.assert_called_with(font_path)
        mocked_symlink.assert_called_once_with("directory/font_file.ttf", font_path)

        # post assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 1)

    @patch.object(Path, "unlink", autospec=True)
    @patch.object(Path, "symlink", autospec=True)
    @patch.object(Path, "islink", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_load_font_install(
        self, mocked_exists, mocked_islink, mocked_symlink, mocked_unlink
    ):
        """Test to load one font which is not installed."""
        # prepare the mock
        mocked_exists.return_value = False
        mocked_islink.return_value = False

        # pre assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player.font_loader", "DEBUG") as logger:
            self.font_loader.load_font(self.font_path)

        # assert effect on logs
        font_path = self.user_directory / ".fonts/font_file.ttf"
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.font_loader:Font 'font_file.ttf' "
                "loaded in user directory: '{}'".format(font_path)
            ],
        )

        # assert the call
        mocked_exists.assert_has_calls(
            [
                call("/usr/share/fonts/font_file.ttf"),
                call(self.user_directory / ".fonts/font_file.ttf"),
            ]
        )
        mocked_islink.assert_called_with(font_path)
        mocked_unlink.assert_not_called()
        mocked_symlink.assert_called_once_with(
            "directory/font_file.ttf", self.user_directory / ".fonts/font_file.ttf"
        )

        # post assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 1)
        self.assertEqual(
            self.font_loader.fonts_loaded[0],
            self.user_directory / ".fonts/font_file.ttf",
        )

    @patch.object(FontLoaderLinux, "load_from_resources_directory")
    @patch("dakara_player.font_loader.os.mkdir", autospec=True)
    def test_load(self, mocked_mkdir, mocked_load_from_resources_directory):
        """Test to load fonts from main method."""
        # call the method
        self.font_loader.load()

        # assert the call
        mocked_mkdir.assert_called_once_with(self.user_directory / ".fonts")
        mocked_load_from_resources_directory.assert_called_once_with()

    @patch.object(FontLoaderLinux, "load_from_resources_directory")
    @patch("dakara_player.font_loader.os.mkdir", autospec=True)
    def test_load_directory_exists(
        self, mocked_mkdir, mocked_load_from_resources_directory
    ):
        """Test to load fonts from main method."""
        mocked_mkdir.side_effect = OSError("error message")

        # call the method
        self.font_loader.load()

    @patch.object(Path, "unlink", autospec=True)
    def test_unload(self, mocked_unlink):
        """Test to unload fonts."""
        # set a font as loaded
        self.font_loader.fonts_loaded = [Path("font1"), Path("font2")]

        # call the method
        self.font_loader.unload()

        # assert the call
        # especially check that the unload function does not alter the list of
        # elements we are iterating on
        mocked_unlink.assert_has_calls([call("font1"), call("font2")])

    @patch.object(Path, "unlink", autospec=True)
    def test_unload_font(self, mocked_unlink):
        """Test to unload one font."""
        # set a font as loaded
        self.font_loader.fonts_loaded = self.font_path_list

        # pre assert there is one font loaded
        self.assertEqual(len(self.font_loader.fonts_loaded), 1)

        # call the method
        with self.assertLogs("dakara_player.font_loader", "DEBUG") as logger:
            self.font_loader.unload_font(self.font_path)

        # assert effect of logs
        self.assertListEqual(
            logger.output,
            ["DEBUG:dakara_player.font_loader:Font 'directory/font_file.ttf' unloaded"],
        )

        # assert the call
        mocked_unlink.assert_called_once_with(self.font_path)

        # assert there are no font loaded anymore
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

    @patch.object(Path, "unlink", autospec=True)
    def test_unload_font_error(self, mocked_unlink):
        """Test to unload one font when unable to remove font."""
        mocked_unlink.side_effect = OSError("error message")

        # set a font as loaded
        self.font_loader.fonts_loaded = self.font_path_list

        # call the method
        with self.assertLogs("dakara_player.font_loader", "ERROR") as logger:
            self.font_loader.unload_font(self.font_path)

        # assert effect of logs
        self.assertListEqual(
            logger.output,
            [
                "ERROR:dakara_player.font_loader:Unable to unload "
                "'directory/font_file.ttf'"
            ],
        )


class FontLoaderWindowsTestCase(TestCase):
    """Test the Windows font loader."""

    def setUp(self):
        # create directory
        self.directory = Path("directory")

        # create font file list
        self.font_name = "font_file.ttf"
        self.font_name_list = [self.font_name]
        self.font_path = self.directory / self.font_name
        self.font_path_list = [self.font_path]

    @patch("dakara_player.font_loader.path")
    @patch("dakara_player.font_loader.input")
    @patch("dakara_player.font_loader.contents")
    def test_load(self, mocked_contents, mocked_input, mocked_path):
        """Test to ask to load fonts manually."""
        mocked_contents.return_value = [self.font_name, "__init__.py"]
        mocked_path.return_value.__enter__.return_value = self.font_path
        output = StringIO()

        font_loader = FontLoaderWindows(output)
        font_loader.load()

        lines = output.getvalue().splitlines()
        self.assertListEqual(
            lines,
            [
                "Please install the following fonts and press Enter:",
                Path("directory") / "font_file.ttf",
            ],
        )

        mocked_contents.assert_called_once_with("dakara_player.resources.fonts")
        mocked_path.assert_called_once_with(
            "dakara_player.resources.fonts", self.font_name
        )
        mocked_input.assert_called_once_with()

    def test_unload(self):
        """Test to ask to unload fonts manually."""
        output = StringIO()
        font_loader = FontLoaderWindows(output)

        font_loader.unload()
        lines = output.getvalue().splitlines()
        self.assertListEqual(lines, ["You can now remove the installed fonts"])
