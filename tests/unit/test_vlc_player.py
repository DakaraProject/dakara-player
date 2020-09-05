import sys
from queue import Queue
from threading import Event
from unittest import skipIf, TestCase
from unittest.mock import MagicMock, patch

import vlc
from dakara_base.resources_manager import get_file
from path import Path

from dakara_player_vlc.vlc_player import (
    InvalidStateError,
    mrl_to_path,
    path_to_mrl,
    VlcMediaPlayer,
)
from dakara_player_vlc.media_player import KaraFolderNotFound


@patch("dakara_player_vlc.media_player.PATH_BACKGROUNDS", "bg")
@patch("dakara_player_vlc.media_player.TRANSITION_DURATION", 10)
@patch("dakara_player_vlc.media_player.IDLE_DURATION", 20)
class VlcMediaPlayerTestCase(TestCase):
    """Test the VLC player class unitary
    """

    def setUp(self):
        # create playlist entry ID
        self.id = 42

        # create playlist entry file path
        self.song_file_path = Path("path/to/file")

        # create playlist entry
        self.playlist_entry = {
            "id": self.id,
            "song": {"file_path": self.song_file_path},
            "owner": "me",
            "use_instrumental": False,
        }

    def get_instance(self, config={}):
        """Get a heavily mocked instance of VlcMediaPlayer

        Args:
            config (dict): configuration passed to the constructor.

        Returns:
            tuple: contains the following elements:
                VlcMediaPlayer: instance;
                tuple: contains the mocked objects, for checking:
                    unittest.mock.MagicMock: VLC Instance instance;
                    unittest.mock.MagicMock: BackgroundLoader instance;
                    unittest.mock.MagicMock: TextGenerator instance.
        """
        with patch(
            "dakara_player_vlc.media_player.TextGenerator"
        ) as mocked_instance_class, patch(
            "dakara_player_vlc.media_player.BackgroundLoader"
        ) as mocked_background_loader_class, patch(
            "dakara_player_vlc.vlc_player.Instance"
        ) as mocked_text_generator_class:
            return (
                VlcMediaPlayer(Event(), Queue(), config, Path("temp")),
                (
                    mocked_instance_class,
                    mocked_background_loader_class,
                    mocked_text_generator_class,
                ),
            )

    def test_set_callback(self):
        """Test the assignation of a callback
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # create a callback function
        callback = MagicMock()

        # pre assert the callback is not set yet
        self.assertIsNot(vlc_player.callbacks.get("test"), callback)

        # call the method
        vlc_player.set_callback("test", callback)

        # post assert the callback is now set
        self.assertIs(vlc_player.callbacks.get("test"), callback)

    def test_set_vlc_callback(self):
        """Test the assignation of a callback to a VLC event

        We have also to mock the event manager method because there is no way
        with the VLC library to know which callback is associated to a given
        event.
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # patch the event creator
        vlc_player.event_manager.event_attach = MagicMock()

        # create a callback function
        callback = MagicMock()

        # pre assert the callback is not set yet
        self.assertIsNot(
            vlc_player.vlc_callbacks.get(vlc.EventType.MediaPlayerEndReached), callback
        )

        # call the method
        vlc_player.set_vlc_callback(vlc.EventType.MediaPlayerEndReached, callback)

        # assert the callback is now set
        self.assertIs(
            vlc_player.vlc_callbacks.get(vlc.EventType.MediaPlayerEndReached), callback
        )

        # assert the event manager got the right arguments
        vlc_player.event_manager.event_attach.assert_called_with(
            vlc.EventType.MediaPlayerEndReached, callback
        )

    @patch("dakara_player_vlc.vlc_player.vlc.libvlc_get_version", autospec=True)
    def test_get_version(self, mocked_libvlc_get_version):
        """Test to get the VLC version
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the version of VLC
        mocked_libvlc_get_version.return_value = b"0.0.0 NoName"

        # pre assert that test screen parameters are empty
        self.assertListEqual(vlc_player.media_parameters_text_screen, [])

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.get_version()

        # assert the effect on logger
        self.assertListEqual(
            logger.output, ["INFO:dakara_player_vlc.vlc_player:VLC 0.0.0 NoName"]
        )

        # assert that test screen parameters are empty
        self.assertListEqual(vlc_player.media_parameters_text_screen, [])

    @patch("dakara_player_vlc.vlc_player.vlc.libvlc_get_version", autospec=True)
    def test_get_version_3(self, mocked_libvlc_get_version):
        """Test to check VLC version 3
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the version of VLC
        mocked_libvlc_get_version.return_value = b"3.0.0 NoName"

        # pre assert that test screen parameters are empty
        self.assertListEqual(vlc_player.media_parameters_text_screen, [])

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            vlc_player.get_version()

        # assert that test screen parameters are empty
        self.assertListEqual(
            vlc_player.media_parameters_text_screen, ["no-sub-autodetect-file"]
        )

    @patch.object(Path, "exists")
    def test_check_kara_folder_path(self, mocked_exists):
        """Test to check if the kara folder exists
        """
        # create instance
        vlc_player, _ = self.get_instance({"kara_folder": "/path/to/kara/directory"})

        # pretend the directory exists
        mocked_exists.return_value = True

        # call the method
        vlc_player.check_kara_folder_path()

        # assert the call
        mocked_exists.assert_called_with()

    @patch.object(Path, "exists")
    def test_check_kara_folder_path_does_not_exist(self, mocked_exists):
        """Test to check if the kara folder does not exist
        """
        # create instance
        vlc_player, _ = self.get_instance({"kara_folder": "/path/to/kara/directory"})

        # pretend the directory does not exist
        mocked_exists.return_value = False

        # call the method
        with self.assertRaises(KaraFolderNotFound) as error:
            vlc_player.check_kara_folder_path()

        # assert the error
        self.assertEqual(
            str(error.exception),
            'Karaoke folder "/path/to/kara/directory" does not exist',
        )

    @patch.object(VlcMediaPlayer, "check_kara_folder_path")
    @patch.object(VlcMediaPlayer, "get_version")
    def test_load(self, mocked_get_version, mocked_check_kara_folder_path):
        """Test to load the instance
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # call the method
        vlc_player.load()

        # assert the calls
        mocked_get_version.assert_called_with()
        mocked_check_kara_folder_path.assert_called_with()
        vlc_player.player.set_fullscreen.assert_called_with(False)
        vlc_player.background_loader.load.assert_called_with()
        vlc_player.text_generator.load.assert_called_with()

    @patch.object(Path, "exists")
    def test_play_playlist_entry_error_file(self, mocked_exists):
        """Test to play a file that does not exist
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the system call
        mocked_exists.return_value = False

        # mock the callbacks
        vlc_player.set_callback("started_transition", MagicMock())
        vlc_player.set_callback("started_song", MagicMock())
        vlc_player.set_callback("could_not_play", MagicMock())

        # pre assertions
        self.assertIsNone(vlc_player.playing_id)

        # call the method
        with self.assertLogs("dakara_player_vlc.media_player", "DEBUG") as logger:
            vlc_player.play_playlist_entry(self.playlist_entry)

            # call assertions
            mocked_exists.assert_called_once_with()

            # post assertions
            self.assertIsNone(vlc_player.playing_id)

            # assert the callbacks
            vlc_player.callbacks["started_transition"].assert_not_called()
            vlc_player.callbacks["started_song"].assert_not_called()
            vlc_player.callbacks["could_not_play"].assert_called_with(self.id)

        # assert the effects on logs
        self.assertListEqual(
            logger.output,
            [
                "ERROR:dakara_player_vlc.media_player:File not found '{}'".format(
                    self.song_file_path
                )
            ],
        )

    @patch.object(VlcMediaPlayer, "get_audio_tracks_id")
    @patch.object(VlcMediaPlayer, "get_number_tracks")
    @patch.object(VlcMediaPlayer, "get_instrumental_audio_file")
    def test_manage_instrumental_file(
        self,
        mocked_get_instrumental_audio_file,
        mocked_get_number_tracks,
        mocked_get_audio_tracks_id,
    ):
        """Test add instrumental file
        """
        # create instance
        vlc_player, (_, _, instance) = self.get_instance(
            config={"kara_folder": get_file("tests.resources", "")}
        )
        video_path = get_file("tests.resources", "") / "path" / "to" / "video"
        audio_path = get_file("tests.resources", "") / "path" / "to" / "audio"

        # pre assertions
        self.assertIsNone(vlc_player.audio_track_id)
        self.assertIsNotNone(vlc_player.kara_folder_path)

        # set playlist entry to request instrumental
        self.playlist_entry["use_instrumental"] = True

        # mocks
        mocked_get_instrumental_audio_file.return_value = audio_path
        mocked_get_number_tracks.return_value = 2
        mocked_media_pending = instance.return_value.media_new_path.return_value
        vlc_player.media_pending = mocked_media_pending

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.manage_instrumental(self.playlist_entry, video_path)

        # post assertions
        self.assertEqual(vlc_player.audio_track_id, 2)

        # assert the effects on logs
        self.assertListEqual(
            logger.output,
            [
                "INFO:dakara_player_vlc.vlc_player:Requesting to play instrumental "
                "file '{}' for '{}'".format(audio_path, video_path),
            ],
        )

        # assert the call
        mocked_get_audio_tracks_id.assert_not_called()

    @patch.object(VlcMediaPlayer, "get_number_tracks")
    @patch.object(VlcMediaPlayer, "get_instrumental_audio_file")
    def test_manage_instrumental_file_error_slaves_add(
        self, mocked_get_instrumental_audio_file, mocked_get_number_tracks,
    ):
        """Test to be unable to add instrumental file
        """
        # create instance
        vlc_player, (_, _, instance) = self.get_instance(
            config={"kara_folder": get_file("tests.resources", "")}
        )
        video_path = get_file("tests.resources", "") / "path" / "to" / "video"
        audio_path = get_file("tests.resources", "") / "path" / "to" / "audio"

        # pre assertions
        self.assertIsNone(vlc_player.audio_track_id)
        self.assertIsNotNone(vlc_player.kara_folder_path)

        # set playlist entry to request instrumental
        self.playlist_entry["use_instrumental"] = True

        # mocks
        mocked_get_instrumental_audio_file.return_value = audio_path
        mocked_get_number_tracks.return_value = 2

        # make slaves_add method unavailable
        mocked_media_pending = instance.return_value.media_new_path.return_value
        mocked_media_pending.slaves_add.side_effect = NameError("no slaves_add")
        vlc_player.media_pending = mocked_media_pending

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.manage_instrumental(self.playlist_entry, video_path)

        # post assertions
        self.assertIsNone(vlc_player.audio_track_id)

        # assert the effects on logs
        self.assertListEqual(
            logger.output,
            [
                "INFO:dakara_player_vlc.vlc_player:Requesting to play instrumental "
                "file '{}' for '{}'".format(audio_path, video_path),
                "ERROR:dakara_player_vlc.vlc_player:This version of VLC does "
                "not support slaves, cannot add instrumental file",
            ],
        )

    @patch.object(VlcMediaPlayer, "get_audio_tracks_id")
    @patch.object(VlcMediaPlayer, "get_number_tracks")
    @patch.object(VlcMediaPlayer, "get_instrumental_audio_file")
    def test_manage_instrumental_track(
        self,
        mocked_get_instrumental_audio_file,
        mocked_get_number_tracks,
        mocked_get_audio_tracks_id,
    ):
        """Test add instrumental track
        """
        # create instance
        vlc_player, (_, _, instance) = self.get_instance(
            config={"kara_folder": get_file("tests.resources", "")}
        )
        video_path = get_file("tests.resources", "") / "path" / "to" / "video"

        # pre assertions
        self.assertIsNone(vlc_player.audio_track_id)
        self.assertIsNotNone(vlc_player.kara_folder_path)

        # set playlist entry to request instrumental
        self.playlist_entry["use_instrumental"] = True

        # mocks
        mocked_get_instrumental_audio_file.return_value = None
        mocked_get_audio_tracks_id.return_value = [0, 99, 42]
        mocked_media_pending = instance.return_value.media_new_path.return_value
        vlc_player.media_pending = mocked_media_pending

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.manage_instrumental(self.playlist_entry, video_path)

        # post assertions
        self.assertEqual(vlc_player.audio_track_id, 99)

        # assert the effects on logs
        self.assertListEqual(
            logger.output,
            [
                "INFO:dakara_player_vlc.vlc_player:Requesting to play instrumental "
                "track of '{}'".format(video_path),
            ],
        )

        # assert the call
        mocked_get_number_tracks.assert_not_called()

    @patch.object(VlcMediaPlayer, "get_audio_tracks_id")
    @patch.object(VlcMediaPlayer, "get_instrumental_audio_file")
    def test_manage_instrumental_no_instrumental_found(
        self, mocked_get_instrumental_audio_file, mocked_get_audio_tracks_id
    ):
        """Test to cannot find instrumental
        """
        # create instance
        vlc_player, (_, _, instance) = self.get_instance(
            config={"kara_folder": get_file("tests.resources", "")}
        )
        video_path = get_file("tests.resources", "") / "path" / "to" / "video"

        # pre assertions
        self.assertIsNone(vlc_player.audio_track_id)

        # set playlist entry to request instrumental
        self.playlist_entry["use_instrumental"] = True

        # mocks
        mocked_get_instrumental_audio_file.return_value = None
        mocked_get_audio_tracks_id.return_value = [99]

        # make slaves_add method unavailable
        mocked_media_pending = instance.return_value.media_new_path.return_value
        vlc_player.media_pending = mocked_media_pending

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.manage_instrumental(self.playlist_entry, video_path)

        # post assertions
        self.assertIsNone(vlc_player.audio_track_id)

        # assert the effects on logs
        self.assertListEqual(
            logger.output,
            [
                "WARNING:dakara_player_vlc.vlc_player:Cannot find instrumental "
                "file or track for file '{}'".format(video_path)
            ],
        )

    def test_set_pause_idle(self,):
        """Test to set pause when the player is idle
        """
        # create instance
        vlc_player, (_, _, instance_class) = self.get_instance(
            config={"kara_folder": get_file("tests.resources", "")}
        )
        player = instance_class.return_value.media_player_new.return_value

        # mock
        vlc_player.vlc_states["in_idle"].start()

        # call method
        vlc_player.set_pause(True)

        # assert call
        player.pause.assert_not_called()

    @patch.object(VlcMediaPlayer, "create_thread")
    def test_handle_end_reached_transition(self, mocked_create_thread):
        """Test song end callback for after a transition screen
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.states["in_song"].start()
        vlc_player.vlc_states["in_transition"].start()
        vlc_player.playing_id = 999
        vlc_player.set_callback("finished", MagicMock())
        media_pending = MagicMock()
        vlc_player.media_pending = media_pending
        vlc_player.media_pending.get_mrl.return_value = "file:///test.mkv"
        file_path = Path("/test.mkv")

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.handle_end_reached("event")

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.vlc_player:Song end callback called",
                "DEBUG:dakara_player_vlc.vlc_player:Will play '{}'".format(
                    file_path.normpath()
                ),
            ],
        )

        # assert the call
        self.assertFalse(vlc_player.vlc_states["in_transition"].is_active())
        vlc_player.media_pending.get_mrl.assert_called_with()
        vlc_player.callbacks["finished"].assert_not_called()
        mocked_create_thread.assert_called_with(
            target=vlc_player.play_media, args=(media_pending,)
        )

    @patch.object(VlcMediaPlayer, "create_thread")
    def test_handle_end_reached_idle(self, mocked_create_thread):
        """Test song end callback for after an idle screen
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.states["in_idle"].start()
        vlc_player.vlc_states["in_idle"].start()
        vlc_player.set_callback("finished", MagicMock())

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            vlc_player.handle_end_reached("event")

        # assert the call
        vlc_player.callbacks["finished"].assert_not_called()
        mocked_create_thread.assert_called_with(target=vlc_player.play_idle_screen)

    @patch.object(VlcMediaPlayer, "create_thread")
    def test_handle_end_reached_finished(self, mocked_create_thread):
        """Test song end callback for after an actual song
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.states["in_song"].start()
        vlc_player.vlc_states["in_media"].start()
        vlc_player.playing_id = 999
        vlc_player.set_callback("finished", MagicMock())

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            vlc_player.handle_end_reached("event")

        # assert the call
        vlc_player.callbacks["finished"].assert_called_with(999)
        mocked_create_thread.assert_not_called()

    @patch.object(VlcMediaPlayer, "create_thread")
    def test_handle_end_reached_invalid(self, mocked_create_thread):
        """Test song end callback on invalid state
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.set_callback("finished", MagicMock())

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            with self.assertRaises(InvalidStateError):
                vlc_player.handle_end_reached("event")

        # assert the call
        vlc_player.callbacks["finished"].assert_not_called()
        mocked_create_thread.assert_not_called()

    def test_handle_encountered_error(self):
        """Test error callback
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.set_callback("error", MagicMock())
        vlc_player.states["in_song"].start()
        vlc_player.vlc_states["in_media"].start()
        vlc_player.playing_id = 999
        media_pending = MagicMock()
        vlc_player.media_pending = media_pending
        vlc_player.media_pending.get_mrl.return_value = "file:///test.mkv"
        file_path = Path("/test.mkv")

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.handle_encountered_error("event")

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.vlc_player:Error callback called",
                "ERROR:dakara_player_vlc.vlc_player:Unable to play '{}'".format(
                    file_path.normpath()
                ),
            ],
        )

        # assert the call
        vlc_player.callbacks["error"].assert_called_with(
            999, "Unable to play current song"
        )
        self.assertFalse(vlc_player.states["in_song"].is_active())
        self.assertFalse(vlc_player.vlc_states["in_media"].is_active())
        self.assertIsNone(vlc_player.playing_id)

    @patch.object(VlcMediaPlayer, "get_timing")
    def test_handle_playing_unpause(self, mocked_get_timing):
        """Test playing callback when unpausing
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.set_callback("resumed", MagicMock())
        vlc_player.states["in_song"].start()
        vlc_player.vlc_states["in_media"].start()
        vlc_player.vlc_states["in_pause"].start()
        vlc_player.playing_id = 999
        mocked_get_timing.return_value = 25

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.handle_playing("event")

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.vlc_player:Playing callback called",
                "DEBUG:dakara_player_vlc.vlc_player:Resumed play",
            ],
        )

        # assert the call
        vlc_player.callbacks["resumed"].assert_called_with(999, 25)
        self.assertFalse(vlc_player.vlc_states["in_pause"].is_active())

    def test_handle_playing_media_starts(self):
        """Test playing callback when media starts
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.set_callback("started_song", MagicMock())
        vlc_player.states["in_song"].start()
        vlc_player.vlc_states["in_transition"].start()
        vlc_player.vlc_states["in_transition"].finish()
        vlc_player.playing_id = 999
        vlc_player.audio_track_id = None
        media_pending = MagicMock()
        vlc_player.media_pending = media_pending
        vlc_player.media_pending.get_mrl.return_value = "file:///test.mkv"
        file_path = Path("/test.mkv")

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.handle_playing("event")

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.vlc_player:Playing callback called",
                "INFO:dakara_player_vlc.vlc_player:Now playing '{}'".format(
                    file_path.normpath()
                ),
            ],
        )

        # assert the call
        vlc_player.callbacks["started_song"].assert_called_with(999)
        self.assertTrue(vlc_player.vlc_states["in_media"].is_active())

    def test_handle_playing_media_starts_track_id(self):
        """Test playing callback when media starts with requested track ID
        """
        # create instance
        vlc_player, (_, _, instance_class) = self.get_instance()

        # mock the call
        vlc_player.set_callback("started_song", MagicMock())
        vlc_player.states["in_song"].start()
        vlc_player.vlc_states["in_transition"].start()
        vlc_player.vlc_states["in_transition"].finish()
        vlc_player.playing_id = 999
        vlc_player.audio_track_id = 99
        media_pending = MagicMock()
        vlc_player.media_pending = media_pending
        vlc_player.media_pending.get_mrl.return_value = "file:///test.mkv"
        file_path = Path("/test.mkv")
        player = instance_class.return_value.media_player_new.return_value

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.handle_playing("event")

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.vlc_player:Playing callback called",
                "DEBUG:dakara_player_vlc.vlc_player:Requesting to play audio track 99",
                "INFO:dakara_player_vlc.vlc_player:Now playing '{}'".format(
                    file_path.normpath()
                ),
            ],
        )

        # assert the call
        vlc_player.callbacks["started_song"].assert_called_with(999)
        player.audio_set_track.assert_called_with(99)
        self.assertTrue(vlc_player.vlc_states["in_media"].is_active())

    def test_handle_playing_transition_starts(self):
        """Test playing callback when transition starts
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.set_callback("started_transition", MagicMock())
        vlc_player.states["in_song"].start()
        vlc_player.playing_id = 999
        vlc_player.audio_track_id = None
        media_pending = MagicMock()
        vlc_player.media_pending = media_pending
        vlc_player.media_pending.get_mrl.return_value = "file:///test.mkv"
        file_path = Path("/test.mkv")

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.handle_playing("event")

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.vlc_player:Playing callback called",
                "INFO:dakara_player_vlc.vlc_player:Playing transition for '{}'".format(
                    file_path.normpath()
                ),
            ],
        )

        # assert the call
        vlc_player.callbacks["started_transition"].assert_called_with(999)
        self.assertTrue(vlc_player.vlc_states["in_transition"].is_active())

    def test_handle_playing_idle_starts(self):
        """Test playing callback when idle screen starts
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.states["in_idle"].start()

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.handle_playing("event")

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.vlc_player:Playing callback called",
                "DEBUG:dakara_player_vlc.vlc_player:Playing idle screen",
            ],
        )

        # assert the call
        self.assertTrue(vlc_player.vlc_states["in_idle"].is_active())

    def test_handle_playing_invalid(self):
        """Test playing callback on invalid state
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            with self.assertRaisesRegex(
                InvalidStateError, "Playing on an undeterminated state"
            ):
                vlc_player.handle_playing("event")

    @patch.object(VlcMediaPlayer, "get_timing")
    def test_handle_paused(self, mocked_get_timing):
        """Test paused callback
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.set_callback("paused", MagicMock())
        vlc_player.playing_id = 999
        mocked_get_timing.return_value = 25

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.handle_paused("event")

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.vlc_player:Paused callback called",
                "DEBUG:dakara_player_vlc.vlc_player:Set pause",
            ],
        )

        # assert the call
        vlc_player.callbacks["paused"].assert_called_with(999, 25)
        self.assertTrue(vlc_player.vlc_states["in_pause"].is_active())

    def test_default_backgrounds(self):
        """Test to instanciate with default backgrounds
        """
        # create object
        _, (_, mocked_background_loader_class, _) = self.get_instance()

        # assert the instanciation of the background loader
        mocked_background_loader_class.assert_called_with(
            directory="",
            default_directory=Path("bg"),
            background_filenames={"transition": None, "idle": None},
            default_background_filenames={
                "transition": "transition.png",
                "idle": "idle.png",
            },
        )

    def test_custom_backgrounds(self):
        """Test to instanciate with an existing backgrounds directory
        """
        # create object
        _, (_, mocked_background_loader_class, _) = self.get_instance(
            {
                "backgrounds": {
                    "directory": Path("custom/bg").normpath(),
                    "transition_background_name": "custom_transition.png",
                    "idle_background_name": "custom_idle.png",
                }
            }
        )

        # assert the instanciation of the background loader
        mocked_background_loader_class.assert_called_with(
            directory=Path("custom/bg").normpath(),
            default_directory=Path("bg"),
            background_filenames={
                "transition": "custom_transition.png",
                "idle": "custom_idle.png",
            },
            default_background_filenames={
                "transition": "transition.png",
                "idle": "idle.png",
            },
        )

    def test_default_durations(self):
        """Test to instanciate with default durations
        """
        # create object
        vlc_player, _ = self.get_instance()

        # assert the instance
        self.assertDictEqual(vlc_player.durations, {"transition": 10, "idle": 20})

    def test_custom_durations(self):
        """Test to instanciate with custom durations
        """
        # create object
        vlc_player, _ = self.get_instance({"durations": {"transition_duration": 5}})

        # assert the instance
        self.assertDictEqual(vlc_player.durations, {"transition": 5, "idle": 20})


class MrlFunctionsTestCase(TestCase):
    """Test the MRL conversion functions
    """

    is_windows = sys.platform.startswith("win")

    @skipIf(is_windows, "Tested on POSIX")
    def test_mrl_to_path_posix(self):
        """Test to convert MRL to path for POSIX
        """
        path = mrl_to_path("file:///home/username/directory/file%20name.ext")
        self.assertEqual(
            path, Path("/home").normpath() / "username" / "directory" / "file name.ext"
        )

    @skipIf(not is_windows, "Tested on Windows")
    def test_mrl_to_path_windows(self):
        """Test to convert MRL to path for Windows
        """
        path = mrl_to_path("file:///C:/Users/username/directory/file%20name.ext")
        self.assertEqual(
            path,
            Path("C:/Users").normpath() / "username" / "directory" / "file name.ext",
        )

    @skipIf(is_windows, "Tested on POSIX")
    def test_path_to_mrl_posix(self):
        """Test to convert path to MRL for POSIX
        """
        mrl = path_to_mrl(
            Path("/home").normpath() / "username" / "directory" / "file name.ext"
        )
        self.assertEqual(mrl, "file:///home/username/directory/file%20name.ext")

    @skipIf(not is_windows, "Tested on Windows")
    def test_path_to_mrl_windows(self):
        """Test to convert path to MRL for Windows
        """
        mrl = path_to_mrl(
            Path("C:/Users").normpath() / "username" / "directory" / "file name.ext"
        )
        self.assertEqual(mrl, "file:///C:/Users/username/directory/file%20name.ext")
