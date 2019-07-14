from unittest import TestCase
from unittest.mock import MagicMock, patch, ANY
from threading import Event
from queue import Queue

from vlc import State, EventType
from path import Path

from dakara_player_vlc.version import __version__ as dakara_player_vlc_version
from dakara_player_vlc.vlc_player import (
    VlcPlayer,
    mrl_to_path,
    IDLE_BG_NAME,
    TRANSITION_BG_NAME,
)

from dakara_player_vlc.resources_manager import (
    get_test_material,
    get_background,
    PATH_TEST_MATERIALS,
)


class VlcPlayerPreLoadTestCase(TestCase):
    """Test the VLC player class before it is loaded
    """

    def setUp(self):
        # create instance
        self.vlc_player = VlcPlayer(Event(), Queue(), {}, MagicMock())

    def test_set_callback(self):
        """Test the assignation of a callback
        """
        # create a callback function
        callback = MagicMock()

        # pre assert the callback is not set yet
        self.assertIsNot(self.vlc_player.callbacks.get("test"), callback)

        # call the method
        self.vlc_player.set_callback("test", callback)

        # post assert the callback is now set
        self.assertIs(self.vlc_player.callbacks.get("test"), callback)

    def test_set_vlc_callback(self):
        """Test the assignation of a callback to a VLC event

        We have also to mock the event manager method because there is no way
        with the VLC library to know which callback is associated to a given
        event.
        """
        # patch the event creator
        self.vlc_player.event_manager.event_attach = MagicMock()

        # create a callback function
        callback = MagicMock()

        # pre assert the callback is not set yet
        self.assertIsNot(
            self.vlc_player.vlc_callbacks.get(EventType.MediaPlayerEndReached), callback
        )

        # call the method
        self.vlc_player.set_vlc_callback(EventType.MediaPlayerEndReached, callback)

        # assert the callback is now set
        self.assertIs(
            self.vlc_player.vlc_callbacks.get(EventType.MediaPlayerEndReached), callback
        )

        # assert the event manager got the right arguments
        self.vlc_player.event_manager.event_attach.assert_called_with(
            EventType.MediaPlayerEndReached, callback
        )

    @patch("dakara_player_vlc.vlc_player.vlc.libvlc_get_version")
    def test_check_vlc_version(self, mocked_libvlc_get_version):
        """Test to check a VLC version
        """
        # mock the version of VLC
        mocked_libvlc_get_version.return_value = b"0.0.0 NoName"

        # pre assert that test screen parameters are empty
        self.assertListEqual(self.vlc_player.media_parameters_text_screen, [])

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            self.vlc_player.check_vlc_version()

        # assert the effect on logger
        self.assertListEqual(
            logger.output, ["INFO:dakara_player_vlc.vlc_player:VLC 0.0.0 NoName"]
        )

        # assert that test screen parameters are empty
        self.assertListEqual(self.vlc_player.media_parameters_text_screen, [])

    @patch("dakara_player_vlc.vlc_player.vlc.libvlc_get_version")
    def test_check_vlc_version_3(self, mocked_libvlc_get_version):
        """Test to check VLC version 3
        """
        # mock the version of VLC
        mocked_libvlc_get_version.return_value = b"3.0.0 NoName"

        # pre assert that test screen parameters are empty
        self.assertListEqual(self.vlc_player.media_parameters_text_screen, [])

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.check_vlc_version()

        # assert that test screen parameters are empty
        self.assertListEqual(
            self.vlc_player.media_parameters_text_screen, ["no-sub-autodetect-file"]
        )

    def test_set_default_callbacks(self):
        """Test to set the default callbacks
        """
        # macke the callbacks lists empty
        self.vlc_player.callbacks = {}
        self.vlc_player.vlc_callbacks = {}

        # call the method
        self.vlc_player.set_default_callbacks()

        # assert there are callbacks defined
        self.assertCountEqual(
            list(self.vlc_player.callbacks.keys()),
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
            list(self.vlc_player.vlc_callbacks.keys()),
            [EventType.MediaPlayerEndReached, EventType.MediaPlayerEncounteredError],
        )

    @patch.object(VlcPlayer, "check_vlc_version")
    def test_load(self, mocked_check_vlc_version):
        """Test to load the instance
        """
        # hard patch the attributes
        # normally, I should put these actions in dedicated methods I would
        # `patch.object`ed, but since the added value is negligible, I stick
        # with this weird hybrid approach for now
        self.vlc_player.player = MagicMock()
        self.vlc_player.background_loader = MagicMock()

        # call the method
        self.vlc_player.load()

        # assert the calls
        mocked_check_vlc_version.assert_called_with()
        self.vlc_player.player.set_fullscreen.assert_called_with(False)
        self.vlc_player.background_loader.load.assert_called_with()


class VlcPlayerPostLoadTestCase(TestCase):
    """Test the VLC player class after it is loaded
    """

    def setUp(self):
        # create instance parameter
        self.instance_parameters = []

        # create fullscreen flag
        self.fullscreen = True

        # create kara folder
        self.kara_folder = PATH_TEST_MATERIALS

        # create media parameter
        self.media_parameters = ["no-video"]

        # create idle background path
        self.idle_background_path = get_background(IDLE_BG_NAME)

        # create transition background path
        self.transition_background_path = get_background(TRANSITION_BG_NAME)

        # create transition duration
        self.transition_duration = 1

        # create a mock text generator
        self.text_generator = MagicMock()

        # create a subtitle
        self.subtitle_path = get_test_material("song.ass")

        # create song path
        self.song_file_path = get_test_material("song.png")

        # create playlist entry
        self.playlist_entry = {"id": 42, "song": {"file_path": self.song_file_path}}

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
            self.text_generator,
        )

        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.load()

    @staticmethod
    def get_event_and_callback():
        """Get an event and a callback that sets this event
        """
        event = Event()

        def callback(*args, **kwargs):
            """Callback that sets the joined event
            """
            event.set()

        return event, callback

    def test_play_idle_screen(self):
        """Test the display of the idle screen
        """
        # mock the text generator
        self.text_generator.create_idle_text.return_value = self.subtitle_path

        # create an event for when the player starts to play
        is_playing, callback_is_playing = self.get_event_and_callback()
        self.vlc_player.set_vlc_callback(
            EventType.MediaPlayerPlaying, callback_is_playing
        )

        # pre assertions
        self.assertIsNone(self.vlc_player.player.get_media())
        self.assertEqual(self.vlc_player.player.get_state(), State.NothingSpecial)

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            self.vlc_player.play_idle_screen()

            # wait for the player to start actually playing
            is_playing.wait()

            # call assertions
            self.text_generator.create_idle_text.assert_called_once_with(
                {
                    "notes": [
                        "VLC " + self.vlc_player.vlc_version,
                        "Dakara player " + dakara_player_vlc_version,
                    ]
                }
            )

            # post assertions
            self.assertEqual(self.vlc_player.player.get_state(), State.Playing)

            self.assertIsNotNone(self.vlc_player.player.get_media())
            media = self.vlc_player.player.get_media()
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.idle_background_path)
            # TODO check which subtitle file is read
            # seems impossible to do for now

        # assert the effect on logs
        self.assertListEqual(
            logger.output, ["DEBUG:dakara_player_vlc.vlc_player:Playing idle screen"]
        )

    def test_play_playlist_entry(self):
        """Test to play a playlist entry

        First, the transition screen is played, then the song itself.
        """
        # mock the text generator
        self.text_generator.create_transition_text.return_value = self.subtitle_path

        # mock the callbacks
        self.vlc_player.set_callback("started_transition", MagicMock())
        self.vlc_player.set_callback("started_song", MagicMock())

        # create an event for when the player starts to play
        is_playing, callback_is_playing = self.get_event_and_callback()
        self.vlc_player.set_vlc_callback(
            EventType.MediaPlayerPlaying, callback_is_playing
        )

        # pre assertions
        self.assertIsNone(self.vlc_player.playing_id)
        self.assertFalse(self.vlc_player.in_transition)
        self.assertIsNone(self.vlc_player.player.get_media())
        self.assertEqual(self.vlc_player.player.get_state(), State.NothingSpecial)

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # wait for the player to start actually playing the transition
            is_playing.wait()

            # reset the event to catch when the player starts to play the song
            is_playing.clear()

            # call assertions
            self.text_generator.create_transition_text.assert_called_once_with(
                self.playlist_entry
            )

            # post assertions for transition screen
            self.assertIsNotNone(self.vlc_player.playing_id)
            self.assertTrue(self.vlc_player.in_transition)
            self.assertEqual(self.vlc_player.player.get_state(), State.Playing)

            self.assertIsNotNone(self.vlc_player.player.get_media())
            media = self.vlc_player.player.get_media()
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.transition_background_path)
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
            self.assertEqual(self.vlc_player.player.get_state(), State.Playing)

            self.assertIsNotNone(self.vlc_player.player.get_media())
            media = self.vlc_player.player.get_media()
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song_file_path)

            # assert the started song callback has been called
            self.vlc_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry["id"]
            )

            # close the player
            self.vlc_player.stop_player()

        # assert the effect on player
        self.assertListEqual(
            logger.output,
            [
                "INFO:dakara_player_vlc.vlc_player:Playing transition for '{}'".format(
                    self.song_file_path
                ),
                "DEBUG:dakara_player_vlc.vlc_player:Song end callback called",
                "INFO:dakara_player_vlc.vlc_player:Now playing '{}'".format(
                    self.song_file_path
                ),
                "INFO:dakara_player_vlc.vlc_player:Stopping player",
                "DEBUG:dakara_player_vlc.vlc_player:Stopped player",
            ],
        )

    @patch("dakara_player_vlc.vlc_player.os.path.isfile")
    def test_play_playlist_entry_error_file(self, mock_isfile):
        """Test to play a file that does not exist
        """
        # mock the system call
        mock_isfile.return_value = False

        # mock the callbacks
        self.vlc_player.set_callback("started_transition", MagicMock())
        self.vlc_player.set_callback("started_song", MagicMock())
        self.vlc_player.set_callback("could_not_play", MagicMock())

        # pre assertions
        self.assertIsNone(self.vlc_player.playing_id)
        self.assertIsNone(self.vlc_player.player.get_media())
        self.assertEqual(self.vlc_player.player.get_state(), State.NothingSpecial)

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # call assertions
            mock_isfile.assert_called_once_with(self.song_file_path)

            # post assertions
            self.assertIsNone(self.vlc_player.playing_id)
            self.assertIsNone(self.vlc_player.player.get_media())
            self.assertEqual(self.vlc_player.player.get_state(), State.NothingSpecial)

            # assert the callbacks
            self.vlc_player.callbacks["started_transition"].assert_not_called()
            self.vlc_player.callbacks["started_song"].assert_not_called()
            self.vlc_player.callbacks["could_not_play"].assert_called_with(
                self.playlist_entry["id"]
            )

        # assert the effects on logs
        self.assertListEqual(
            logger.output,
            [
                "ERROR:dakara_player_vlc.vlc_player:File not found '{}'".format(
                    self.song_file_path
                )
            ],
        )

    def test_handle_end_reached_transition(self):
        """Test song end callback for after a transition screen
        """
        # mock the call
        self.vlc_player.in_transition = True
        self.vlc_player.playing_id = 999
        self.vlc_player.set_callback("finished", MagicMock())
        self.vlc_player.set_callback("started_song", MagicMock())
        self.vlc_player.create_thread = MagicMock()
        media_pending = MagicMock()
        self.vlc_player.media_pending = media_pending
        self.vlc_player.media_pending.get_mrl.return_value = "file:///test.mkv"
        file_path = Path("/test.mkv")

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            self.vlc_player.handle_end_reached("event")

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
        self.assertFalse(self.vlc_player.in_transition)
        self.vlc_player.media_pending.get_mrl.assert_called_with()
        self.vlc_player.callbacks["finished"].assert_not_called()
        self.vlc_player.callbacks["started_song"].assert_called_with(999)
        self.vlc_player.create_thread.assert_called_with(
            target=self.vlc_player.play_media, args=(media_pending,)
        )

    def test_handle_end_reached_idle(self):
        """Test song end callback for after an idle screen
        """
        # mock the call
        self.vlc_player.in_transition = False
        self.vlc_player.playing_id = None
        self.vlc_player.set_callback("finished", MagicMock())
        self.vlc_player.set_callback("started_song", MagicMock())
        self.vlc_player.create_thread = MagicMock()

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.handle_end_reached("event")

        # assert the call
        self.vlc_player.callbacks["finished"].assert_not_called()
        self.vlc_player.callbacks["started_song"].assert_not_called()
        self.vlc_player.create_thread.assert_called_with(
            target=self.vlc_player.play_idle_screen
        )

    def test_handle_end_reached_finished(self):
        """Test song end callback for after an actual song
        """
        # mock the call
        self.vlc_player.in_transition = False
        self.vlc_player.playing_id = 999
        self.vlc_player.set_callback("finished", MagicMock())
        self.vlc_player.set_callback("started_song", MagicMock())
        self.vlc_player.create_thread = MagicMock()

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.handle_end_reached("event")

        # assert the call
        self.vlc_player.callbacks["finished"].assert_called_with(999)
        self.vlc_player.callbacks["started_song"].assert_not_called()
        self.vlc_player.create_thread.assert_not_called()

    @patch("dakara_player_vlc.vlc_player.vlc.libvlc_errmsg")
    def test_handle_encountered_error(self, mock_libvcl_errmsg):
        """Test error callback
        """
        # mock the call
        mock_libvcl_errmsg.return_value = b"error"
        self.vlc_player.set_callback("error", MagicMock())
        self.vlc_player.playing_id = 999

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
            self.vlc_player.handle_encountered_error("event")

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.vlc_player:Error callback called",
                "ERROR:dakara_player_vlc.vlc_player:error",
            ],
        )

        # assert the call
        mock_libvcl_errmsg.assert_called_with()
        self.vlc_player.callbacks["error"].assert_called_with(999, "error")
        self.assertIsNone(self.vlc_player.playing_id)
        self.assertFalse(self.vlc_player.in_transition)

    def test_set_pause(self):
        """Test to pause and unpause the player
        """
        # mock the text generator
        self.text_generator.create_transition_text.return_value = self.subtitle_path

        # mock the callbacks
        self.vlc_player.set_callback("paused", MagicMock())
        self.vlc_player.set_callback("resumed", MagicMock())

        # create an event for when the player starts to play
        is_playing, callback_is_playing = self.get_event_and_callback()
        self.vlc_player.set_vlc_callback(
            EventType.MediaPlayerPlaying, callback_is_playing
        )

        # start the playlist entry
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
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

            # call the method to resume the player
            self.vlc_player.set_pause(False)

            # assert the effect on logs

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

        # assert the effect on logs
        self.assertListEqual(
            logger.output,
            [
                "INFO:dakara_player_vlc.vlc_player:Playing transition for '{}'".format(
                    self.song_file_path
                ),
                "DEBUG:dakara_player_vlc.vlc_player:Song end callback called",
                "INFO:dakara_player_vlc.vlc_player:Now playing '{}'".format(
                    self.song_file_path
                ),
                "INFO:dakara_player_vlc.vlc_player:Setting pause",
                "DEBUG:dakara_player_vlc.vlc_player:Set pause",
                "INFO:dakara_player_vlc.vlc_player:Resuming play",
                "DEBUG:dakara_player_vlc.vlc_player:Resumed play",
                "INFO:dakara_player_vlc.vlc_player:Stopping player",
                "DEBUG:dakara_player_vlc.vlc_player:Stopped player",
            ],
        )

    def test_set_double_pause(self):
        """Test that double pause and double resume have no effects
        """
        # mock the text generator
        self.text_generator.create_transition_text.return_value = self.subtitle_path

        # mock the callbacks
        self.vlc_player.set_callback("paused", MagicMock())
        self.vlc_player.set_callback("resumed", MagicMock())

        # create an event for when the player starts to play
        is_playing, callback_is_playing = self.get_event_and_callback()
        self.vlc_player.set_vlc_callback(
            EventType.MediaPlayerPlaying, callback_is_playing
        )

        # start the playlist entry
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG") as logger:
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

            # assert the call
            self.assertTrue(self.vlc_player.is_paused())

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_called_with(ANY, ANY)
            self.vlc_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            self.vlc_player.callbacks["paused"].reset_mock()
            self.vlc_player.callbacks["resumed"].reset_mock()

            # re-call the method to pause the player
            self.vlc_player.set_pause(True)

            # assert the call
            self.assertTrue(self.vlc_player.is_paused())

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_not_called()
            self.vlc_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            self.vlc_player.callbacks["paused"].reset_mock()
            self.vlc_player.callbacks["resumed"].reset_mock()

            # call the method to resume the player
            self.vlc_player.set_pause(False)

            # assert the call
            self.assertFalse(self.vlc_player.is_paused())

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_not_called()
            self.vlc_player.callbacks["resumed"].assert_called_with(ANY, ANY)

            # reset the mocks
            self.vlc_player.callbacks["paused"].reset_mock()
            self.vlc_player.callbacks["resumed"].reset_mock()

            # re-call the method to resume the player
            self.vlc_player.set_pause(False)

            # assert the call
            self.assertFalse(self.vlc_player.is_paused())

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_not_called()
            self.vlc_player.callbacks["resumed"].assert_not_called()

            # close the player
            self.vlc_player.stop_player()

        # assert the effects on logs
        self.assertListEqual(
            logger.output,
            [
                "INFO:dakara_player_vlc.vlc_player:Playing transition for '{}'".format(
                    self.song_file_path
                ),
                "DEBUG:dakara_player_vlc.vlc_player:Song end callback called",
                "INFO:dakara_player_vlc.vlc_player:Now playing '{}'".format(
                    self.song_file_path
                ),
                "INFO:dakara_player_vlc.vlc_player:Setting pause",
                "DEBUG:dakara_player_vlc.vlc_player:Set pause",
                "DEBUG:dakara_player_vlc.vlc_player:Player already in pause",
                "INFO:dakara_player_vlc.vlc_player:Resuming play",
                "DEBUG:dakara_player_vlc.vlc_player:Resumed play",
                "DEBUG:dakara_player_vlc.vlc_player:Player already playing",
                "INFO:dakara_player_vlc.vlc_player:Stopping player",
                "DEBUG:dakara_player_vlc.vlc_player:Stopped player",
            ],
        )


@patch("dakara_player_vlc.vlc_player.PATH_BACKGROUNDS", "bg")
@patch("dakara_player_vlc.vlc_player.BackgroundLoader")
class VlcPlayerCustomBackgroundsTestCase(TestCase):
    """Test the VLC player class with custom backgrounds
    """

    def setUp(self):
        # create a mock text generator
        self.text_generator = MagicMock()

        # create stop event
        self.stop = Event()

        # create errors queue
        self.errors = Queue()

    def test_default_backgrounds(self, mocked_background_loader_class):
        """Test to instanciate with default backgrounds
        """
        # create object
        VlcPlayer(self.stop, self.errors, {}, self.text_generator)

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

    def test_custom_backgrounds(self, mocked_background_loader_class):
        """Test to instanciate with an existing backgrounds directory
        """
        # create object
        VlcPlayer(
            self.stop,
            self.errors,
            {
                "backgrounds": {
                    "directory": Path("custom/bg").normpath(),
                    "transition_background_name": "custom_transition.png",
                    "idle_background_name": "custom_idle.png",
                }
            },
            self.text_generator,
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


@patch("dakara_player_vlc.vlc_player.TRANSITION_DURATION", 10)
@patch("dakara_player_vlc.vlc_player.IDLE_DURATION", 20)
class VlcPlayerCustomDurationsTestCase(TestCase):
    """Test the VLC player class with custom durations
    """

    def setUp(self):
        # create a mock text generator
        self.text_generator = MagicMock()

        # create stop event
        self.stop = Event()

        # create errors queue
        self.errors = Queue()

    def test_default_durations(self):
        """Test to instanciate with default durations
        """
        # create object
        vlc_player = VlcPlayer(self.stop, self.errors, {}, self.text_generator)

        # assert the instance
        self.assertDictEqual(vlc_player.durations, {"transition": 10, "idle": 20})

    def test_customs(self):
        """Test to instanciate with custom durations
        """
        # create object
        vlc_player = VlcPlayer(
            self.stop,
            self.errors,
            {"durations": {"transition_duration": 5}},
            self.text_generator,
        )

        # assert the instance
        self.assertDictEqual(vlc_player.durations, {"transition": 5, "idle": 20})
