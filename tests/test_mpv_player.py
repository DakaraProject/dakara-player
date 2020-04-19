from queue import Queue
from threading import Event
from unittest import TestCase
from unittest.mock import MagicMock, patch

import mpv
from path import Path

from dakara_player_vlc.mpv_player import (
    MpvMediaPlayer,
    MpvNotAvailableError,
)
from dakara_player_vlc.media_player import MediaPlayerNotAvailableError


class MpvMediaPlayerTestCase(TestCase):
    """Test the MPV player class unitary
    """

    def setUp(self):
        # create playlist entry ID
        self.id = 42

        # create playlist entry file path
        self.song_file_path = Path("path/to/file")

        # create plàylist entry
        self.playlist_entry = {
            "id": self.id,
            "song": {"file_path": self.song_file_path},
            "owner": "me",
        }

    def get_instance(self, config={}):
        """Get a heavily mocked instance of MpvMediaPlayer

        Args:
            config (dict): configuration passed to the constructor.

        Returns:
            tuple: contains the following elements:
                MpvMediaPlayer: instance;
                tuple: contains the mocked objects, for checking:
                    unittest.mock.MagicMock: MPV class;
                    unittest.mock.MagicMock: BackgroundLoader class;
                    unittest.mock.MagicMock: TextGenerator class.
        """
        with patch(
            "dakara_player_vlc.media_player.TextGenerator"
        ) as mocked_text_generator_class, patch(
            "dakara_player_vlc.media_player.BackgroundLoader"
        ) as mocked_background_loader_class, patch(
            "dakara_player_vlc.mpv_player.mpv.MPV"
        ) as mocked_mpv_class:
            return (
                MpvMediaPlayer(Event(), Queue(), config, Path("temp")),
                (
                    mocked_mpv_class,
                    mocked_background_loader_class,
                    mocked_text_generator_class,
                ),
            )

    def test_is_available(self):
        """Test if MPV is available
        """
        self.assertTrue(MpvMediaPlayer.is_available())

    @patch.object(MpvMediaPlayer, "is_available")
    def test_init_unavailable(self, mocked_is_available):
        """Test when MPV is not available
        """
        mocked_is_available.return_value = False

        with self.assertRaisesRegex(
            MediaPlayerNotAvailableError, "MPV is not available"
        ) as error:
            MpvMediaPlayer(Event(), Queue(), {}, Path("temp"))

        self.assertIs(error.exception.__class__, MpvNotAvailableError)

    def test_get_version(self):
        """Test to get the MPV version
        """
        # create instance
        mpv_player, (mpv_class, _, _) = self.get_instance()

        # mock the version of MPV
        mpv_class.return_value.mpv_version = "mpv 0.32.0+git.20200402T120653.5824ac7d36"

        # call the method
        with self.assertLogs("dakara_player_vlc.mpv_player", "DEBUG") as logger:
            mpv_player.get_version()

        # assert the effect on logger
        self.assertListEqual(
            logger.output, ["INFO:dakara_player_vlc.mpv_player:mpv 0.32.0"]
        )

    @patch.object(MpvMediaPlayer, "get_version")
    def test_load_player(self, mocked_get_version):
        """Test to load the instance
        """
        # create instance
        mpv_player, _ = self.get_instance()

        # call the method
        mpv_player.load_player()

        # assert the calls
        mocked_get_version.assert_called_with()

    @patch.object(MpvMediaPlayer, "create_thread")
    @patch.object(Path, "exists")
    def test_handle_end_reached_transition(self, mocked_exists, mocked_create_thread):
        """Test song end callback for after a transition screen
        """
        # create instance
        mpv_player, _ = self.get_instance()

        # mock the call
        mpv_player.in_transition = True
        mpv_player.playing_id = 999
        mpv_player.set_callback("finished", MagicMock())
        mpv_player.set_callback("started_song", MagicMock())
        file_path = Path("path") / "to" / "media.mkv"
        sub_path = Path("path") / "to" / "media.ass"
        mpv_player.media_pending = file_path
        mocked_exists.return_value = True

        # call the method
        with self.assertLogs("dakara_player_vlc.mpv_player", "DEBUG") as logger:
            mpv_player.handle_end_reached(
                {"event": {"reason": mpv.MpvEventEndFile.EOF}}
            )

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.mpv_player:Song end callback called",
                "INFO:dakara_player_vlc.mpv_player:Now playing '{}'".format(
                    file_path.normpath()
                ),
            ],
        )

        # assert the call
        self.assertFalse(mpv_player.in_transition)
        mpv_player.callbacks["finished"].assert_not_called()
        mpv_player.callbacks["started_song"].assert_called_with(999)
        mocked_create_thread.assert_called_with(
            target=mpv_player.play_media, args=(file_path, sub_path)
        )

    @patch.object(MpvMediaPlayer, "create_thread")
    @patch.object(Path, "exists")
    def test_handle_end_reached_transition_no_subfile(
        self, mocked_exists, mocked_create_thread
    ):
        """Test song end callback for after a transition screen without subtitle
        """
        # create instance
        mpv_player, _ = self.get_instance()

        # mock the call
        mpv_player.in_transition = True
        mpv_player.playing_id = 999
        mpv_player.set_callback("finished", MagicMock())
        mpv_player.set_callback("started_song", MagicMock())
        file_path = Path("path") / "to" / "media.mkv"
        mpv_player.media_pending = file_path
        mocked_exists.return_value = False

        # call the method
        with self.assertLogs("dakara_player_vlc.mpv_player", "DEBUG") as logger:
            mpv_player.handle_end_reached(
                {"event": {"reason": mpv.MpvEventEndFile.EOF}}
            )

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.mpv_player:Song end callback called",
                "INFO:dakara_player_vlc.mpv_player:Now playing '{}'".format(
                    file_path.normpath()
                ),
            ],
        )

        # assert the call
        self.assertFalse(mpv_player.in_transition)
        mpv_player.callbacks["finished"].assert_not_called()
        mpv_player.callbacks["started_song"].assert_called_with(999)
        mocked_create_thread.assert_called_with(
            target=mpv_player.play_media, args=(file_path, None)
        )

    @patch.object(MpvMediaPlayer, "create_thread")
    def test_handle_end_reached_idle(self, mocked_create_thread):
        """Test song end callback for after an idle screen
        """
        # create instance
        mpv_player, _ = self.get_instance()

        # mock the call
        mpv_player.in_transition = False
        mpv_player.playing_id = None
        mpv_player.set_callback("finished", MagicMock())
        mpv_player.set_callback("started_song", MagicMock())

        # call the method
        with self.assertLogs("dakara_player_vlc.mpv_player", "DEBUG"):
            mpv_player.handle_end_reached(
                {"event": {"reason": mpv.MpvEventEndFile.EOF}}
            )

        # assert the call
        mpv_player.callbacks["finished"].assert_not_called()
        mpv_player.callbacks["started_song"].assert_not_called()
        mocked_create_thread.assert_called_with(target=mpv_player.play_idle_screen)

    @patch.object(MpvMediaPlayer, "create_thread")
    def test_handle_end_reached_finished(self, mocked_create_thread):
        """Test song end callback for after an actual song
        """
        # create instance
        mpv_player, _ = self.get_instance()

        # mock the call
        mpv_player.in_transition = False
        mpv_player.playing_id = 999
        mpv_player.set_callback("finished", MagicMock())
        mpv_player.set_callback("started_song", MagicMock())

        # call the method
        with self.assertLogs("dakara_player_vlc.mpv_player", "DEBUG"):
            mpv_player.handle_end_reached(
                {"event": {"reason": mpv.MpvEventEndFile.EOF}}
            )

        # assert the call
        mpv_player.callbacks["finished"].assert_called_with(999)
        mpv_player.callbacks["started_song"].assert_not_called()
        mocked_create_thread.assert_not_called()

    @patch.object(MpvMediaPlayer, "create_thread")
    def test_handle_end_reached_other(self, mocked_create_thread):
        """Test song end callback for another reason
        """
        # create instance
        mpv_player, _ = self.get_instance()

        # mock the call
        mpv_player.in_transition = False
        mpv_player.playing_id = 999
        mpv_player.set_callback("finished", MagicMock())
        mpv_player.set_callback("started_song", MagicMock())

        # call the method
        mpv_player.handle_end_reached({"event": {"reason": None}})

        # assert the call
        mpv_player.callbacks["finished"].assert_not_called()
        mpv_player.callbacks["started_song"].assert_not_called()
        mocked_create_thread.assert_not_called()

    def test_handle_log_message(self):
        """Test log message callback
        """
        # create instance
        mpv_player, _ = self.get_instance()

        # mock the call
        mpv_player.set_callback("error", MagicMock())
        mpv_player.set_callback("finished", MagicMock())
        mpv_player.playing_id = 999

        # call the method
        with self.assertLogs("dakara_player_vlc.mpv_player", "DEBUG") as logger:
            mpv_player.handle_log_messages("error", "mpv.component", "error message")

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.mpv_player:Log message callback called",
                "ERROR:dakara_player_vlc.mpv_player:mpv: mpv.component: error message",
                "ERROR:dakara_player_vlc.mpv_player:Unable to play current media",
            ],
        )

        # assert the call
        mpv_player.callbacks["finished"].assert_called_with(999)
        mpv_player.callbacks["error"].assert_called_with(
            999, "Unable to play current media: error message"
        )
        self.assertIsNone(mpv_player.playing_id)
        self.assertFalse(mpv_player.in_transition)

    @patch.object(MpvMediaPlayer, "set_mpv_default_callbacks")
    def test_init(self, mocked_set_mpv_defaul_callback):
        """Test to initialize MPV player with custom config
        """
        mpv_player, (mpv_class, _, _) = self.get_instance({"mpv": {"key1": "value1"}})
        mpv_class.return_value.__setitem__.assert_called_with("key1", "value1")
        mocked_set_mpv_defaul_callback.assert_called_with()
