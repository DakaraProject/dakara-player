from unittest import TestCase
from unittest.mock import patch, call, ANY
import logging
import os

from dakara_player_vlc.font_loader import (
        FontLoaderLinux,
        FontLoaderWindows,
        get_font_loader_class,
        SHARE_DIRECTORY_ABSOLUTE,
        FONT_DIRECTORY,
        )


# shut down font loader logging
logging.getLogger('font_loader').setLevel(logging.CRITICAL)


class GetFontLoaderClassTestCase(TestCase):
    """Test font loader class getter
    """
    def test(self):
        """Test to get the correct font loader class for the platform
        """
        # call for Linux
        with patch('dakara_player_vlc.font_loader.sys.platform', "linux"):
            FontLoaderClass = get_font_loader_class()
            self.assertEqual(FontLoaderClass, FontLoaderLinux)

        # call for Windows
        with patch('dakara_player_vlc.font_loader.sys.platform', "win32"):
            FontLoaderClass = get_font_loader_class()
            self.assertEqual(FontLoaderClass, FontLoaderWindows)

        # call for uniplemented OS
        with patch('dakara_player_vlc.font_loader.sys.platform', "other"):
            with self.assertRaises(NotImplementedError):
                get_font_loader_class()


class FontLoaderLinuxTestCase(TestCase):
    """Test the Linux font loader
    """
    def setUp(self):
        # create directory
        self.directory = 'directory'

        # create font file list
        self.font_name = "font file"
        self.font_name_list = [self.font_name]
        self.font_path = os.path.join(self.directory, self.font_name)
        self.font_path_list = [self.font_path]

        # create a font loader object
        self.font_loader = FontLoaderLinux()

    @patch('dakara_player_vlc.font_loader.os.path.isfile')
    def test_load_from_list_installed_system(self, mock_isfile):
        """Test the detection of a font at system level
        """
        # mock the system call
        mock_isfile.return_value = True

        # call the method
        self.font_loader.load_from_list(self.font_path_list)

        # call assertions
        mock_isfile.assert_called_once_with(
                os.path.join(FontLoaderLinux.FONT_DIRECTORY_SYSTEM,
                             self.font_name)
                )

    @patch('dakara_player_vlc.font_loader.os.path.isfile')
    def test_load_from_list_installed_user(self, mock_isfile):
        """Test the detection of a font at user level
        """
        # mock the system call
        mock_isfile.side_effect = (False, True)

        # call the method
        self.font_loader.load_from_list(self.font_path_list)

        # call assertions
        mock_isfile.assert_has_calls((
                call(os.path.join(FontLoaderLinux.FONT_DIRECTORY_SYSTEM,
                                  self.font_name)),
                call(os.path.join(FontLoaderLinux.FONT_DIRECTORY_USER,
                                  self.font_name))
                ))

    @patch('dakara_player_vlc.font_loader.os.symlink')
    @patch('dakara_player_vlc.font_loader.os.path.isfile')
    def test_load_from_list_uninstalled(self, mock_isfile, mock_symlink):
        """Test the installation of a font
        """
        # mock the system call
        mock_isfile.side_effect = (False, False)

        # pre assertions
        self.assertFalse(self.font_loader.fonts_loaded)

        # call the method
        self.font_loader.load_from_list(self.font_path_list)

        # call assertions
        mock_isfile.assert_has_calls((
                call(os.path.join(FontLoaderLinux.FONT_DIRECTORY_SYSTEM,
                                  self.font_name)),
                call(os.path.join(FontLoaderLinux.FONT_DIRECTORY_USER,
                                  self.font_name))
                ))

        font_file_target_path = os.path.join(
                FontLoaderLinux.FONT_DIRECTORY_USER,
                self.font_name
                )

        mock_symlink.assert_called_once_with(
                self.font_path,
                font_file_target_path
                )

        # post assertions
        self.assertEqual(self.font_loader.fonts_loaded,
                         [font_file_target_path])

    @patch('dakara_player_vlc.font_loader.os.path.isfile')
    @patch('dakara_player_vlc.font_loader.os.listdir')
    @patch('dakara_player_vlc.font_loader.os.path.isdir')
    def test_load_from_directory(self, mock_isdir, mock_listdir,
                                 mock_isfile):
        """Test the loading of a font from the directory

        Let's assume the font is present in the system directories.
        """
        # mock system calls
        mock_isdir.return_value = True
        mock_listdir.return_value = self.font_name_list
        mock_isfile.return_value = True

        # pre assertions
        self.assertFalse(self.font_loader.fonts_loaded)

        # call the method
        self.font_loader.load_from_directory(self.directory)

        # call assertions
        mock_isdir.assert_called_once_with(self.directory)
        mock_listdir.assert_called_once_with(self.directory)
        mock_isfile.assert_called_once_with(ANY)

        # post assertions
        self.assertFalse(self.font_loader.fonts_loaded)

    @patch('dakara_player_vlc.font_loader.os.path.isfile')
    @patch('dakara_player_vlc.font_loader.os.listdir')
    @patch('dakara_player_vlc.font_loader.os.path.isdir')
    @patch('dakara_player_vlc.font_loader.os.mkdir')
    def test_load(self, mock_mkdir, mock_isdir, mock_listdir, mock_isfile):
        """Test the loading of a font

        Let's assume the font is present in the system directories.
        """
        directory = os.path.join(
                SHARE_DIRECTORY_ABSOLUTE,
                FONT_DIRECTORY
                )

        # mock system calls
        mock_isdir.return_value = True
        mock_listdir.return_value = self.font_name_list
        mock_isfile.return_value = True

        # pre assertions
        self.assertFalse(self.font_loader.fonts_loaded)

        # call the method
        self.font_loader.load()

        # call assertions
        mock_mkdir.assert_called_once_with(FontLoaderLinux.FONT_DIRECTORY_USER)
        mock_isdir.assert_called_once_with(directory)
        mock_listdir.assert_called_once_with(directory)
        mock_isfile.assert_called_once_with(ANY)

        # post assertions
        self.assertFalse(self.font_loader.fonts_loaded)

    @patch('dakara_player_vlc.font_loader.os.unlink')
    def test_unload(self, mock_unlink):
        """Test to unload a font
        """
        # set a font as loaded
        self.font_loader.fonts_loaded = self.font_path_list

        # pre assertions
        self.assertTrue(self.font_loader.fonts_loaded)

        # call the method
        self.font_loader.unload()

        # call assertions
        mock_unlink.assert_called_once_with(self.font_path)

        # post assertions
        self.assertFalse(self.font_loader.fonts_loaded)
