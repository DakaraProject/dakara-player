from unittest import TestCase
from unittest.mock import patch

from path import Path

from dakara_player.background_loader import (
    BackgroundLoader,
    BackgroundNotFoundError,
)


@patch("dakara_player.background_loader.path", autospec=True)
@patch.object(Path, "copy", autospec=True)
@patch.object(Path, "exists", autospec=True)
class BackgroundLoaderTestCase(TestCase):
    """Test the loader for backgrounds
    """

    def setUp(self):
        # destination
        self.destination = Path("/") / "destination"

    def test_load_package(self, mocked_exists, mocked_copy, mocked_path):
        """Test to load a background from package
        """
        mocked_exists.return_value = False
        mocked_copy.return_value = Path("/") / "destination" / "background.png"
        mocked_path.return_value.__enter__.return_value = (
            Path("/") / "package" / "background.png"
        )

        # create the instance
        loader = BackgroundLoader(
            destination=self.destination,
            package="package",
            filenames={"background": "background.png"},
        )

        # pre assert that there are no backgrounds
        self.assertDictEqual(loader.backgrounds, {})

        # load the backgrounds
        loader.load()

        # assert the backgrounds
        self.assertDictEqual(
            loader.backgrounds, {"background": self.destination / "background.png"},
        )

        # assert the call of the mocked method
        mocked_exists.assert_not_called()
        mocked_copy.assert_called_with(
            Path("/") / "package" / "background.png", Path("/") / "destination"
        )
        mocked_path.assert_called_with("package", "background.png")

    def test_load_directory(self, mocked_exists, mocked_copy, mocked_path):
        """Test to load a background from directory
        """
        mocked_exists.return_value = True
        mocked_copy.return_value = Path("/") / "destination" / "background.png"

        # create the instance
        loader = BackgroundLoader(
            destination=self.destination,
            package="package",
            directory=Path("/") / "directory",
            filenames={"background": "background.png"},
        )

        # load the backgrounds
        loader.load()

        # assert the backgrounds
        self.assertDictEqual(
            loader.backgrounds, {"background": self.destination / "background.png"}
        )

        # assert the call of the mocked method
        mocked_exists.assert_called_with(Path("/") / "directory" / "background.png")
        mocked_copy.assert_called_with(
            Path("/") / "directory" / "background.png", Path("/") / "destination"
        )
        mocked_path.assert_not_called()

    def test_load_error(self, mocked_exists, mocked_copy, mocked_path):
        """Test to load one unexisting background
        """
        mocked_exists.return_value = False
        mocked_path.return_value.__enter__.side_effect = FileNotFoundError

        # create the instance
        loader = BackgroundLoader(
            destination=self.destination,
            package="package",
            directory=Path("/") / "directory",
            filenames={"idle": "idle.png"},
        )

        # load the backgrounds
        with self.assertRaisesRegex(
            BackgroundNotFoundError, "No idle background file found for 'idle.png'"
        ):
            loader.load()

        # assert the backgrounds
        self.assertDictEqual(loader.backgrounds, {})

        # assert the call of the mocked method
        mocked_exists.assert_called_with(Path("/") / "directory" / "idle.png")
        mocked_copy.assert_not_called()
        mocked_path.assert_called_with("package", "idle.png")
