import shutil
import sys
import tempfile
from queue import Queue
from threading import Event
from unittest import skipIf, TestCase
from unittest.mock import MagicMock, patch, ANY

import vlc
from dakara_base.resources_manager import get_file
from path import Path

from dakara_player_vlc.vlc_player import (
    IDLE_BG_NAME,
    mrl_to_path,
    path_to_mrl,
    TRANSITION_BG_NAME,
    VlcPlayer,
    KaraFolderNotFound,
)

from dakara_player_vlc.resources_manager import get_background


@patch("dakara_player_vlc.vlc_player.PATH_BACKGROUNDS", "bg")
@patch("dakara_player_vlc.vlc_player.TRANSITION_DURATION", 10)
@patch("dakara_player_vlc.vlc_player.IDLE_DURATION", 20)
class VlcPlayerTestCase(TestCase):
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
            "use_intrumental": False,
        }

    def get_instance(self, config={}):
        """Get a heavily mocked instance of VlcPlayer

        Args:
            config (dict): configuration passed to the constructor.

        Returns:
            tuple: contains the following elements:
                VlcPlayer: instance;
                tuple: contains the mocked objects, for checking:
                    unittest.mock.MagicMock: VLC Instance instance;
                    unittest.mock.MagicMock: BackgroundLoader instance;
                    unittest.mock.MagicMock: TextGenerator instance.
        """
        with patch(
            "dakara_player_vlc.vlc_player.TextGenerator"
        ) as mocked_instance_class, patch(
            "dakara_player_vlc.vlc_player.BackgroundLoader"
        ) as mocked_background_loader_class, patch(
            "dakara_player_vlc.vlc_player.Instance"
        ) as mocked_text_generator_class:
            return (
                VlcPlayer(Event(), Queue(), config, Path("temp")),
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
    def test_check_vlc_version(self, mocked_libvlc_get_version):
        """Test to check a VLC version
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the version of VLC
        mocked_libvlc_get_version.return_value = b"0.0.0 NoName"

        # pre assert that test screen parameters are empty
        self.assertListEqual(vlc_player.media_parameters_text_screen, [])

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.check_vlc_version()

        # assert the effect on logger
        self.assertListEqual(
            logger.output, ["INFO:dakara_player_vlc.vlc_player:VLC 0.0.0 NoName"]
        )

        # assert that test screen parameters are empty
        self.assertListEqual(vlc_player.media_parameters_text_screen, [])

    @patch("dakara_player_vlc.vlc_player.vlc.libvlc_get_version", autospec=True)
    def test_check_vlc_version_3(self, mocked_libvlc_get_version):
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
            vlc_player.check_vlc_version()

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

    def test_set_default_callbacks(self):
        """Test to set the default callbacks
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # make the callbacks lists empty
        vlc_player.callbacks = {}
        vlc_player.vlc_callbacks = {}

        # call the method
        vlc_player.set_default_callbacks()

        # assert there are callbacks defined
        self.assertCountEqual(
            list(vlc_player.callbacks.keys()),
            [
                "started_transition",
                "started_song",
                "could_not_play",
                "finished",
                "paused",
                "resumed",
                "error",
            ],
        )
        self.assertCountEqual(
            list(vlc_player.vlc_callbacks.keys()),
            [
                vlc.EventType.MediaPlayerEndReached,
                vlc.EventType.MediaPlayerEncounteredError,
                vlc.EventType.MediaPlayerPlaying,
            ],
        )

    @patch.object(VlcPlayer, "check_kara_folder_path")
    @patch.object(VlcPlayer, "check_vlc_version")
    def test_load(self, mocked_check_vlc_version, mocked_check_kara_folder_path):
        """Test to load the instance
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # call the method
        vlc_player.load()

        # assert the calls
        mocked_check_vlc_version.assert_called_with()
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
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
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
                "ERROR:dakara_player_vlc.vlc_player:File not found '{}'".format(
                    self.song_file_path
                )
            ],
        )

    @patch.object(VlcPlayer, "create_thread")
    def test_handle_end_reached_transition(self, mocked_create_thread):
        """Test song end callback for after a transition screen
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.in_transition = True
        vlc_player.playing_id = 999
        vlc_player.set_callback("finished", MagicMock())
        vlc_player.set_callback("started_song", MagicMock())
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
                "INFO:dakara_player_vlc.vlc_player:Now playing '{}'".format(
                    file_path.normpath()
                ),
            ],
        )

        # assert the call
        self.assertFalse(vlc_player.in_transition)
        vlc_player.media_pending.get_mrl.assert_called_with()
        vlc_player.callbacks["finished"].assert_not_called()
        vlc_player.callbacks["started_song"].assert_called_with(999)
        mocked_create_thread.assert_called_with(
            target=vlc_player.play_media, args=(media_pending,)
        )

    @patch.object(VlcPlayer, "create_thread")
    def test_handle_end_reached_idle(self, mocked_create_thread):
        """Test song end callback for after an idle screen
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.in_transition = False
        vlc_player.playing_id = None
        vlc_player.set_callback("finished", MagicMock())
        vlc_player.set_callback("started_song", MagicMock())

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            vlc_player.handle_end_reached("event")

        # assert the call
        vlc_player.callbacks["finished"].assert_not_called()
        vlc_player.callbacks["started_song"].assert_not_called()
        mocked_create_thread.assert_called_with(target=vlc_player.play_idle_screen)

    @patch.object(VlcPlayer, "create_thread")
    def test_handle_end_reached_finished(self, mocked_create_thread):
        """Test song end callback for after an actual song
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.in_transition = False
        vlc_player.playing_id = 999
        vlc_player.set_callback("finished", MagicMock())
        vlc_player.set_callback("started_song", MagicMock())

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            vlc_player.handle_end_reached("event")

        # assert the call
        vlc_player.callbacks["finished"].assert_called_with(999)
        vlc_player.callbacks["started_song"].assert_not_called()
        mocked_create_thread.assert_not_called()

    def test_handle_encountered_error(self):
        """Test error callback
        """
        # create instance
        vlc_player, _ = self.get_instance()

        # mock the call
        vlc_player.set_callback("error", MagicMock())
        vlc_player.playing_id = 999

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            vlc_player.handle_encountered_error("event")

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.vlc_player:Error callback called",
                "ERROR:dakara_player_vlc.vlc_player:Unable to play current media",
            ],
        )

        # assert the call
        vlc_player.callbacks["error"].assert_called_with(
            999, "Unable to play current media"
        )
        self.assertIsNone(vlc_player.playing_id)
        self.assertFalse(vlc_player.in_transition)

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


class VlcPlayerIntegrationTestCase(TestCase):
    """Test the VLC player class in real conditions
    """

    def setUp(self):
        # create instance parameter
        self.instance_parameters = ["--vout=vdummy", "--aout=adummy", "--text-renderer=tdummy"]

        # create fullscreen flag
        self.fullscreen = True

        # create kara folder
        self.kara_folder = get_file("tests.resources", "")

        # create media parameter
        self.media_parameters = []

        # create idle background path
        self.idle_background_path = get_background(IDLE_BG_NAME)

        # create transition background path
        self.transition_background_path = get_background(TRANSITION_BG_NAME)

        # create transition duration
        self.transition_duration = 1

        # create a subtitle
        self.subtitle_name = "song.ass"
        self.subtitle_path = self.kara_folder / self.subtitle_name

        # create song path
        self.song_file_name = "song.mkv"
        self.song_file_path = self.kara_folder / self.song_file_name
        self.song2_file_name = "song2.mkv"
        self.song2_file_path = self.kara_folder / self.song2_file_name

        # create playlist entry
        self.playlist_entry = {
            "id": 42,
            "song": {"file_path": self.song_file_path},
            "owner": "me",
            "use_intrumental": False,
        }

        # temporary directory
        self.temp = Path(tempfile.mkdtemp())

        # create vlc player and load it
        self.vlc_player = VlcPlayer(
            Event(),
            Queue(),
            {
                "kara_folder": self.kara_folder,
                "fullscreen": self.fullscreen,
                "vlc": {
                    "instance_parameters": self.instance_parameters,
                    "media_parameters": self.media_parameters,
                },
            },
            self.temp,
        )

        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.load()

    def tearDown(self):
        # remove temporary directory
        shutil.rmtree(self.temp, ignore_errors=True)

    @staticmethod
    def get_event_and_callback(old_callback=None):
        """Get an event and a callback that sets this event

        Args:
            old_callback (function): If given, will call this callback as well.
                This allows to combine existing callbacks with test callbacks
                for the same VLC event type.
        """
        event = Event()

        def callback(vlc_event):
            """Callback that sets the joined event
            """
            # prevent callback to be called twice
            if event.is_set():
                return

            # execute old callback if necessary
            if old_callback:
                old_callback(vlc_event)

            event.set()

        return event, callback

    def test_play_idle_screen(self):
        """Test the display of the idle screen
        """
        # create an event for when the player starts to play
        is_playing, callback_is_playing = self.get_event_and_callback()
        self.vlc_player.set_vlc_callback(
            vlc.EventType.MediaPlayerPlaying, callback_is_playing
        )

        # pre assertions
        self.assertIsNone(self.vlc_player.player.get_media())
        self.assertEqual(self.vlc_player.player.get_state(), vlc.State.NothingSpecial)

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.play_idle_screen()

            # wait for the player to start actually playing
            is_playing.wait()

            # post assertions
            self.assertEqual(self.vlc_player.player.get_state(), vlc.State.Playing)

            self.assertIsNotNone(self.vlc_player.player.get_media())
            media = self.vlc_player.player.get_media()
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.idle_background_path)
            # TODO check which subtitle file is read
            # seems impossible to do for now

            # close the player
            self.vlc_player.stop_player()

    def test_play_playlist_entry(self):
        """Test to play a playlist entry

        First, the transition screen is played, then the song itself.
        """
        # mock the callbacks
        self.vlc_player.set_callback("started_transition", MagicMock())
        self.vlc_player.set_callback("started_song", MagicMock())

        # create an event for when the player starts to play
        is_playing, callback_is_playing = self.get_event_and_callback(
            self.vlc_player.vlc_callbacks[vlc.EventType.MediaPlayerPlaying]
        )
        self.vlc_player.set_vlc_callback(
            vlc.EventType.MediaPlayerPlaying, callback_is_playing
        )

        # pre assertions
        self.assertIsNone(self.vlc_player.playing_id)
        self.assertFalse(self.vlc_player.in_transition)
        self.assertIsNone(self.vlc_player.player.get_media())
        self.assertEqual(self.vlc_player.player.get_state(), vlc.State.NothingSpecial)

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # wait for the player to start actually playing the transition
            is_playing.wait()

            # reset the event to catch when the player starts to play the song
            is_playing.clear()

            # post assertions for transition screen
            self.assertIsNotNone(self.vlc_player.playing_id)
            self.assertTrue(self.vlc_player.in_transition)
            self.assertEqual(self.vlc_player.player.get_state(), vlc.State.Playing)

            # check media exists
            media = self.vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.transition_background_path)

            # check there is no audio track
            track = self.vlc_player.player.audio_get_track()
            self.assertEqual(track, -1)

            # TODO check which subtitle file is read
            # seems impossible to do for now

            # assert the started transition callback has been called
            self.vlc_player.callbacks["started_transition"].assert_called_with(
                self.playlist_entry["id"]
            )

            # wait for the player to start actually playing the song
            is_playing.wait()

            # post assertions for song
            self.assertFalse(self.vlc_player.in_transition)
            self.assertEqual(self.vlc_player.player.get_state(), vlc.State.Playing)

            # check media exists
            media = self.vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song_file_path)

            # check audio track
            track = self.vlc_player.player.audio_get_track()
            self.assertEqual(track, 1)

            # assert the started song callback has been called
            self.vlc_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry["id"]
            )

            # close the player
            self.vlc_player.stop_player()

    def test_play_playlist_entry_instrumental_track(self):
        """Test to play a playlist entry using instrumental track
        """
        # mock the callbacks
        self.vlc_player.set_callback("started_transition", MagicMock())
        self.vlc_player.set_callback("started_song", MagicMock())

        # create an event for when the player starts to play
        is_playing, callback_is_playing = self.get_event_and_callback(
            self.vlc_player.vlc_callbacks[vlc.EventType.MediaPlayerPlaying]
        )
        self.vlc_player.set_vlc_callback(
            vlc.EventType.MediaPlayerPlaying, callback_is_playing
        )

        # pre assertions
        self.assertIsNone(self.vlc_player.playing_id)
        self.assertFalse(self.vlc_player.in_transition)
        self.assertIsNone(self.vlc_player.player.get_media())
        self.assertEqual(self.vlc_player.player.get_state(), vlc.State.NothingSpecial)

        # request to use instrumental track
        self.playlist_entry["use_intrumental"] = True

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # wait for the player to start actually playing the song
            is_playing.wait()
            is_playing.clear()
            is_playing.wait()

            # post assertions for song
            self.assertFalse(self.vlc_player.in_transition)
            self.assertEqual(self.vlc_player.player.get_state(), vlc.State.Playing)

            # check media exists
            media = self.vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song_file_path)

            # check audio track
            track = self.vlc_player.player.audio_get_track()
            self.assertEqual(track, 2)

            # assert the started song callback has been called
            self.vlc_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry["id"]
            )

            # close the player
            self.vlc_player.stop_player()

    @skipIf(
        not hasattr(vlc, "libvlc_media_slaves_add"), "VLC does not support slaves_add"
    )
    def test_play_playlist_entry_instrumental_file(self):
        """Test to play a playlist entry using instrumental file
        """
        # mock the callbacks
        self.vlc_player.set_callback("started_transition", MagicMock())
        self.vlc_player.set_callback("started_song", MagicMock())

        # create an event for when the player starts to play
        is_playing, callback_is_playing = self.get_event_and_callback(
            self.vlc_player.vlc_callbacks[vlc.EventType.MediaPlayerPlaying]
        )
        self.vlc_player.set_vlc_callback(
            vlc.EventType.MediaPlayerPlaying, callback_is_playing
        )

        # pre assertions
        self.assertIsNone(self.vlc_player.playing_id)
        self.assertFalse(self.vlc_player.in_transition)
        self.assertIsNone(self.vlc_player.player.get_media())
        self.assertEqual(self.vlc_player.player.get_state(), vlc.State.NothingSpecial)

        # request to use instrumental file
        self.playlist_entry["song"]["file_path"] = self.song2_file_path
        self.playlist_entry["use_intrumental"] = True

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # wait for the player to start actually playing the song
            is_playing.wait()
            is_playing.clear()
            is_playing.wait()

            # post assertions for song
            self.assertFalse(self.vlc_player.in_transition)
            self.assertEqual(self.vlc_player.player.get_state(), vlc.State.Playing)

            # check media exists
            media = self.vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song2_file_path)

            # check audio track
            track = self.vlc_player.player.audio_get_track()
            self.assertEqual(track, 4)

            # assert the started song callback has been called
            self.vlc_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry["id"]
            )

            # close the player
            self.vlc_player.stop_player()

    def test_set_pause(self):
        """Test to pause and unpause the player
        """
        # mock the callbacks
        self.vlc_player.set_callback("paused", MagicMock())
        self.vlc_player.set_callback("resumed", MagicMock())

        # create an event for when the player starts to play
        is_playing, callback_is_playing = self.get_event_and_callback(
            self.vlc_player.vlc_callbacks[vlc.EventType.MediaPlayerPlaying]
        )
        self.vlc_player.set_vlc_callback(
            vlc.EventType.MediaPlayerPlaying, callback_is_playing
        )

        # create an event for when the player pauses
        is_paused, callback_is_paused = self.get_event_and_callback()
        self.vlc_player.set_vlc_callback(
            vlc.EventType.MediaPlayerPaused, callback_is_paused
        )

        # start the playlist entry
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # wait for the player to start actually playing the song
            is_playing.wait()
            is_playing.clear()
            is_playing.wait()

            # pre asserts
            self.assertFalse(self.vlc_player.is_paused())
            self.assertFalse(self.vlc_player.is_idle())

            # call the method to pause the player
            self.vlc_player.set_pause(True)
            timing = self.vlc_player.get_timing()

            # wait for the player to be paused
            is_paused.wait(2)

            # assert the call
            self.assertTrue(self.vlc_player.is_paused())

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_called_with(
                self.playlist_entry["id"], timing
            )
            self.vlc_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            self.vlc_player.callbacks["paused"].reset_mock()
            self.vlc_player.callbacks["resumed"].reset_mock()
            is_playing.clear()

            # call the method to resume the player
            self.vlc_player.set_pause(False)

            # wait for the player to play again
            is_playing.wait()

            # assert the call
            self.assertFalse(self.vlc_player.is_paused())

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_not_called()
            self.vlc_player.callbacks["resumed"].assert_called_with(
                self.playlist_entry["id"],
                timing,  # on a slow computer, the timing may be inaccurate
            )

            # close the player
            self.vlc_player.stop_player()

    def test_set_double_pause(self):
        """Test that double pause and double resume have no effects
        """
        # mock the callbacks
        self.vlc_player.set_callback("paused", MagicMock())
        self.vlc_player.set_callback("resumed", MagicMock())

        # create an event for when the player starts to play
        is_playing, callback_is_playing = self.get_event_and_callback(
            self.vlc_player.vlc_callbacks[vlc.EventType.MediaPlayerPlaying]
        )
        self.vlc_player.set_vlc_callback(
            vlc.EventType.MediaPlayerPlaying, callback_is_playing
        )

        # create an event for when the player pauses
        is_paused, callback_is_paused = self.get_event_and_callback()
        self.vlc_player.set_vlc_callback(
            vlc.EventType.MediaPlayerPaused, callback_is_paused
        )

        # start the playlist entry
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # wait for the player to start actually playing the song
            is_playing.wait()
            is_playing.clear()
            is_playing.wait()

            # pre asserts
            self.assertFalse(self.vlc_player.is_paused())
            self.assertFalse(self.vlc_player.is_idle())

            # call the method to pause the player
            self.vlc_player.set_pause(True)

            # wait for the player to be paused
            is_paused.wait(2)

            # assert the call
            self.assertTrue(self.vlc_player.is_paused())

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_called_with(ANY, ANY)
            self.vlc_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            self.vlc_player.callbacks["paused"].reset_mock()
            self.vlc_player.callbacks["resumed"].reset_mock()
            is_playing.clear()
            is_paused.clear()

            # re-call the method to pause the player
            self.vlc_player.set_pause(True)

            # assert callback was not called
            self.assertFalse(is_paused.is_set())

            # assert the call
            self.assertTrue(self.vlc_player.is_paused())

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_not_called()
            self.vlc_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            self.vlc_player.callbacks["paused"].reset_mock()
            self.vlc_player.callbacks["resumed"].reset_mock()
            is_playing.clear()
            is_paused.clear()

            # call the method to resume the player
            self.vlc_player.set_pause(False)

            # wait for the player to play again
            is_playing.wait()

            # assert the call
            self.assertFalse(self.vlc_player.is_paused())

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_not_called()
            self.vlc_player.callbacks["resumed"].assert_called_with(ANY, ANY)

            # reset the mocks
            self.vlc_player.callbacks["paused"].reset_mock()
            self.vlc_player.callbacks["resumed"].reset_mock()
            is_playing.clear()
            is_paused.clear()

            # re-call the method to resume the player
            self.vlc_player.set_pause(False)

            # assert the callback was not called
            self.assertFalse(is_playing.is_set())

            # assert the call
            self.assertFalse(self.vlc_player.is_paused())

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_not_called()
            self.vlc_player.callbacks["resumed"].assert_not_called()

            # close the player
            self.vlc_player.stop_player()


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
