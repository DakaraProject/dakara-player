from unittest import TestCase
from unittest.mock import call, patch

from path import Path

from dakara_player import user_resource_files


class GetUserDirectoryTestCase(TestCase):
    """Test the get_user_directory function."""

    @patch("dakara_player.user_resource_files.sys.platform", "linux")
    def test_get_linux(self):
        """Test get user directory on Linux."""
        self.assertIn(
            Path(".local") / "share" / "dakara" / "player",
            user_resource_files.get_user_directory().expand(),
        )

    @patch("dakara_player.user_resource_files.sys.platform", "win32")
    def test_get_windows(self):
        """Test get user directory on Windows."""
        self.assertIn(
            Path("Dakara") / "player", user_resource_files.get_user_directory().expand()
        )

    @patch("dakara_player.user_resource_files.sys.platform", "unknown")
    def test_get_unknown(self):
        """Test get user directory on unknown OS."""
        with self.assertRaises(NotImplementedError):
            user_resource_files.get_user_directory().expand()


class CopyResourceTestCase(TestCase):
    """Test the copy_resource function."""

    @patch.object(Path, "copy", autospec=True)
    @patch("dakara_player.user_resource_files.path", autospec=True)
    @patch("dakara_player.user_resource_files.contents", autospec=True)
    @patch.object(Path, "makedirs_p", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_copy(
        self,
        mocked_exists,
        mocked_makedirs_p,
        mocked_contents,
        mocked_path,
        mocked_copy,
    ):
        """Test to copy files in a non existing directory."""
        mocked_exists.return_value = False
        mocked_contents.return_value = ["file1.ext", "file2.ext", "__init__.py"]
        mocked_path.return_value.__enter__.side_effect = [
            "path/to/file1.ext",
            "path/to/file2.ext",
        ]

        user_resource_files.copy_resource(
            "package.resources", Path("destination"), False
        )

        mocked_exists.assert_called_with(Path("destination"))
        mocked_makedirs_p.assert_called_with(Path("destination"))
        mocked_contents.assert_called_with("package.resources")
        mocked_copy.assert_has_calls(
            [
                call(Path("path/to/file1.ext"), "destination"),
                call(Path("path/to/file2.ext"), "destination"),
            ]
        )

    @patch("dakara_player.user_resource_files.input")
    @patch.object(Path, "copy", autospec=True)
    @patch("dakara_player.user_resource_files.path", autospec=True)
    @patch("dakara_player.user_resource_files.contents", autospec=True)
    @patch.object(Path, "makedirs_p", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_copy_existing_abort(
        self,
        mocked_exists,
        mocked_makedirs_p,
        mocked_contents,
        mocked_path,
        mocked_copy,
        mocked_input,
    ):
        """Test to copy files in an existing directory and abort."""
        mocked_exists.return_value = True
        mocked_contents.return_value = ["file1.ext", "file2.ext", "__init__.py"]
        mocked_path.return_value.__enter__.side_effect = [
            "path/to/file1.ext",
            "path/to/file2.ext",
        ]
        mocked_input.return_value = "no"

        user_resource_files.copy_resource(
            "package.resources", Path("destination"), False
        )

        mocked_exists.assert_called_with(Path("destination"))
        mocked_makedirs_p.assert_not_called()
        mocked_contents.assert_not_called()
        mocked_copy.assert_not_called()

    @patch("dakara_player.user_resource_files.input")
    @patch.object(Path, "copy", autospec=True)
    @patch("dakara_player.user_resource_files.path", autospec=True)
    @patch("dakara_player.user_resource_files.contents", autospec=True)
    @patch.object(Path, "makedirs_p", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_copy_existing_abort_invalid(
        self,
        mocked_exists,
        mocked_makedirs_p,
        mocked_contents,
        mocked_path,
        mocked_copy,
        mocked_input,
    ):
        """Test to copy files in an existing directory and abort on invalid input."""
        mocked_exists.return_value = True
        mocked_contents.return_value = ["file1.ext", "file2.ext", "__init__.py"]
        mocked_path.return_value.__enter__.side_effect = [
            "path/to/file1.ext",
            "path/to/file2.ext",
        ]
        mocked_input.return_value = "aaa"

        user_resource_files.copy_resource(
            "package.resources", Path("destination"), False
        )

        mocked_exists.assert_called_with(Path("destination"))
        mocked_makedirs_p.assert_not_called()
        mocked_contents.assert_not_called()
        mocked_copy.assert_not_called()

    @patch("dakara_player.user_resource_files.input")
    @patch.object(Path, "copy", autospec=True)
    @patch("dakara_player.user_resource_files.path", autospec=True)
    @patch("dakara_player.user_resource_files.contents", autospec=True)
    @patch.object(Path, "makedirs_p", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_copy_existing_overwrite(
        self,
        mocked_exists,
        mocked_makedirs_p,
        mocked_contents,
        mocked_path,
        mocked_copy,
        mocked_input,
    ):
        """Test to copy files in an existing directory and overwrite."""
        mocked_exists.return_value = True
        mocked_contents.return_value = ["file1.ext", "file2.ext", "__init__.py"]
        mocked_path.return_value.__enter__.side_effect = [
            "path/to/file1.ext",
            "path/to/file2.ext",
        ]
        mocked_input.return_value = "yes"

        user_resource_files.copy_resource(
            "package.resources", Path("destination"), False
        )

        mocked_exists.assert_called_with(Path("destination"))
        mocked_makedirs_p.assert_called_with(Path("destination"))
        mocked_contents.assert_called_with("package.resources")
        mocked_copy.assert_has_calls(
            [
                call(Path("path/to/file1.ext"), "destination"),
                call(Path("path/to/file2.ext"), "destination"),
            ]
        )

    @patch("dakara_player.user_resource_files.input")
    @patch.object(Path, "copy", autospec=True)
    @patch("dakara_player.user_resource_files.path", autospec=True)
    @patch("dakara_player.user_resource_files.contents", autospec=True)
    @patch.object(Path, "makedirs_p", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_copy_existing_force(
        self,
        mocked_exists,
        mocked_makedirs_p,
        mocked_contents,
        mocked_path,
        mocked_copy,
        mocked_input,
    ):
        """Test to force copy files in an existing directory."""
        mocked_exists.return_value = True
        mocked_contents.return_value = ["file1.ext", "file2.ext", "__init__.py"]
        mocked_path.return_value.__enter__.side_effect = [
            "path/to/file1.ext",
            "path/to/file2.ext",
        ]

        user_resource_files.copy_resource(
            "package.resources", Path("destination"), True
        )

        mocked_input.assert_not_called()
        mocked_exists.assert_not_called()
        mocked_makedirs_p.assert_called_with(Path("destination"))
        mocked_contents.assert_called_with("package.resources")
        mocked_copy.assert_has_calls(
            [
                call(Path("path/to/file1.ext"), "destination"),
                call(Path("path/to/file2.ext"), "destination"),
            ]
        )


@patch("dakara_player.user_resource_files.get_user_directory", autospec=True)
@patch("dakara_player.user_resource_files.copy_resource", autospec=True)
class CreateResourceFilesTestCase(TestCase):
    """Test the create_resource_files function."""

    @patch.object(Path, "makedirs_p", autospec=True)
    def test_create(
        self, mocked_makedirs_p, mocked_copy_resource, mocked_get_user_directory
    ):
        """Test to create resource files."""
        mocked_get_user_directory.return_value = Path("directory")
        with self.assertLogs("dakara_player.user_resource_files", "DEBUG") as logger:
            user_resource_files.create_resource_files()

        mocked_makedirs_p.assert_called_with(Path("directory"))
        mocked_copy_resource.assert_has_calls(
            [
                call(
                    "dakara_player.resources.backgrounds",
                    Path("directory") / "backgrounds",
                    False,
                ),
                call(
                    "dakara_player.resources.templates",
                    Path("directory") / "templates",
                    False,
                ),
            ]
        )

        self.assertListEqual(
            logger.output,
            [
                "INFO:dakara_player.user_resource_files:Resource files "
                "created in 'directory'"
            ],
        )
