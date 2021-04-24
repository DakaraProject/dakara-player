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

    def test_load_default(self, mocked_exists, mocked_copy, mocked_path):
        """Test to load a default background
        """
        mocked_exists.return_value = False
        mocked_copy.return_value = Path("/") / "destination" / "idle.png"
        mocked_path.return_value.__enter__.return_value = (
            Path("/") / "package" / "idle.png"
        )

        # create the instance
        loader = BackgroundLoader(
            destination=self.destination,
            package="package",
            filenames={"idle": "idle.png"},
        )

        # pre assert that there are no backgrounds
        self.assertDictEqual(loader.backgrounds, {})

        # load the backgrounds
        with self.assertLogs("dakara_player.background_loader", "DEBUG") as logger:
            loader.load()

        # assert the backgrounds
        self.assertDictEqual(
            loader.backgrounds, {"idle": self.destination / "idle.png"},
        )

        # assert logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.background_loader:Loading backgrounds",
                "DEBUG:dakara_player.background_loader:Loading default "
                "idle background file 'idle.png'",
            ],
        )

        # assert the call of the mocked method
        mocked_exists.assert_not_called()
        mocked_copy.assert_called_with(
            Path("/") / "package" / "idle.png", Path("/") / "destination"
        )
        mocked_path.assert_called_with("package", "idle.png")

    def test_load_custom(self, mocked_exists, mocked_copy, mocked_path):
        """Test to load a custom background
        """
        mocked_exists.return_value = True
        mocked_copy.return_value = Path("/") / "destination" / "idle.png"

        # create the instance
        loader = BackgroundLoader(
            destination=self.destination,
            package="package",
            directory=Path("/") / "directory",
            filenames={"idle": "idle.png"},
        )

        # load the backgrounds
        with self.assertLogs("dakara_player.background_loader", "DEBUG") as logger:
            loader.load()

        # assert the backgrounds
        self.assertDictEqual(
            loader.backgrounds, {"idle": self.destination / "idle.png"}
        )

        # assert logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.background_loader:Loading backgrounds",
                "DEBUG:dakara_player.background_loader:Loading custom idle "
                "background file 'idle.png'",
            ],
        )

        # assert the call of the mocked method
        mocked_exists.assert_called_with(Path("/") / "directory" / "idle.png")
        mocked_copy.assert_called_with(
            Path("/") / "directory" / "idle.png", Path("/") / "destination"
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
