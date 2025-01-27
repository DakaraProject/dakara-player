from pathlib import Path
from unittest import TestCase
from unittest.mock import PropertyMock, call, patch

from dakara_base.directory import AppDirsPath

from dakara_player import user_resources


class CopyResourceTestCase(TestCase):
    """Test the copy_resource function."""

    @patch("dakara_player.user_resources.copy", autospec=True)
    @patch("dakara_player.user_resources.path", autospec=True)
    @patch("dakara_player.user_resources.contents", autospec=True)
    @patch.object(Path, "mkdir", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_copy(
        self,
        mocked_exists,
        mocked_mkdir,
        mocked_contents,
        mocked_path,
        mocked_copy,
    ):
        """Test to copy files in a non existing directory."""
        mocked_exists.return_value = False
        mocked_contents.return_value = ["file1.ext", "file2.ext", "__init__.py"]
        mocked_path.return_value.__enter__.side_effect = [
            Path("path/to/file1.ext"),
            Path("path/to/file2.ext"),
        ]

        user_resources.copy_resource("package.resources", Path("destination"), False)

        mocked_exists.assert_called_with(Path("destination"))
        mocked_mkdir.assert_called_with(
            Path("destination"), parents=True, exist_ok=True
        )
        mocked_contents.assert_called_with("package.resources")
        mocked_copy.assert_has_calls(
            [
                call(Path("path/to/file1.ext"), Path("destination")),
                call(Path("path/to/file2.ext"), Path("destination")),
            ]
        )

    @patch("dakara_player.user_resources.input")
    @patch("dakara_player.user_resources.copy", autospec=True)
    @patch("dakara_player.user_resources.path", autospec=True)
    @patch("dakara_player.user_resources.contents", autospec=True)
    @patch.object(Path, "mkdir", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_copy_existing_abort(
        self,
        mocked_exists,
        mocked_mkdir,
        mocked_contents,
        mocked_path,
        mocked_copy,
        mocked_input,
    ):
        """Test to copy files in an existing directory and abort."""
        mocked_exists.return_value = True
        mocked_contents.return_value = ["file1.ext", "file2.ext", "__init__.py"]
        mocked_path.return_value.__enter__.side_effect = [
            Path("path/to/file1.ext"),
            Path("path/to/file2.ext"),
        ]
        mocked_input.return_value = "no"

        user_resources.copy_resource("package.resources", Path("destination"), False)

        mocked_exists.assert_called_with(Path("destination"))
        mocked_mkdir.assert_not_called()
        mocked_contents.assert_not_called()
        mocked_copy.assert_not_called()

    @patch("dakara_player.user_resources.input")
    @patch("dakara_player.user_resources.copy", autospec=True)
    @patch("dakara_player.user_resources.path", autospec=True)
    @patch("dakara_player.user_resources.contents", autospec=True)
    @patch.object(Path, "mkdir", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_copy_existing_abort_invalid(
        self,
        mocked_exists,
        mocked_mkdir,
        mocked_contents,
        mocked_path,
        mocked_copy,
        mocked_input,
    ):
        """Test to copy files in an existing directory and abort on invalid input."""
        mocked_exists.return_value = True
        mocked_contents.return_value = ["file1.ext", "file2.ext", "__init__.py"]
        mocked_path.return_value.__enter__.side_effect = [
            Path("path/to/file1.ext"),
            Path("path/to/file2.ext"),
        ]
        mocked_input.return_value = "aaa"

        user_resources.copy_resource("package.resources", Path("destination"), False)

        mocked_exists.assert_called_with(Path("destination"))
        mocked_mkdir.assert_not_called()
        mocked_contents.assert_not_called()
        mocked_copy.assert_not_called()

    @patch("dakara_player.user_resources.input")
    @patch("dakara_player.user_resources.copy", autospec=True)
    @patch("dakara_player.user_resources.path", autospec=True)
    @patch("dakara_player.user_resources.contents", autospec=True)
    @patch.object(Path, "mkdir", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_copy_existing_overwrite(
        self,
        mocked_exists,
        mocked_mkdir,
        mocked_contents,
        mocked_path,
        mocked_copy,
        mocked_input,
    ):
        """Test to copy files in an existing directory and overwrite."""
        mocked_exists.return_value = True
        mocked_contents.return_value = ["file1.ext", "file2.ext", "__init__.py"]
        mocked_path.return_value.__enter__.side_effect = [
            Path("path/to/file1.ext"),
            Path("path/to/file2.ext"),
        ]
        mocked_input.return_value = "yes"

        user_resources.copy_resource("package.resources", Path("destination"), False)

        mocked_exists.assert_called_with(Path("destination"))
        mocked_mkdir.assert_called_with(
            Path("destination"), parents=True, exist_ok=True
        )
        mocked_contents.assert_called_with("package.resources")
        mocked_copy.assert_has_calls(
            [
                call(Path("path/to/file1.ext"), Path("destination")),
                call(Path("path/to/file2.ext"), Path("destination")),
            ]
        )

    @patch("dakara_player.user_resources.input")
    @patch("dakara_player.user_resources.copy", autospec=True)
    @patch("dakara_player.user_resources.path", autospec=True)
    @patch("dakara_player.user_resources.contents", autospec=True)
    @patch.object(Path, "mkdir", autospec=True)
    @patch.object(Path, "exists", autospec=True)
    def test_copy_existing_force(
        self,
        mocked_exists,
        mocked_mkdir,
        mocked_contents,
        mocked_path,
        mocked_copy,
        mocked_input,
    ):
        """Test to force copy files in an existing directory."""
        mocked_exists.return_value = True
        mocked_contents.return_value = ["file1.ext", "file2.ext", "__init__.py"]
        mocked_path.return_value.__enter__.side_effect = [
            Path("path/to/file1.ext"),
            Path("path/to/file2.ext"),
        ]

        user_resources.copy_resource("package.resources", Path("destination"), True)

        mocked_input.assert_not_called()
        mocked_exists.assert_not_called()
        mocked_mkdir.assert_called_with(
            Path("destination"), parents=True, exist_ok=True
        )
        mocked_contents.assert_called_with("package.resources")
        mocked_copy.assert_has_calls(
            [
                call(Path("path/to/file1.ext"), Path("destination")),
                call(Path("path/to/file2.ext"), Path("destination")),
            ]
        )


@patch.object(AppDirsPath, "user_data_dir", new_callable=PropertyMock)
@patch("dakara_player.user_resources.copy_resource", autospec=True)
class CreateResourceFilesTestCase(TestCase):
    """Test the create_resource_files function."""

    @patch.object(Path, "mkdir", autospec=True)
    def test_create(self, mocked_mkdir, mocked_copy_resource, mocked_user_data_dir):
        """Test to create resource files."""
        mocked_user_data_dir.return_value = Path("directory")
        with self.assertLogs("dakara_player.user_resources", "DEBUG") as logger:
            user_resources.create_resource_files()

        mocked_mkdir.assert_called_with(Path("directory"), parents=True, exist_ok=True)
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
                "INFO:dakara_player.user_resources:Resource files "
                "created in 'directory'"
            ],
        )
