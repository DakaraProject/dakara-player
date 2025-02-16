from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from dakara_player.background import BackgroundLoader, BackgroundNotFoundError


class BackgroundLoaderTestCase(TestCase):
    """Test the loader for backgrounds."""

    @patch.object(BackgroundLoader, "get_background_path", autospec=True)
    def test_load(self, mocked_get_background_path):
        """Test to load backgrounds."""
        mocked_get_background_path.return_value = Path("destination") / "idle.png"

        # create the instance
        loader = BackgroundLoader(
            destination=Path("destination"),
            package="package",
            directory=Path("directory"),
            filenames={"idle": "idle.png"},
        )

        # pre assert that there are no backgrounds
        self.assertDictEqual(loader.backgrounds, {})

        # load the backgrounds
        with self.assertLogs("dakara_player.background", "DEBUG") as logger:
            loader.load()

        # assert the backgrounds
        self.assertDictEqual(
            loader.backgrounds, {"idle": Path("destination") / "idle.png"}
        )

        # assert logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.background:Loading backgrounds",
            ],
        )

        # assert mocks
        mocked_get_background_path.assert_called_with(loader, "idle", "idle.png")

    @patch.object(BackgroundLoader, "copy_default_background", autospec=True)
    @patch.object(BackgroundLoader, "copy_custom_background", autospec=True)
    def test_get_background_path_custom(
        self, mocked_copy_custom_background, mocked_copy_default_background
    ):
        """Test to get a custom background."""
        mocked_copy_custom_background.return_value = Path("destination") / "idle.png"

        # create the instance
        loader = BackgroundLoader(
            destination=Path("destination"),
            package="package",
            directory=Path("directory"),
        )

        # get the backgrounds
        path = loader.get_background_path("idle", "idle.png")

        # assert the backgrounds
        self.assertEqual(path, Path("destination") / "idle.png")

        # assert the call of the mocked method
        mocked_copy_custom_background.assert_called_with(loader, "idle", "idle.png")
        mocked_copy_default_background.assert_not_called()

    @patch.object(BackgroundLoader, "copy_default_background", autospec=True)
    @patch.object(BackgroundLoader, "copy_custom_background", autospec=True)
    def test_get_background_path_default(
        self, mocked_copy_custom_background, mocked_copy_default_background
    ):
        """Test to get a default background."""
        mocked_copy_default_background.return_value = Path("destination") / "idle.png"

        # create the instance
        loader = BackgroundLoader(destination=Path("destination"), package="package")

        # get the backgrounds
        path = loader.get_background_path("idle", "idle.png")

        # assert the backgrounds
        self.assertEqual(path, Path("destination") / "idle.png")

        # assert the call of the mocked method
        mocked_copy_custom_background.assert_not_called()
        mocked_copy_default_background.assert_called_with(loader, "idle", "idle.png")

    @patch.object(BackgroundLoader, "copy_default_background", autospec=True)
    @patch.object(BackgroundLoader, "copy_custom_background", autospec=True)
    def test_get_background_path_custom_not_found(
        self, mocked_copy_custom_background, mocked_copy_default_background
    ):
        """Test to get a default background after trying to get a custom one."""
        mocked_copy_custom_background.side_effect = FileNotFoundError()
        mocked_copy_default_background.return_value = Path("destination") / "idle.png"

        # create the instance
        loader = BackgroundLoader(
            destination=Path("destination"),
            package="package",
            directory=Path("directory"),
        )

        # get the backgrounds
        path = loader.get_background_path("idle", "idle.png")

        # assert the backgrounds
        self.assertEqual(path, Path("destination") / "idle.png")

        # assert the call of the mocked method
        mocked_copy_custom_background.assert_called_with(loader, "idle", "idle.png")
        mocked_copy_default_background.assert_called_with(loader, "idle", "idle.png")

    @patch.object(BackgroundLoader, "copy_default_background", autospec=True)
    @patch.object(BackgroundLoader, "copy_custom_background", autospec=True)
    def test_get_background_path_default_not_found(
        self, mocked_copy_custom_background, mocked_copy_default_background
    ):
        """Test to get a unexisting background."""
        mocked_copy_default_background.side_effect = FileNotFoundError()

        # create the instance
        loader = BackgroundLoader(
            destination=Path("destination"),
            package="package",
        )

        # get the backgrounds
        with self.assertRaisesRegex(
            BackgroundNotFoundError, "No idle background file found for 'idle.png'"
        ):
            loader.get_background_path("idle", "idle.png")

        # assert the call of the mocked method
        mocked_copy_custom_background.assert_not_called()
        mocked_copy_default_background.assert_called_with(loader, "idle", "idle.png")

    @patch("dakara_player.background.copy", autospec=True)
    def test_copy_custom_background(self, mocked_copy):
        """Test to copy a custom background."""
        mocked_copy.return_value = str(Path("destination") / "idle.png")

        # create the instance
        loader = BackgroundLoader(
            destination=Path("destination"),
            package="package",
            directory=Path("directory"),
        )

        # copy the backgrounds
        with self.assertLogs("dakara_player.background", "DEBUG") as logger:
            output_path = loader.copy_custom_background("idle", "idle.png")

        # assert the background
        self.assertEqual(output_path, Path("destination") / "idle.png")

        # assert logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.background:Loading custom idle "
                "background file 'idle.png'",
            ],
        )

        # assert the call of the mocked method
        mocked_copy.assert_called_with(
            Path("directory") / "idle.png", Path("destination")
        )

    @patch("dakara_player.background.copy", autospec=True)
    @patch("dakara_player.background.as_file", autospec=True)
    @patch("dakara_player.background.files", autospec=True)
    def test_copy_default_background(self, mocked_files, mocked_as_file, mocked_copy):
        """Test to copy a default background."""
        mocked_as_file.return_value.__enter__.return_value = (
            Path("package") / "idle.png"
        )
        mocked_copy.return_value = str(Path("destination") / "idle.png")

        # create the instance
        loader = BackgroundLoader(
            destination=Path("destination"),
            package="package",
        )

        # copy the backgrounds
        with self.assertLogs("dakara_player.background", "DEBUG") as logger:
            output_path = loader.copy_default_background("idle", "idle.png")

        # assert the background
        self.assertEqual(output_path, Path("destination") / "idle.png")

        # assert logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.background:Loading default "
                "idle background file 'idle.png'",
            ],
        )

        # assert the call of the mocked method
        mocked_files.assert_called_with("package")
        mocked_files.return_value.joinpath.assert_called_with("idle.png")
        mocked_copy.assert_called_with(
            Path("package") / "idle.png", Path("destination")
        )

    # def test_load_default(self, mocked_exists, mocked_copy, mocked_path):
    #     """Test to load a default background."""
    #     mocked_exists.return_value = False
    #     mocked_copy.return_value = Path("/") / "destination" / "idle.png"
    #     mocked_path.return_value.__enter__.return_value = (
    #         Path("/") / "package" / "idle.png"
    #     )
    #
    #     # create the instance
    #     loader = BackgroundLoader(
    #         destination=self.destination,
    #         package="package",
    #         filenames={"idle": "idle.png"},
    #     )
    #
    #     # pre assert that there are no backgrounds
    #     self.assertDictEqual(loader.backgrounds, {})
    #
    #     # load the backgrounds
    #     with self.assertLogs("dakara_player.background", "DEBUG") as logger:
    #         loader.load()
    #
    #     # assert the backgrounds
    #     self.assertDictEqual(
    #         loader.backgrounds,
    #         {"idle": self.destination / "idle.png"},
    #     )
    #
    #     # assert logs
    #     self.assertListEqual(
    #         logger.output,
    #         [
    #             "DEBUG:dakara_player.background:Loading backgrounds",
    #             "DEBUG:dakara_player.background:Loading default "
    #             "idle background file 'idle.png'",
    #         ],
    #     )
    #
    #     # assert the call of the mocked method
    #     mocked_exists.assert_not_called()
    #     mocked_copy.assert_called_with(
    #         Path("/") / "package" / "idle.png", Path("/") / "destination"
    #     )
    #     mocked_path.assert_called_with("package", "idle.png")
