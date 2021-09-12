from contextlib import ExitStack
from queue import Queue
from tempfile import gettempdir
from threading import Event
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

from packaging.version import Version
from path import Path

from dakara_player.media_player.base import (
    InvalidStateError,
    MediaPlayerNotAvailableError,
    VersionNotFoundError,
)
from dakara_player.media_player.mpv import (
    MediaPlayerMpv,
    MediaPlayerMpvOld,
    MediaPlayerMpvPost0330,
)


class MediaPlayerMpvTestCase(TestCase):
    """Test the static methods of the abstract MediaPlayerMpv class."""

    @patch("dakara_player.media_player.mpv.mpv.MPV")
    def test_get_version_postrelease(self, mocked_mpv_class):
        """Test to get the mpv post release version."""
        # mock the version of mpv
        mocked_mpv_class.return_value.mpv_version = (
            "mpv 0.32.0+git.20200402T120653.5824ac7d36"
        )

        # call the method
        version = MediaPlayerMpvOld.get_version()

        # assert the result
        self.assertEqual(version.base_version, "0.32.0")
        self.assertTrue(version.is_postrelease)

    @patch("dakara_player.media_player.mpv.mpv.MPV")
    def test_get_version(self, mocked_mpv_class):
        """Test to get the mpv stable version."""
        # mock the version of mpv
        mocked_mpv_class.return_value.mpv_version = "mpv 0.32.0"

        # call the method
        version = MediaPlayerMpvOld.get_version()

        # assert the result
        self.assertEqual(version.base_version, "0.32.0")
        self.assertFalse(version.is_postrelease)

    @patch("dakara_player.media_player.mpv.mpv.MPV")
    def test_get_version_not_found(self, mocked_mpv_class):
        """Test to get the mpv version when it is not available."""
        # mock the version of mpv
        mocked_mpv_class.return_value.mpv_version = "none"

        # call the method
        with self.assertRaisesRegex(VersionNotFoundError, "Unable to get mpv version"):
            MediaPlayerMpvOld.get_version()

    @patch.object(MediaPlayerMpv, "get_version")
    def test_get_old(self, mocked_get_version):
        """Test to get media player for old version of mpv."""
        mocked_get_version.return_value = Version("0.27.0")

        self.assertIs(MediaPlayerMpv.get_class_from_version(), MediaPlayerMpvOld)

    @patch.object(MediaPlayerMpv, "get_version")
    def test_get_post_0330(self, mocked_get_version):
        """Test to get media player for version of mpv newer than 0.33.0."""
        mocked_get_version.return_value = Version("0.33.0")

        self.assertIs(MediaPlayerMpv.get_class_from_version(), MediaPlayerMpvPost0330)

    @patch.object(MediaPlayerMpv, "get_class_from_version")
    def test_instanciate(self, mocked_get_class_from_version):
        """Test to instanciate media player mpv class."""

        class Dummy:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        mocked_get_class_from_version.return_value = Dummy

        instance = MediaPlayerMpv.from_version(1, 2, v3=3, v4=4)
        self.assertIsInstance(instance, Dummy)
        self.assertEqual(instance.args, (1, 2))
        self.assertEqual(instance.kwargs, {"v3": 3, "v4": 4})

    @patch("dakara_player.media_player.mpv.mpv.MPV")
    def test_is_available_ok_direct(self, mocked_mpv_class):
        """Test to get availability directly."""
        self.assertTrue(MediaPlayerMpv.is_available())

    @patch("dakara_player.media_player.mpv.mpv.MPV")
    def test_is_available_ok_indirect(self, mocked_mpv_class):
        """Test to get availability indirectly."""
        mocked_mpv_class.side_effect = [FileNotFoundError(), MagicMock()]
        self.assertTrue(MediaPlayerMpv.is_available())

    @patch("dakara_player.media_player.mpv.mpv", None)
    def test_is_available_ng_no_module(self):
        """Test to get inavailability if mpv module cannot be loaded."""
        self.assertFalse(MediaPlayerMpv.is_available())

    @patch("dakara_player.media_player.mpv.mpv.MPV")
    def test_is_available_ng(self, mocked_mpv_class):
        """Test to get inavailability."""
        mocked_mpv_class.side_effect = FileNotFoundError()
        self.assertFalse(MediaPlayerMpv.is_available())


class MediaPlayerMpvModelTestCase(TestCase):
    """Test the mpv player class unitary."""

    mpv_player_class = None

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
        self, config=None,
    ):
        """Get a heavily mocked instance of the desired subclass of MediaPlayerMpv.

        Args:
            config (dict): Configuration passed to the constructor.

        Returns:
            tuple: Contains the following elements:
                MediaPlayerMpv: Instance;
                tuple: Contains the mocked objects:
                    unittest.mock.MagicMock: MPV object.
                    unittest.mock.MagicMock: BackgroundLoader object.
                    unittest.mock.MagicMock: TextGenerator object.
                tuple: Contains the mocked classes:
                    unittest.mock.MagicMock: MPV class.
                    unittest.mock.MagicMock: BackgroundLoader class.
                    unittest.mock.MagicMock: TextGenerator class.
        """
        config = config or {"kara_folder": gettempdir()}

        with ExitStack() as stack:
            mocked_instance_class = stack.enter_context(
                patch("dakara_player.media_player.mpv.mpv.MPV")
            )

            mocked_background_loader_class = stack.enter_context(
                patch("dakara_player.media_player.base.BackgroundLoader")
            )

            mocked_text_generator_class = stack.enter_context(
                patch("dakara_player.media_player.base.TextGenerator")
            )

            return (
                self.mpv_player_class(Event(), Queue(), config, Path("temp")),
                (
                    mocked_instance_class.return_value,
                    mocked_background_loader_class.return_value,
                    mocked_text_generator_class.return_value,
                ),
                (
                    mocked_instance_class,
                    mocked_background_loader_class,
                    mocked_text_generator_class,
                ),
            )

    def set_playlist_entry(self, mpv_player, started=True):
        """Set a playlist entry and make the player play it.

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


class MediaPlayerMpvOldTestCase(MediaPlayerMpvModelTestCase):
    """Test the old mpv player class unitary."""

    mpv_player_class = MediaPlayerMpvOld

    @patch.object(MediaPlayerMpvOld, "is_available")
    def test_init_unavailable(self, mocked_is_available):
        """Test when mpv is not available."""
        mocked_is_available.return_value = False

        with self.assertRaisesRegex(
            MediaPlayerNotAvailableError, "mpv is not available"
        ):
            MediaPlayerMpvOld(Event(), Queue(), {}, Path("temp"))

    @patch.object(MediaPlayerMpvOld, "is_playing_this")
    def test_get_timing(self, mocked_is_playing_this):
        """Test to get timing."""
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mocked_player.time_pos = 42.42
        mocked_is_playing_this.return_value = False

        self.assertEqual(mpv_player.get_timing(), 42)

        mocked_is_playing_this.assert_has_calls([call("idle"), call("transition")])

    @patch.object(MediaPlayerMpvOld, "is_playing_this")
    def test_get_timing_idle(self, mocked_is_playing_this):
        """Test to get timing when idle."""
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mocked_player.time_pos = 42.42
        mocked_is_playing_this.side_effect = [True, False]

        self.assertEqual(mpv_player.get_timing(), 0)

    @patch.object(MediaPlayerMpvOld, "is_playing_this")
    def test_get_timing_transition(self, mocked_is_playing_this):
        """Test to get timing when in transition."""
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mocked_player.time_pos = 42.42
        mocked_is_playing_this.side_effect = [False, True]

        self.assertEqual(mpv_player.get_timing(), 0)

    @patch.object(MediaPlayerMpvOld, "get_version")
    def test_load_player(self, mocked_get_version):
        """Test to load the instance."""
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

    @patch.object(MediaPlayerMpvOld, "clear_playlist_entry")
    @patch.object(MediaPlayerMpvOld, "play")
    def test_handle_end_file_transition(self, mocked_play, mocked_clear_playlist_entry):
        """Test end file callback for after a transition."""
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

    @patch.object(MediaPlayerMpvOld, "clear_playlist_entry")
    @patch.object(MediaPlayerMpvOld, "play")
    def test_handle_end_file_song(self, mocked_play, mocked_clear_playlist_entry):
        """Test end file callback for after a song."""
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

    @patch.object(MediaPlayerMpvOld, "clear_playlist_entry")
    @patch.object(MediaPlayerMpvOld, "play")
    def test_handle_end_file_other(self, mocked_play, mocked_clear_playlist_entry):
        """Test end file callback for unknown state."""
        # create instance
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mpv_player.set_callback("finished", MagicMock())
        self.set_playlist_entry(mpv_player)
        mocked_player.playlist[0]["filename"] = Path(gettempdir()) / "other"

        self.assertFalse(mpv_player.stop.is_set())

        # call the method
        with self.assertLogs("dakara_player.media_player.mpv", "DEBUG"):
            mpv_player.handle_end_file({"event": "end-file"})

        self.assertTrue(mpv_player.stop.is_set())
        exception_class, exception, _ = mpv_player.errors.get()
        self.assertIs(exception_class, InvalidStateError)
        self.assertIn("End file on an undeterminated state", str(exception))

        # assert the call
        mocked_play.assert_not_called()
        mocked_clear_playlist_entry.assert_not_called()
        mpv_player.callbacks["finished"].assert_not_called()

    @patch.object(MediaPlayerMpvOld, "skip")
    def test_handle_log_message(self, mocked_skip):
        """Test log message callback."""
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

    @patch.object(MediaPlayerMpvOld, "is_playing_this")
    def test_handle_start_file_transition(self, mocked_is_playing_this):
        """Test start file callback for a transition."""
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

    @patch.object(MediaPlayerMpvOld, "is_playing_this")
    def test_handle_start_file_song(self, mocked_is_playing_this):
        """Test start file callback for a song."""
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

    @patch.object(MediaPlayerMpvOld, "is_playing_this")
    def test_handle_start_file_idle(self, mocked_is_playing_this):
        """Test start file callback for a idle."""
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

    @patch.object(MediaPlayerMpvOld, "is_playing_this")
    def test_handle_start_file_unknown(self, mocked_is_playing_this):
        """Test start file callback for an unknown state."""
        # create instance
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mpv_player.set_callback("started_transition", MagicMock())
        mpv_player.set_callback("started_song", MagicMock())
        self.set_playlist_entry(mpv_player)

        # create mocks
        mocked_is_playing_this.return_value = False

        self.assertFalse(mpv_player.stop.is_set())

        # call the method
        mpv_player.handle_start_file({})

        self.assertTrue(mpv_player.stop.is_set())
        exception_class, exception, _ = mpv_player.errors.get()
        self.assertIs(exception_class, InvalidStateError)
        self.assertIn("Start file on an undeterminated state", str(exception))

        # assert the call
        mpv_player.callbacks["started_transition"].assert_not_called()
        mpv_player.callbacks["started_song"].assert_not_called()

    @patch.object(MediaPlayerMpvOld, "get_timing")
    def test_handle_pause(self, mocked_get_timing):
        """Test pause callback."""
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

    @patch.object(MediaPlayerMpvOld, "get_timing")
    def test_handle_unpause(self, mocked_get_timing):
        """Test unpause callback."""
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
        """Test to initialize mpv player with custom config."""
        mpv_player, (mocked_player, _, _), _ = self.get_instance(
            {"mpv": {"key1": "value1"}}
        )
        self.assertEqual(getattr(mocked_player, "key1"), "value1")

    def test_play_invalid(self):
        """Test to play invalid action."""
        mpv_player, _, _ = self.get_instance()

        with self.assertRaisesRegex(ValueError, "Unexpected action to play: none"):
            mpv_player.play("none")

        mpv_player.player.play.assert_not_called()

    def test_play_no_song_path_subtitle(self):
        """Test to play a file no detected subtitle."""
        mpv_player, _, _ = self.get_instance()
        mpv_player.playlist_entry_data["song"].path = "test_file"
        mpv_player.playlist_entry_data["song"].path_subtitle = None

        mpv_player.play("song")

        mpv_player.player.play.assert_called_with("test_file")
        self.assertNotEqual(mpv_player.player.sub_files, [None])


class MediaPlayerMpvPost0330TestCase(MediaPlayerMpvModelTestCase):
    """Test the post 0.33.0 mpv player class unitary."""

    mpv_player_class = MediaPlayerMpvPost0330

    @patch.object(MediaPlayerMpvPost0330, "clear_playlist_entry")
    @patch.object(MediaPlayerMpvPost0330, "play")
    def test_handle_end_file_transition(self, mocked_play, mocked_clear_playlist_entry):
        """Test end file callback for after a transition."""
        # create instance
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mpv_player.set_callback("finished", MagicMock())
        self.set_playlist_entry(mpv_player)
        mocked_player.playlist[0]["filename"] = Path(gettempdir()) / "transition.png"

        # call the method
        with self.assertLogs("dakara_player.media_player.mpv", "DEBUG") as logger:
            mpv_player.handle_end_file(
                {"event": "end-file", "reason": "eof", "playlist_entry_id": 1}
            )

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

    @patch.object(MediaPlayerMpvPost0330, "clear_playlist_entry")
    @patch.object(MediaPlayerMpvPost0330, "play")
    def test_handle_end_file_song(self, mocked_play, mocked_clear_playlist_entry):
        """Test end file callback for after a song."""
        # create instance
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mpv_player.set_callback("finished", MagicMock())
        self.set_playlist_entry(mpv_player)

        # call the method
        with self.assertLogs("dakara_player.media_player.mpv", "DEBUG") as logger:
            mpv_player.handle_end_file(
                {"event": "end-file", "reason": "eof", "playlist_entry_id": 1}
            )

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            ["DEBUG:dakara_player.media_player.mpv:File end callback called"],
        )

        # assert the call
        mocked_play.assert_not_called()
        mocked_clear_playlist_entry.assert_called_with()
        mpv_player.callbacks["finished"].assert_called_with(self.playlist_entry["id"])

    @patch.object(MediaPlayerMpvPost0330, "clear_playlist_entry")
    @patch.object(MediaPlayerMpvPost0330, "play")
    def test_handle_end_file_other(self, mocked_play, mocked_clear_playlist_entry):
        """Test end file callback for unknown state."""
        # create instance
        mpv_player, (mocked_player, _, _), _ = self.get_instance()
        mpv_player.set_callback("finished", MagicMock())
        self.set_playlist_entry(mpv_player)
        mocked_player.playlist[0]["filename"] = Path(gettempdir()) / "other"

        self.assertFalse(mpv_player.stop.is_set())

        # call the method
        with self.assertLogs("dakara_player.media_player.mpv", "DEBUG"):
            mpv_player.handle_end_file(
                {"event": "end-file", "reason": "eof", "playlist_entry_id": 1}
            )

        self.assertTrue(mpv_player.stop.is_set())
        exception_class, exception, _ = mpv_player.errors.get()
        self.assertIs(exception_class, InvalidStateError)
        self.assertIn("End file on an undeterminated state", str(exception))

        # assert the call
        mocked_play.assert_not_called()
        mocked_clear_playlist_entry.assert_not_called()
        mpv_player.callbacks["finished"].assert_not_called()
