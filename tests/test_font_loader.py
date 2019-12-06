import sys
from unittest import TestCase, skipUnless
from unittest.mock import patch, call

from path import Path

from dakara_player_vlc.font_loader import (
    FontLoaderLinux,
    FontLoaderWindows,
    get_font_loader_class,
)


class GetFontLoaderClassTestCase(TestCase):
    """Test font loader class getter
    """

    def test(self):
        """Test to get the correct font loader class for the platform
        """
        # call for Linux
        with patch("dakara_player_vlc.font_loader.sys.platform", "linux"):
            FontLoaderClass = get_font_loader_class()
            self.assertEqual(FontLoaderClass, FontLoaderLinux)

        # call for Windows
        with patch("dakara_player_vlc.font_loader.sys.platform", "win32"):
            FontLoaderClass = get_font_loader_class()
            self.assertEqual(FontLoaderClass, FontLoaderWindows)

        # call for uniplemented OS
        with patch("dakara_player_vlc.font_loader.sys.platform", "other"):
            with self.assertRaises(NotImplementedError) as error:
                get_font_loader_class()

            self.assertEqual(
                str(error.exception),
                "This operating system (other) is not currently supported",
            )


@skipUnless(sys.platform.startswith("linux"), "Can be tested on Linux only")
class FontLoaderLinuxTestCase(TestCase):
    """Test the Linux font loader
    """

    def setUp(self):
        # create directory
        self.directory = Path("directory")

        # create font file list
        self.font_name = "font file"
        self.font_name_list = [self.font_name]
        self.font_path = self.directory / self.font_name
        self.font_path_list = [self.font_path]

        # save user directory
        self.user_directory = Path("~").expanduser()

        # create a font loader object
        with self.assertLogs("dakara_player_vlc.font_loader", "DEBUG"):
            self.font_loader = FontLoaderLinux()

    @patch.object(FontLoaderLinux, "load_from_list")
    @patch("dakara_player_vlc.font_loader.get_all_fonts", autospec=True)
    def test_load_from_resources_directory(
        self, mocked_get_all_fonts, mocked_load_from_list
    ):
        """Test to load fonts from the resources directory
        """
        # mock system calls
        mocked_get_all_fonts.return_value = self.font_path_list

        # call the method
        with self.assertLogs("dakara_player_vlc.font_loader", "DEBUG") as logger:
            self.font_loader.load_from_resources_directory()

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.font_loader:Scanning fonts directory",
                "DEBUG:dakara_player_vlc.font_loader:Found 1 font(s) to load",
            ],
        )

        # call assertions
        mocked_get_all_fonts.assert_called_once_with()
        mocked_load_from_list.assert_called_once_with(self.font_path_list)

    @patch.object(FontLoaderLinux, "load_font")
    def test_load_from_list(self, mocked_load_font):
        """Test to load fonts from list
        """
        # call the method
        with self.assertLogs("dakara_player_vlc.font_loader", "DEBUG") as logger:
            self.font_loader.load_from_list(self.font_path_list)

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.font_loader:Font 'font file' "
                "found to be loaded"
            ],
        )

        # assert the call
        mocked_load_font.assert_called_once_with(self.font_path)

    @patch("dakara_player_vlc.font_loader.os.unlink")
    @patch("dakara_player_vlc.font_loader.os.symlink", autospec=True)
    @patch("dakara_player_vlc.font_loader.isfile", autospec=True)
    def test_load_font_system(self, mocked_isfile, mocked_symlink, mocked_unlink):
        """Test to load one font which is in system directory
        """
        # prepare the mock
        mocked_isfile.return_value = True

        # pre assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player_vlc.font_loader", "DEBUG") as logger:
            self.font_loader.load_font(self.font_path)

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.font_loader:Font 'font file' "
                "found in system directory"
            ],
        )

        # assert the call
        mocked_isfile.assert_called_once_with("/usr/share/fonts/font file")
        mocked_unlink.assert_not_called()
        mocked_symlink.assert_not_called()

        # post assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

    @patch("dakara_player_vlc.font_loader.os.unlink")
    @patch("dakara_player_vlc.font_loader.os.symlink", autospec=True)
    @patch("dakara_player_vlc.font_loader.islink")
    @patch("dakara_player_vlc.font_loader.isfile")
    def test_load_font_user(
        self, mocked_isfile, mocked_islink, mocked_symlink, mocked_unlink
    ):
        """Test to load one font which is in user directory
        """
        # prepare the mock
        mocked_isfile.side_effect = [False, True]
        mocked_islink.return_value = False

        # pre assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player_vlc.font_loader", "DEBUG") as logger:
            self.font_loader.load_font(self.font_path)

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.font_loader:Font 'font file' "
                "found in user directory"
            ],
        )

        # assert the call
        mocked_isfile.assert_has_calls(
            [
                call("/usr/share/fonts/font file"),
                call(self.user_directory / ".fonts/font file"),
            ]
        )
        mocked_islink.assert_not_called()
        mocked_unlink.assert_not_called()
        mocked_symlink.assert_not_called()

        # post assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

    @patch("dakara_player_vlc.font_loader.os.unlink")
    @patch("dakara_player_vlc.font_loader.os.readlink")
    @patch("dakara_player_vlc.font_loader.exists")
    @patch("dakara_player_vlc.font_loader.os.symlink", autospec=True)
    @patch("dakara_player_vlc.font_loader.islink")
    @patch("dakara_player_vlc.font_loader.isfile")
    def test_load_font_user_link_valid(
        self,
        mocked_isfile,
        mocked_islink,
        mocked_symlink,
        mocked_exists,
        mocked_readlink,
        mocked_unlink,
    ):
        """Test to load one font which is in user directory as valid link
        """
        # prepare the mock
        mocked_isfile.side_effect = [False, False]
        mocked_islink.return_value = True
        mocked_exists.return_value = True
        mocked_readlink.return_value = "/real/path/to/font file"

        # pre assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player_vlc.font_loader", "DEBUG") as logger:
            self.font_loader.load_font(self.font_path)

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.font_loader:Font 'font file' "
                "found as symbolic link in user directory"
            ],
        )

        # assert the call
        font_path = self.user_directory / ".fonts/font file"
        mocked_islink.assert_called_with(font_path)
        mocked_exists.assert_called_with("/real/path/to/font file")
        mocked_readlink.assert_called_with(font_path)
        mocked_unlink.assert_not_called()
        mocked_symlink.assert_not_called()

    @patch("dakara_player_vlc.font_loader.os.unlink")
    @patch("dakara_player_vlc.font_loader.os.readlink")
    @patch("dakara_player_vlc.font_loader.exists")
    @patch("dakara_player_vlc.font_loader.os.symlink", autospec=True)
    @patch("dakara_player_vlc.font_loader.islink")
    @patch("dakara_player_vlc.font_loader.isfile")
    def test_load_font_user_link_dead(
        self,
        mocked_isfile,
        mocked_islink,
        mocked_symlink,
        mocked_exists,
        mocked_readlink,
        mocked_unlink,
    ):
        """Test to load one font which is in user directory as dead link
        """
        # prepare the mock
        mocked_isfile.side_effect = [False, False]
        mocked_islink.return_value = True
        mocked_exists.return_value = False
        mocked_readlink.return_value = "/real/path/to/font file"

        # pre assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player_vlc.font_loader", "DEBUG") as logger:
            self.font_loader.load_font(self.font_path)

        # assert effect on logs
        font_path = self.user_directory / ".fonts/font file"
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.font_loader:Dead symbolic link found for "
                "font 'font file' in user directory, removing it",
                "DEBUG:dakara_player_vlc.font_loader:Font 'font file' "
                "loaded in user directory: '{}'".format(font_path),
            ],
        )

        # assert the call
        mocked_islink.assert_called_with(font_path)
        mocked_exists.assert_called_with("/real/path/to/font file")
        mocked_readlink.assert_called_with(font_path)
        mocked_unlink.assert_called_with(font_path)
        mocked_symlink.assert_called_once_with("directory/font file", font_path)

        # post assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 1)

    @patch("dakara_player_vlc.font_loader.os.unlink")
    @patch("dakara_player_vlc.font_loader.os.symlink", autospec=True)
    @patch("dakara_player_vlc.font_loader.islink", autospec=True)
    @patch("dakara_player_vlc.font_loader.isfile", autospec=True)
    def test_load_font_install(
        self, mocked_isfile, mocked_islink, mocked_symlink, mocked_unlink
    ):
        """Test to load one font which is not installed
        """
        # prepare the mock
        mocked_isfile.return_value = False
        mocked_islink.return_value = False

        # pre assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player_vlc.font_loader", "DEBUG") as logger:
            self.font_loader.load_font(self.font_path)

        # assert effect on logs
        font_path = self.user_directory / ".fonts/font file"
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.font_loader:Font 'font file' "
                "loaded in user directory: '{}'".format(font_path)
            ],
        )

        # assert the call
        mocked_isfile.assert_has_calls(
            [
                call("/usr/share/fonts/font file"),
                call(self.user_directory / ".fonts/font file"),
            ]
        )
        mocked_islink.assert_called_with(font_path)
        mocked_unlink.assert_not_called()
        mocked_symlink.assert_called_once_with(
            "directory/font file", self.user_directory / ".fonts/font file"
        )

        # post assertions
        self.assertEqual(len(self.font_loader.fonts_loaded), 1)
        self.assertEqual(
            self.font_loader.fonts_loaded[0], self.user_directory / ".fonts/font file"
        )

    @patch.object(FontLoaderLinux, "load_from_resources_directory")
    @patch("dakara_player_vlc.font_loader.os.mkdir", autospec=True)
    def test_load(self, mocked_mkdir, mocked_load_from_resources_directory):
        """Test to load fonts from main method
        """
        # call the method
        self.font_loader.load()

        # assert the call
        mocked_mkdir.assert_called_once_with(self.user_directory / ".fonts")
        mocked_load_from_resources_directory.assert_called_once_with()

    @patch.object(FontLoaderLinux, "unload_font")
    def test_unload(self, mocked_unload_font):
        """Test to unload fonts
        """
        # set a font as loaded
        self.font_loader.fonts_loaded = self.font_path_list

        # call the method
        self.font_loader.unload()

        # assert the call
        mocked_unload_font.assert_called_once_with(self.font_path)

    @patch("dakara_player_vlc.font_loader.os.unlink", autospec=True)
    def test_unload_font(self, mocked_unlink):
        """Test to unload one font
        """
        # set a font as loaded
        self.font_loader.fonts_loaded = self.font_path_list

        # pre assert there is one font loaded
        self.assertEqual(len(self.font_loader.fonts_loaded), 1)

        # call the method
        with self.assertLogs("dakara_player_vlc.font_loader", "DEBUG") as logger:
            self.font_loader.unload_font(self.font_path)

        # assert effect of logs
        self.assertListEqual(
            logger.output,
            ["DEBUG:dakara_player_vlc.font_loader:Font 'directory/font file' unloaded"],
        )

        # assert the call
        mocked_unlink.assert_called_once_with(self.font_path)

        # assert there are no font loaded anymore
        self.assertEqual(len(self.font_loader.fonts_loaded), 0)
