from queue import Queue
from contextlib import ExitStack
from tempfile import gettempdir
from threading import Event
from unittest import TestCase
from unittest.mock import MagicMock, patch, call

from path import Path

from dakara_player.media_player.mpv import MediaPlayerMpv
from dakara_player.media_player.base import (
    MediaPlayerNotAvailableError,
    InvalidStateError,
    VersionNotFoundError,
)


class MediaPlayerMpvTestCase(TestCase):
    """Test the mpv player class unitary
    """

    def setUp(self):
        # create playlist entry ID
        self.id = 42

        # create playlist entry file path
        self.song_file_path = Path("file")
        self.subtitle_file_path = Path("file_sub")

        # create plàylist entry
        self.playlist_entry = {
            "id": self.id,
            "song": {"title": "Song title", "file_path": self.song_file_path},
            "owner": "me",
        }

    def get_instance(
        self,
        config=None,
        mock_instance=True,
        mock_background_loader=True,
        mock_text_generator=True,
    ):
        """Get a heavily mocked instance of MediaPlayerMpv

        Args:
            config (dict): Configuration passed to the constructor.
            mock_instance (bool): If True, the MPV class is mocked, otherwise
                it is a real object.
            mock_background_loader(bool): If True, the BackgroundLoader class
                is mocked, otherwise it is a real object.
            mock_text_generator(bool): If True, the TextGenerator class is
                mocked, otherwise it is a real object.

        Returns:
            tuple: Contains the following elements:
                MediaPlayerMpv: Instance;
                tuple: Contains the mocked objects:
                    unittest.mock.MagicMock: MPV object or None if
                        `mock_instance` is False;
                    unittest.mock.MagicMock: BackgroundLoader object or None if
                        `mock_background_loader` is False;
                    unittest.mock.MagicMock: TextGenerator object or None if
                        `mock_text_generator` is False;
                tuple: Contains the mocked classes:
                    unittest.mock.MagicMock: MPV class or None if
                        `mock_instance` is False;
                    unittest.mock.MagicMock: BackgroundLoader class or None if
                        `mock_background_loader` is False;
                    unittest.mock.MagicMock: TextGenerator class or None if
                        `mock_text_generator` is False.
        """
        config = config or {"kara_folder": gettempdir()}

        with ExitStack() as stack:
            mocked_instance_class = (
                stack.enter_context(patch("dakara_player.media_player.mpv.mpv.MPV"))
                if mock_instance
                else None
            )

            mocked_background_loader_class = (
                stack.enter_context(
                    patch("dakara_player.media_player.base.BackgroundLoader")
                )
                if mock_background_loader
                else None
            )

            mocked_text_generator_class = (
                stack.enter_context(
                    patch("dakara_player.media_player.base.TextGenerator")
                )
                if mock_text_generator
                else None
            )

            return (
                MediaPlayerMpv(Event(), Queue(), config, Path("temp")),
                (
                    mocked_instance_class.return_value
                    if mocked_instance_class
                    else None,
                    mocked_background_loader_class.return_value
                    if mocked_background_loader_class
                    else None,
                    mocked_text_generator_class.return_value
                    if mocked_text_generator_class
                    else None,
                ),
                (
                    mocked_instance_class,
                    mocked_background_loader_class,
                    mocked_text_generator_class,
                ),
            )

    def set_playlist_entry(self, mpv_player, started=True):
        """Set a playlist entry and make the player play it

        Args:
            mpv_player (MediaPlayerMpv): Instance of the mpv player.
            started (bool): If True, make the player play the song.
        """
        mpv_player.playlist_entry = self.playlist_entry

        # create mocked transition
        mpv_player.playlist_entry_data["transition"].path = (
            Path(gettempdir()) / "transition.png"
        )

        # create mocked song
        mpv_player.playlist_entry_data["song"].path = (
            mpv_player.kara_folder_path / self.song_file_path
        )
        mpv_player.playlist_entry_data["song"].path_subtitle = (
            mpv_player.kara_folder_path / self.subtitle_file_path
        )

        # set media has started
        if started:
            mpv_player.player.path = mpv_player.playlist_entry_data["song"].path
            mpv_player.player.sub_files = [
                mpv_player.playlist_entry_data["song"].path_subtitle
            ]
            mpv_player.player.playlist = [
                {
                    "id": 1,
                    "filename": mpv_player.player.path,
                    "current": True,
                    "playing": True,
                }
            ]
            mpv_player.player.pause = False

    @patch.object(MediaPlayerMpv, "is_available")
    def test_init_unavailable(self, mocked_is_available):
        """Test when mpv is not available
        """
        mocked_is_available.return_value = False

        with self.assertRaisesRegex(
            MediaPlayerNotAvailableError, "mpv is not available"
        ):
            MediaPlayerMpv(Event(), Queue(), {}, Path("temp"))

    def test_get_version_postrelease(self):
        """Test to get the mpv post release version
        """
        # create instance
        mpv_player, (mocked_mpv, _, _), _ = self.get_instance()

        # mock the version of mpv
        mocked_mpv.mpv_version = "mpv 0.32.0+git.20200402T120653.5824ac7d36"

        # call the method
        version = mpv_player.get_version()

        # assert the result
        self.assertEqual(version.base_version, "0.32.0")
        self.assertTrue(version.is_postrelease)

    def test_get_version(self):
        """Test to get the mpv stable version
        """
        # create instance
        mpv_player, (mocked_mpv, _, _), _ = self.get_instance()

        # mock the version of mpv
        mocked_mpv.mpv_version = "mpv 0.32.0"

        # call the method
        version = mpv_player.get_version()

        # assert the result
        self.assertEqual(version.base_version, "0.32.0")
        self.assertFalse(version.is_postrelease)

    def test_get_version_not_found(self):
        """Test to get the mpv version when it is not available
        """
        # create instance
        mpv_player, (mocked_mpv, _, _), _ = self.get_instance()

        # mock the version of mpv
        mocked_mpv.mpv_version = "none"

        # call the method
        with self.assertRaisesRegex(VersionNotFoundError, "Unable to get mpv version"):
            mpv_player.get_version()

    @patch.object(MediaPlayerMpv, "is_playing_this")
    def test_get_timing(self, mocked_is_playing_this):
        """Test to get timing
        """
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mocked_player.time_pos = 42.42
        mocked_is_playing_this.return_value = False

        self.assertEqual(mpv_player.get_timing(), 42)

        mocked_is_playing_this.assert_has_calls([call("idle"), call("transition")])

    @patch.object(MediaPlayerMpv, "is_playing_this")
    def test_get_timing_idle(self, mocked_is_playing_this):
        """Test to get timing when idle
        """
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mocked_player.time_pos = 42.42
        mocked_is_playing_this.side_effect = [True, False]

        self.assertEqual(mpv_player.get_timing(), 0)

    @patch.object(MediaPlayerMpv, "is_playing_this")
    def test_get_timing_transition(self, mocked_is_playing_this):
        """Test to get timing when in transition
        """
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mocked_player.time_pos = 42.42
        mocked_is_playing_this.side_effect = [False, True]

        self.assertEqual(mpv_player.get_timing(), 0)

    @patch.object(MediaPlayerMpv, "get_version")
    def test_load_player(self, mocked_get_version):
        """Test to load the instance
        """
        # create mock
        mocked_get_version.return_value = "0.32.0"

        # create instance
        mpv_player, _, _ = self.get_instance()

        # call the method
        with self.assertLogs("dakara_player.media_player.mpv", "DEBUG") as logger:
            mpv_player.load_player()

        # assert the calls
        mocked_get_version.assert_called_with()

        # assert the logs
        self.assertListEqual(
            logger.output, ["INFO:dakara_player.media_player.mpv:mpv 0.32.0"]
        )

    @patch.object(MediaPlayerMpv, "clear_playlist_entry")
    @patch.object(MediaPlayerMpv, "play")
    def test_handle_end_file_transition(self, mocked_play, mocked_clear_playlist_entry):
        """Test end file callback for after a transition
        """
        # create instance
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mpv_player.set_callback("finished", MagicMock())
        self.set_playlist_entry(mpv_player)
        mocked_player.playlist[0]["filename"] = Path(gettempdir()) / "transition.png"

        # call the method
        with self.assertLogs("dakara_player.media_player.mpv", "DEBUG") as logger:
            mpv_player.handle_end_file({"event": "end-file"})

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.media_player.mpv:File end callback called",
                "DEBUG:dakara_player.media_player.mpv:Will play '{}'".format(
                    Path(gettempdir()) / self.song_file_path
                ),
            ],
        )

        # assert the call
        mocked_play.assert_called_with("song")
        mocked_clear_playlist_entry.assert_not_called()
        mpv_player.callbacks["finished"].assert_not_called()

    @patch.object(MediaPlayerMpv, "clear_playlist_entry")
    @patch.object(MediaPlayerMpv, "play")
    def test_handle_end_file_song(self, mocked_play, mocked_clear_playlist_entry):
        """Test end file callback for after a song
        """
        # create instance
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mpv_player.set_callback("finished", MagicMock())
        self.set_playlist_entry(mpv_player)

        # call the method
        with self.assertLogs("dakara_player.media_player.mpv", "DEBUG") as logger:
            mpv_player.handle_end_file({"event": "end-file"})

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            ["DEBUG:dakara_player.media_player.mpv:File end callback called"],
        )

        # assert the call
        mocked_play.assert_not_called()
        mocked_clear_playlist_entry.assert_called_with()
        mpv_player.callbacks["finished"].assert_called_with(self.playlist_entry["id"])

    @patch.object(MediaPlayerMpv, "clear_playlist_entry")
    @patch.object(MediaPlayerMpv, "play")
    def test_handle_end_file_other(self, mocked_play, mocked_clear_playlist_entry):
        """Test end file callback for unknown state
        """
        # create instance
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mpv_player.set_callback("finished", MagicMock())
        self.set_playlist_entry(mpv_player)
        mocked_player.playlist[0]["filename"] = Path(gettempdir()) / "other"

        # call the method
        with self.assertLogs("dakara_player.media_player.mpv", "DEBUG"):
            with self.assertRaisesRegex(
                InvalidStateError, "End file on an undeterminated state"
            ):
                mpv_player.handle_end_file({"event": "end-file"})

        # assert the call
        mocked_play.assert_not_called()
        mocked_clear_playlist_entry.assert_not_called()
        mpv_player.callbacks["finished"].assert_not_called()

    @patch.object(MediaPlayerMpv, "skip")
    def test_handle_log_message(self, mocked_skip):
        """Test log message callback
        """
        # create instance
        mpv_player, _, _ = self.get_instance()
        self.set_playlist_entry(mpv_player)

        # mock the call
        mpv_player.set_callback("error", MagicMock())

        # call the method
        with self.assertLogs(
            "dakara_player.media_player.mpv", "DEBUG"
        ) as logger, self.assertLogs("mpv", "DEBUG") as logger_mpv:
            mpv_player.handle_log_messages("fatal", "mpv.component", "error message")

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.media_player.mpv:Log message callback called",
                "ERROR:dakara_player.media_player.mpv:Unable to play '{}'".format(
                    Path(gettempdir()) / self.song_file_path
                ),
            ],
        )
        self.assertListEqual(
            logger_mpv.output, ["CRITICAL:mpv:mpv.component: error message"]
        )

        # assert the call
        mpv_player.callbacks["error"].assert_called_with(
            self.playlist_entry["id"], "Unable to play current song: error message"
        )
        mocked_skip.assert_called_with()

    @patch.object(MediaPlayerMpv, "is_playing_this")
    def test_handle_start_file_transition(self, mocked_is_playing_this):
        """Test start file callback for a transition
        """
        # create instance
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mpv_player.set_callback("started_transition", MagicMock())
        mpv_player.set_callback("started_song", MagicMock())
        self.set_playlist_entry(mpv_player)

        # create mocks
        mocked_is_playing_this.return_value = True

        # call the method
        with self.assertLogs("dakara_player.media_player.mpv", "DEBUG") as logger:
            mpv_player.handle_start_file({})

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.media_player.mpv:Start file callback called",
                "INFO:dakara_player.media_player.mpv:Playing transition for "
                "'Song title'",
            ],
        )

        # assert the call
        mpv_player.callbacks["started_transition"].assert_called_with(
            self.playlist_entry["id"]
        )
        mpv_player.callbacks["started_song"].assert_not_called()
        mocked_is_playing_this.assert_called_with("transition")

    @patch.object(MediaPlayerMpv, "is_playing_this")
    def test_handle_start_file_song(self, mocked_is_playing_this):
        """Test start file callback for a song
        """
        # create instance
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mpv_player.set_callback("started_transition", MagicMock())
        mpv_player.set_callback("started_song", MagicMock())
        self.set_playlist_entry(mpv_player)

        # create mocks
        mocked_is_playing_this.side_effect = [False, True]

        # call the method
        with self.assertLogs("dakara_player.media_player.mpv", "DEBUG") as logger:
            mpv_player.handle_start_file({})

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.media_player.mpv:Start file callback called",
                "INFO:dakara_player.media_player.mpv:Now playing 'Song title' "
                "('{}')".format(Path(gettempdir()) / self.song_file_path),
            ],
        )

        # assert the call
        mpv_player.callbacks["started_transition"].assert_not_called()
        mpv_player.callbacks["started_song"].assert_called_with(
            self.playlist_entry["id"]
        )

        # assert the call
        mpv_player.callbacks["started_transition"].assert_not_called()
        mpv_player.callbacks["started_song"].assert_called_with(
            self.playlist_entry["id"]
        )
        mocked_is_playing_this.assert_has_calls([call("transition"), call("song")])

    @patch.object(MediaPlayerMpv, "is_playing_this")
    def test_handle_start_file_idle(self, mocked_is_playing_this):
        """Test start file callback for a idle
        """
        # create instance
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mpv_player.set_callback("started_transition", MagicMock())
        mpv_player.set_callback("started_song", MagicMock())
        self.set_playlist_entry(mpv_player)

        # create mocks
        mocked_is_playing_this.side_effect = [False, False, True]

        # call the method
        with self.assertLogs("dakara_player.media_player.mpv", "DEBUG") as logger:
            mpv_player.handle_start_file({})

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.media_player.mpv:Start file callback called",
                "DEBUG:dakara_player.media_player.mpv:Playing idle screen",
            ],
        )

        # assert the call
        mpv_player.callbacks["started_transition"].assert_not_called()
        mpv_player.callbacks["started_song"].assert_not_called()
        mocked_is_playing_this.assert_has_calls(
            [call("transition"), call("song"), call("idle")]
        )

    @patch.object(MediaPlayerMpv, "is_playing_this")
    def test_handle_start_file_unknown(self, mocked_is_playing_this):
        """Test start file callback for an unknown state
        """
        # create instance
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mpv_player.set_callback("started_transition", MagicMock())
        mpv_player.set_callback("started_song", MagicMock())
        self.set_playlist_entry(mpv_player)

        # create mocks
        mocked_is_playing_this.return_value = False

        # call the method
        with self.assertRaisesRegex(
            InvalidStateError, "Start file on an undeterminated state"
        ):
            mpv_player.handle_start_file({})

        # assert the call
        mpv_player.callbacks["started_transition"].assert_not_called()
        mpv_player.callbacks["started_song"].assert_not_called()

    @patch.object(MediaPlayerMpv, "get_timing")
    def test_handle_pause(self, mocked_get_timing):
        """Test pause callback
        """
        # create instance
        mpv_player, _, _ = self.get_instance()
        mpv_player.set_callback("paused", MagicMock())
        self.set_playlist_entry(mpv_player)

        # create the mocks
        mocked_get_timing.return_value = 42

        # call the method
        with self.assertLogs("dakara_player.media_player.mpv", "DEBUG") as logger:
            mpv_player.handle_pause({})

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.media_player.mpv:Pause callback called",
                "DEBUG:dakara_player.media_player.mpv:Paused",
            ],
        )

        # assert the call
        mpv_player.callbacks["paused"].assert_called_with(self.playlist_entry["id"], 42)
        mocked_get_timing.assert_called_with()

    @patch.object(MediaPlayerMpv, "get_timing")
    def test_handle_unpause(self, mocked_get_timing):
        """Test unpause callback
        """
        # create instance
        mpv_player, _, _ = self.get_instance()
        mpv_player.set_callback("resumed", MagicMock())
        self.set_playlist_entry(mpv_player)

        # create the mocks
        mocked_get_timing.return_value = 42

        # call the method
        with self.assertLogs("dakara_player.media_player.mpv", "DEBUG") as logger:
            mpv_player.handle_unpause({})

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.media_player.mpv:Unpause callback called",
                "DEBUG:dakara_player.media_player.mpv:Resumed play",
            ],
        )

        # assert the call
        mpv_player.callbacks["resumed"].assert_called_with(
            self.playlist_entry["id"], 42
        )
        mocked_get_timing.assert_called_with()

    def test_init(self):
        """Test to initialize mpv player with custom config
        """
        mpv_player, (mocked_player, _, _), _ = self.get_instance(
            {"mpv": {"key1": "value1"}}
        )
        self.assertEqual(getattr(mocked_player, "key1"), "value1")

    def test_play_invalid(self):
        """Test to play invalid action
        """
        mpv_player, _, _ = self.get_instance()

        with self.assertRaisesRegex(ValueError, "Unexpected action to play: none"):
            mpv_player.play("none")

        mpv_player.player.play.assert_not_called()

    def test_play_no_song_path_subtitle(self):
        """Test to play a file no detected subtitle
        """
        mpv_player, _, _ = self.get_instance()
        mpv_player.playlist_entry_data["song"].path = "test_file"
        mpv_player.playlist_entry_data["song"].path_subtitle = None

        mpv_player.play("song")

        mpv_player.player.play.assert_called_with("test_file")
        self.assertNotEqual(mpv_player.player.sub_files, [None])
