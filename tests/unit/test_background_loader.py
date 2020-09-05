from unittest import TestCase
from unittest.mock import call, patch

from path import Path

from dakara_player_vlc.background_loader import (
    BackgroundLoader,
    BackgroundNotFoundError,
)


class BackgroundLoaderTestCase(TestCase):
    """Test the loader for backgrounds
    """

    @patch(
        "dakara_player_vlc.background_loader.exists", return_value=True, autospec=True
    )
    def test_load_default_name_default_directory(self, mocked_exists):
        """Test to load one default background from defauld directory
        """
        # create the instance
        loader = BackgroundLoader(
            default_directory=Path("default"),
            default_background_filenames={"background": "background.png"},
        )

        # pre assert that there are no backgrounds
        self.assertDictEqual(loader.backgrounds, {})

        # load the backgrounds
        loader.load()

        # assert the backgrounds
        self.assertDictEqual(
            loader.backgrounds,
            {"background": Path("default/background.png").normpath()},
        )

        # assert the call of the mocked method
        mocked_exists.assert_called_with(Path("default/background.png").normpath())

    @patch(
        "dakara_player_vlc.background_loader.exists", return_value=True, autospec=True
    )
    def test_load_default_name_custom_directory(self, mocked_exists):
        """Test to load one default background from custom directory
        """
        # create the instance
        loader = BackgroundLoader(
            directory=Path("custom"),
            default_directory=Path("default"),
            default_background_filenames={"background": "background.png"},
        )

        # pre assert that there are no backgrounds
        self.assertDictEqual(loader.backgrounds, {})

        # load the backgrounds
        loader.load()

        # assert the backgrounds
        self.assertDictEqual(
            loader.backgrounds, {"background": Path("custom/background.png").normpath()}
        )

        # assert the call of the mocked method
        mocked_exists.assert_called_with(Path("custom/background.png").normpath())

    @patch(
        "dakara_player_vlc.background_loader.exists", return_value=True, autospec=True
    )
    def test_load_custom_name_custom_directory(self, mocked_exists):
        """Test to load one custom background from custom directory
        """
        # create the instance
        loader = BackgroundLoader(
            directory=Path("custom"),
            background_filenames={"background": "custom.png"},
            default_directory=Path("default"),
            default_background_filenames={"background": "background.png"},
        )

        # pre assert that there are no backgrounds
        self.assertDictEqual(loader.backgrounds, {})

        # load the backgrounds
        loader.load()

        # assert the backgrounds
        self.assertDictEqual(
            loader.backgrounds, {"background": Path("custom/custom.png").normpath()}
        )

        # assert the call of the mocked method
        mocked_exists.assert_called_with(Path("custom/custom.png").normpath())

    @patch(
        "dakara_player_vlc.background_loader.exists", return_value=True, autospec=True
    )
    def test_load_custom_name_default_directory(self, mocked_exists):
        """Test to load one custom background from default directory

        Should load default background from default directory.
        """
        # create the instance
        loader = BackgroundLoader(
            default_directory=Path("default"),
            default_background_filenames={"background": "background.png"},
            background_filenames={"background": "other.png"},
        )

        # pre assert that there are no backgrounds
        self.assertDictEqual(loader.backgrounds, {})

        # load the backgrounds
        loader.load()

        # assert the backgrounds
        self.assertDictEqual(
            loader.backgrounds,
            {"background": Path("default/background.png").normpath()},
        )

        # assert the call of the mocked method
        mocked_exists.assert_called_with(Path("default/background.png").normpath())

    @patch("dakara_player_vlc.background_loader.exists", autospec=True)
    def test_load_fallback_default_name_custom_directory(self, mocked_exists):
        """Test to fallback to load one default background from custom directory

        Was initially trying to load one custom background from custom directory.
        """
        # create the instance
        loader = BackgroundLoader(
            directory=Path("custom"),
            background_filenames={"background": "custom.png"},
            default_directory=Path("default"),
            default_background_filenames={"background": "background.png"},
        )

        # setup mock
        mocked_exists.side_effect = [False, True]

        # pre assert that there are no backgrounds
        self.assertDictEqual(loader.backgrounds, {})

        # load the backgrounds
        loader.load()

        # assert the backgrounds
        self.assertDictEqual(
            loader.backgrounds, {"background": Path("custom/background.png").normpath()}
        )

        # assert the call of the mocked method
        mocked_exists.assert_has_calls(
            [
                call(Path("custom/custom.png").normpath()),
                call(Path("custom/background.png").normpath()),
            ]
        )

    @patch("dakara_player_vlc.background_loader.exists", autospec=True)
    def test_load_fallback_default_name_default_directory(self, mocked_exists):
        """Test to fallback to load one default background from default directory

        Was initially trying to load one custom background from custom directory.
        """
        # create the instance
        loader = BackgroundLoader(
            directory=Path("custom"),
            background_filenames={"background": "custom.png"},
            default_directory=Path("default"),
            default_background_filenames={"background": "background.png"},
        )

        # setup mock
        mocked_exists.side_effect = [False, False, True]

        # pre assert that there are no backgrounds
        self.assertDictEqual(loader.backgrounds, {})

        # load the backgrounds
        loader.load()

        # assert the backgrounds
        self.assertDictEqual(
            loader.backgrounds,
            {"background": Path("default/background.png").normpath()},
        )

        # assert the call of the mocked method
        mocked_exists.assert_has_calls(
            [
                call(Path("custom/custom.png").normpath()),
                call(Path("custom/background.png").normpath()),
                call(Path("default/background.png").normpath()),
            ]
        )

    @patch("dakara_player_vlc.background_loader.exists", autospec=True)
    def test_load_error(self, mocked_exists):
        """Test to load one unexisting background

        Was initially trying to load one custom background from custom directory.
        """
        # create the instance
        loader = BackgroundLoader(
            directory=Path("custom"),
            background_filenames={"background": "custom.png"},
            default_directory=Path("default"),
            default_background_filenames={"background": "background.png"},
        )

        # setup mock
        mocked_exists.side_effect = [False, False, False]

        # pre assert that there are no backgrounds
        self.assertDictEqual(loader.backgrounds, {})

        # load the backgrounds
        with self.assertRaisesRegex(
            BackgroundNotFoundError, "Unable to find a background file for background"
        ):
            loader.load()

        # assert the backgrounds
        self.assertDictEqual(loader.backgrounds, {})

        # assert the call of the mocked method
        mocked_exists.assert_has_calls(
            [
                call(Path("custom/custom.png").normpath()),
                call(Path("custom/background.png").normpath()),
                call(Path("default/background.png").normpath()),
            ]
        )

    @patch(
        "dakara_player_vlc.background_loader.exists", return_value=True, autospec=True
    )
    def test_load_none_filename(self, mocked_exists):
        """Test to load a None custom filename
        """
        loader = BackgroundLoader(
            directory=Path("custom"),
            background_filenames={"background": None},
            default_directory=Path("default"),
            default_background_filenames={"background": "background.png"},
        )

        # pre assert that there are no backgrounds
        self.assertDictEqual(loader.backgrounds, {})

        # load the backgrounds
        loader.load()

        # assert the backgrounds
        self.assertDictEqual(
            loader.backgrounds, {"background": Path("custom/background.png").normpath()}
        )

        # assert the call of the mocked method
        mocked_exists.assert_called_with(Path("custom/background.png").normpath())
