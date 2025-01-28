import platform
from pathlib import Path
from unittest import TestCase, skipUnless
from unittest.mock import call, patch

from dakara_player.font import (
    FontLoaderLinux,
    FontLoaderNotAvailableError,
    FontLoaderWindows,
    get_font_loader_class,
)


class GetFontLoaderClassTestCase(TestCase):
    """Test font loader class getter."""

    def test(self):
        """Test to get the correct font loader class for the platform."""
        # call for Linux
        with patch("dakara_player.font.platform.system", return_value="Linux"):
            FontLoaderClass = get_font_loader_class()
            self.assertEqual(FontLoaderClass, FontLoaderLinux)

        # call for Windows
        with patch("dakara_player.font.platform.system", return_value="Windows"):
            FontLoaderClass = get_font_loader_class()
            self.assertEqual(FontLoaderClass, FontLoaderWindows)

        # call for uniplemented OS
        with patch("dakara_player.font.platform.system", return_value="other"):
            with self.assertRaisesRegex(
                NotImplementedError,
                r"This operating system \(other\) is not currently supported",
            ):
                get_font_loader_class()


class FontLoaderTestCase(TestCase):
    """Helper to test font loader classes."""

    def setUp(self):
        # create directory
        self.directory = Path("directory")

        # create font file list
        self.font_name = "font_file.ttf"
        self.font_name_list = [self.font_name]
        self.font_path = self.directory / self.font_name
        self.font_path_list = {self.font_name: self.font_path}


class FontLoaderCommonTestCase(FontLoaderTestCase):
    """Test common methods of the font loaders."""

    def get_font_loader(self):
        """Return an instance of the font loader."""
        with self.assertLogs("dakara_player.font", "DEBUG"):
            return FontLoaderLinux("package")

    @patch.object(FontLoaderLinux, "unload")
    def test_context_manager(self, mocked_unload):
        """Test the font loader context manager."""
        with FontLoaderLinux("package"):
            pass

        mocked_unload.assert_called_with()

    @patch("dakara_player.font.contents", autospec=True)
    def test_get_font_name_list(self, mocked_contents):
        """Test to get list of font names."""
        # mock system calls
        mocked_contents.return_value = [self.font_name, "__init__.py"]

        font_loader = self.get_font_loader()

        # call the method
        with self.assertLogs("dakara_player.font", "DEBUG") as logger:
            font_name_list = font_loader.get_font_name_list()

        # assert the result
        self.assertListEqual(font_name_list, self.font_name_list)

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.font:Scanning fonts directory",
                "DEBUG:dakara_player.font:Found 1 font(s) to load",
            ],
        )

        # call assertions
        mocked_contents.assert_called_once_with("package")

    @patch("dakara_player.font.path")
    @patch.object(FontLoaderLinux, "get_font_name_list", autospec=True)
    def test_get_font_path_iterator(self, mocked_get_font_name_list, mocked_path):
        """Test to get iterator of font paths."""
        mocked_get_font_name_list.return_value = self.font_name_list
        mocked_path.return_value.__enter__.return_value = (
            self.directory / self.font_name
        )

        font_loader = self.get_font_loader()

        # call the method
        font_file_path_list = list(font_loader.get_font_path_iterator())

        self.assertListEqual(font_file_path_list, [self.font_path])


@skipUnless(platform.system() == "Linux", "Can be tested on Linux only")
class FontLoaderLinuxTestCase(FontLoaderTestCase):
    """Test the Linux font loader."""

    def setUp(self):
        super().setUp()

        # save user directory
        self.user_directory = Path("~").expanduser()

    def get_font_loader(self):
        """Return an instance of the font loader."""
        with self.assertLogs("dakara_player.font", "DEBUG"):
            return FontLoaderLinux("package")

    @patch.object(FontLoaderLinux, "load_font", autospec=True)
    @patch.object(FontLoaderLinux, "get_font_path_iterator", autospec=True)
    @patch.object(Path, "rglob", autospec=True)
    @patch.object(Path, "mkdir", autospec=True)
    def test_load(
        self,
        mocked_mkdir,
        mocked_rglob,
        mocked_get_font_path_iterator,
        mocked_load_font,
    ):
        """Test to load fonts."""
        # prepare the mock
        mocked_get_font_path_iterator.return_value = (p for p in [self.font_path])
        mocked_rglob.side_effect = [
            [Path("/") / "usr" / "share" / "fonts" / "font1"],
            [self.user_directory / ".fonts" / "font2"],
        ]

        font_loader = self.get_font_loader()

        # call the method
        font_loader.load()

        # assert the call
        mocked_mkdir.assert_called_once_with(
            self.user_directory / ".fonts", parents=True, exist_ok=True
        )
        mocked_rglob.assert_has_calls(
            [
                call(Path("/") / "usr" / "share" / "fonts", "*"),
                call(self.user_directory / ".fonts", "*"),
            ]
        )
        mocked_get_font_path_iterator.assert_called_once_with(font_loader)
        mocked_load_font.assert_called_once_with(
            font_loader,
            self.font_path,
            [Path("/") / "usr" / "share" / "fonts" / "font1"],
            [self.user_directory / ".fonts" / "font2"],
        )

    @patch.object(Path, "unlink", autospec=True)
    @patch("dakara_player.font.copy", autospec=True)
    @patch.object(Path, "is_symlink", autospec=True)
    def test_load_font_system(self, mocked_is_symlink, mocked_copy, mocked_unlink):
        """Test to load one font which is in system directory."""
        font_loader = self.get_font_loader()

        # pre assertions
        self.assertEqual(len(font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player.font", "DEBUG") as logger:
            font_loader.load_font(
                self.font_path,
                [Path("/") / "usr" / "share" / "fonts" / "truetype" / "font_file.ttf"],
                [],
            )

        # post assertions
        self.assertEqual(len(font_loader.fonts_loaded), 0)

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.font:Font 'font_file.ttf' "
                "found in system directory"
            ],
        )

        # assert the call
        mocked_is_symlink.assert_not_called()
        mocked_unlink.assert_not_called()
        mocked_copy.assert_not_called()

    @patch.object(Path, "unlink", autospec=True)
    @patch("dakara_player.font.copy", autospec=True)
    @patch.object(Path, "is_symlink", autospec=True)
    def test_load_font_user(self, mocked_is_symlink, mocked_copy, mocked_unlink):
        """Test to load one font which is in user directory."""
        font_loader = self.get_font_loader()

        # pre assertions
        self.assertEqual(len(font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player.font", "DEBUG") as logger:
            font_loader.load_font(
                self.font_path,
                [],
                [self.user_directory / "fonts" / "truetype" / "font_file.ttf"],
            )

        # post assertions
        self.assertEqual(len(font_loader.fonts_loaded), 0)

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.font:Font 'font_file.ttf' "
                "found in user directory"
            ],
        )

        # assert the call
        mocked_is_symlink.assert_not_called()
        mocked_unlink.assert_not_called()
        mocked_copy.assert_not_called()

    @patch.object(Path, "unlink", autospec=True)
    @patch("dakara_player.font.copy", autospec=True)
    @patch.object(Path, "is_symlink", autospec=True)
    def test_load_font_user_link_dead_install(
        self,
        mocked_is_symlink,
        mocked_copy,
        mocked_unlink,
    ):
        """Test to load one font which is in user directory as dead link."""
        # prepare the mock
        mocked_is_symlink.return_value = True

        font_loader = self.get_font_loader()

        # pre assertions
        self.assertEqual(len(font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player.font", "DEBUG") as logger:
            font_loader.load_font(self.font_path, [], [])

        # post assertions
        self.assertEqual(len(font_loader.fonts_loaded), 1)

        # assert effect on logs
        font_path = self.user_directory / ".fonts/font_file.ttf"
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.font:Dead symbolic link found for "
                "font 'font_file.ttf' in user directory, removing it",
                "DEBUG:dakara_player.font:Font 'font_file.ttf' "
                "loaded in user directory: '{}'".format(font_path),
            ],
        )

        # assert the call
        mocked_is_symlink.assert_called_with(font_path)
        mocked_unlink.assert_called_with(font_path, missing_ok=True)
        mocked_copy.assert_called_once_with(
            Path("directory") / "font_file.ttf", font_path
        )

    @patch.object(Path, "unlink", autospec=True)
    @patch("dakara_player.font.copy", autospec=True)
    @patch.object(Path, "is_symlink", autospec=True)
    def test_load_font_install(self, mocked_is_symlink, mocked_copy, mocked_unlink):
        """Test to load one font which is not installed."""
        # prepare the mock
        mocked_is_symlink.return_value = False

        font_loader = self.get_font_loader()

        # pre assertions
        self.assertEqual(len(font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player.font", "DEBUG") as logger:
            font_loader.load_font(self.font_path, [], [])

        # post assertions
        self.assertEqual(len(font_loader.fonts_loaded), 1)
        self.assertEqual(
            font_loader.fonts_loaded[self.font_name],
            self.user_directory / ".fonts/font_file.ttf",
        )

        # assert effect on logs
        font_path = self.user_directory / ".fonts/font_file.ttf"
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.font:Font 'font_file.ttf' "
                "loaded in user directory: '{}'".format(font_path)
            ],
        )

        # assert the call
        mocked_is_symlink.assert_called_with(font_path)
        mocked_unlink.assert_not_called()
        mocked_copy.assert_called_once_with(
            Path("directory") / "font_file.ttf",
            self.user_directory / ".fonts/font_file.ttf",
        )

    @patch.object(Path, "unlink", autospec=True)
    def test_unload(self, mocked_unlink):
        """Test to unload fonts."""
        font_loader = self.get_font_loader()

        # set a font as loaded
        font_loader.fonts_loaded = {"font1": Path("font1"), "font2": Path("font2")}

        # call the method
        font_loader.unload()

        # assert the call
        # especially check that the unload function does not alter the list of
        # elements we are iterating on
        mocked_unlink.assert_has_calls([call(Path("font1")), call(Path("font2"))])

    @patch.object(Path, "unlink", autospec=True)
    def test_unload_font(self, mocked_unlink):
        """Test to unload one font."""
        font_loader = self.get_font_loader()

        # set a font as loaded
        font_loader.fonts_loaded = self.font_path_list

        # pre assert there is one font loaded
        self.assertEqual(len(font_loader.fonts_loaded), 1)

        # call the method
        with self.assertLogs("dakara_player.font", "DEBUG") as logger:
            font_loader.unload_font(self.font_name)

        # assert there are no font loaded anymore
        self.assertEqual(len(font_loader.fonts_loaded), 0)

        # assert effect of logs
        self.assertListEqual(
            logger.output,
            ["DEBUG:dakara_player.font:Font 'font_file.ttf' unloaded"],
        )

        # assert the call
        mocked_unlink.assert_called_once_with(self.font_path)

    @patch.object(Path, "unlink", autospec=True)
    def test_unload_font_error(self, mocked_unlink):
        """Test to unload one font when unable to remove font."""
        mocked_unlink.side_effect = OSError("error message")

        font_loader = self.get_font_loader()

        # set a font as loaded
        font_loader.fonts_loaded = self.font_path_list

        # pre assert there is one font loaded
        self.assertEqual(len(font_loader.fonts_loaded), 1)

        # call the method
        with self.assertLogs("dakara_player.font", "ERROR") as logger:
            font_loader.unload_font(self.font_name)

        # assert there are no font loaded anymore
        self.assertEqual(len(font_loader.fonts_loaded), 0)

        # assert effect of logs
        self.assertListEqual(
            logger.output,
            [
                "ERROR:dakara_player.font:Font 'font_file.ttf' in "
                "'directory/font_file.ttf' cannot be unloaded: error message"
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
        self.font_path_list = {self.font_name: self.font_path}

    def get_font_loader(self):
        """Return an instance of the font loader."""
        with self.assertLogs("dakara_player.font", "DEBUG"):
            return FontLoaderWindows("package")

    @patch("dakara_player.font.ctypes", spec=[])
    def test_init_no_windll(self, mocked_ctypes):
        """Test to create font loader on a different OS."""
        with self.assertRaisesRegex(
            FontLoaderNotAvailableError, "FontLoaderWindows can only be used on Windows"
        ):
            self.get_font_loader()

    @patch("dakara_player.font.ctypes")
    @patch.object(FontLoaderWindows, "load_font", autospec=True)
    @patch.object(FontLoaderWindows, "get_font_path_iterator", autospec=True)
    def test_load(self, mocked_get_font_path_iterator, mocked_load_font, mocked_ctypes):
        """Test to load fonts."""
        # prepare the mock
        mocked_get_font_path_iterator.return_value = (p for p in [self.font_path])

        font_loader = self.get_font_loader()

        # call the method
        font_loader.load()

        # assert the call
        mocked_get_font_path_iterator.assert_called_once_with(font_loader)
        mocked_load_font.assert_called_once_with(font_loader, self.font_path)

    @patch("dakara_player.font.ctypes")
    def test_load_font(self, mocked_ctypes):
        """Test to load one font."""
        # setup mock
        mocked_ctypes.windll.gdi32.AddFontResourceW.return_value = 1

        font_loader = self.get_font_loader()

        # pre assertions
        self.assertEqual(len(font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player.font", "DEBUG") as logger:
            font_loader.load_font(self.font_path)

        # post assertions
        self.assertEqual(len(font_loader.fonts_loaded), 1)

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            ["DEBUG:dakara_player.font:Font 'font_file.ttf' loaded"],
        )

        # assert the call
        mocked_ctypes.windll.gdi32.AddFontResourceW.assert_called_once_with(
            self.font_path
        )

    @patch("dakara_player.font.ctypes")
    def test_load_font_error(self, mocked_ctypes):
        """Test to fail to load one font."""
        # setup mock
        mocked_ctypes.windll.gdi32.AddFontResourceW.return_value = 0

        font_loader = self.get_font_loader()

        # pre assertions
        self.assertEqual(len(font_loader.fonts_loaded), 0)

        # call the method
        with self.assertLogs("dakara_player.font", "DEBUG") as logger:
            font_loader.load_font(self.font_path)

        # post assertions
        self.assertEqual(len(font_loader.fonts_loaded), 0)

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            ["WARNING:dakara_player.font:Font 'font_file.ttf' cannot be loaded"],
        )

    @patch("dakara_player.font.ctypes")
    @patch.object(FontLoaderWindows, "unload_font")
    def test_unload(self, mocked_unload_font, mocked_ctypes):
        """Test to unload fonts."""
        font_loader = self.get_font_loader()

        # set a font as loaded
        font_loader.fonts_loaded = {"font1": Path("font1"), "font2": Path("font2")}

        # call the method
        font_loader.unload()

        # assert the call
        mocked_unload_font.assert_has_calls([call("font1"), call("font2")])

    @patch("dakara_player.font.ctypes")
    def test_unload_font(self, mocked_ctypes):
        """Test to unload one font."""
        # setup mock
        mocked_ctypes.windll.gdi32.RemoveFontResourceW.return_value = 1

        font_loader = self.get_font_loader()

        # set a font as loaded
        font_loader.fonts_loaded = self.font_path_list

        # pre assert there is one font loaded
        self.assertEqual(len(font_loader.fonts_loaded), 1)

        # call the method
        with self.assertLogs("dakara_player.font", "DEBUG") as logger:
            font_loader.unload_font(self.font_name)

        # assert there are no font loaded anymore
        self.assertEqual(len(font_loader.fonts_loaded), 0)

        # assert effect of logs
        self.assertListEqual(
            logger.output,
            ["DEBUG:dakara_player.font:Font 'font_file.ttf' unloaded"],
        )

        # assert the call
        mocked_ctypes.windll.gdi32.RemoveFontResourceW.assert_called_once_with(
            self.font_path
        )

    @patch("dakara_player.font.ctypes")
    def test_unload_font_error(self, mocked_ctypes):
        """Test to fail to unload one font."""
        # setup mock
        mocked_ctypes.windll.gdi32.RemoveFontResourceW.return_value = 0

        font_loader = self.get_font_loader()

        # set a font as loaded
        font_loader.fonts_loaded = self.font_path_list

        # pre assert there is one font loaded
        self.assertEqual(len(font_loader.fonts_loaded), 1)

        # call the method
        with self.assertLogs("dakara_player.font", "DEBUG") as logger:
            font_loader.unload_font(self.font_name)

        # assert there are no font loaded anymore
        self.assertEqual(len(font_loader.fonts_loaded), 0)

        # assert effect of logs
        self.assertListEqual(
            logger.output,
            [
                "WARNING:dakara_player.font:Font 'font_file.ttf' cannot be unloaded",
            ],
        )
