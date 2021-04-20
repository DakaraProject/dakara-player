from contextlib import ExitStack, contextmanager
from queue import Queue
from time import sleep
from threading import Event
from unittest.mock import ANY, MagicMock

from func_timeout import func_set_timeout
from path import Path, TempDir

try:
    from importlib.resources import path

except ImportError:
    from importlib_resources import path

from dakara_player.media_player.mpv import MediaPlayerMpv
from dakara_player.media_player.base import (
    IDLE_BG_NAME,
    IDLE_TEXT_NAME,
    TRANSITION_BG_NAME,
    TRANSITION_TEXT_NAME,
)
from tests.integration.base import TestCasePoller


class MediaPlayerMpvIntegrationTestCase(TestCasePoller):
    """Test the mpv player class in real conditions
    """

    TIMEOUT = 30
    DELAY = 0.2

    def setUp(self):
        # create fullscreen flag
        self.fullscreen = True

        # create kara folder
        self.kara_folder = TempDir()

        # create transition duration
        self.transition_duration = 1

        # create subtitle
        with path("tests.resources", "song1.ass") as file:
            self.subtitle1_path = Path(file).copy(self.kara_folder)

        with path("tests.resources", "song2.ass") as file:
            self.subtitle2_path = Path(file).copy(self.kara_folder)

        # create song
        with path("tests.resources", "song1.mkv") as file:
            self.song1_path = Path(file).copy(self.kara_folder)

        with path("tests.resources", "song2.mkv") as file:
            self.song2_path = Path(file).copy(self.kara_folder)

        # create audio
        with path("tests.resources", "song2.mp3") as file:
            self.audio2_file_path = Path(file).copy(self.kara_folder)

        # create playlist entry
        self.playlist_entry = {
            "id": 42,
            "song": {"title": "Song 1", "file_path": self.song1_path},
            "owner": "me",
            "use_instrumental": False,
        }

        self.playlist_entry2 = {
            "id": 43,
            "song": {"title": "Song 2", "file_path": self.song2_path},
            "owner": "me",
            "use_instrumental": False,
        }

    def tearDown(self):
        self.kara_folder.rmtree(ignore_errors=True)

    @contextmanager
    def get_instance(self, config=None):
        """Get an instance of MediaPlayerMpv

        This method is a context manager that automatically stops the player on
        exit.

        Args:
            config (dict): Configuration passed to the constructor.

        Yields:
            tuple: Containing the following elements:
                MediaPlayerMpv: Instance;
                path.Path: Path of the temporary directory;
                unittest.case._LoggingWatcher: Captured output.
                """
        if not config:
            config = {
                "kara_folder": self.kara_folder,
                "fullscreen": self.fullscreen,
                "mpv": {"vo": "null", "ao": "null"},
            }

        with TempDir() as temp:
            try:
                with ExitStack() as stack:
                    mpv_player = stack.enter_context(
                        MediaPlayerMpv(Event(), Queue(), config, temp, warn_long_exit=False)
                    )
                    output = stack.enter_context(
                        self.assertLogs("dakara_player.media_player.mpv", "DEBUG")
                    )
                    mpv_player.load()

                    yield mpv_player, temp, output
                    
            except OSError:
                # silence closing errors of mpv
                pass

            # sleep to allow slow systems to correctly clean up
            sleep(self.DELAY)

    @func_set_timeout(TIMEOUT)
    def test_play_idle(self):
        """Test to display the idle screen
        """
        with self.get_instance() as (mpv_player, temp, _):
            # pre assertions
            self.assertIsNone(mpv_player.player.path)

            # call the method
            mpv_player.play("idle")

            # wait for the idle screen to start
            self.wait_is_playing(mpv_player, "idle")

            # post assertions
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, temp / IDLE_BG_NAME)
            self.assertListEqual(mpv_player.player.sub_files, [temp / IDLE_TEXT_NAME])

    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry(self):
        """Test to play a playlist entry

        First, the transition screen is played, then the song itself.
        """
        with self.get_instance() as (mpv_player, temp, _):
            # mock the callbacks
            mpv_player.set_callback("started_transition", MagicMock())
            mpv_player.set_callback("started_song", MagicMock())

            # pre assertions
            self.assertIsNone(mpv_player.playlist_entry)
            self.assertIsNone(mpv_player.player.path)

            # set playlist entry
            mpv_player.set_playlist_entry(self.playlist_entry, autoplay=False)

            # check memory
            self.assertEqual(
                mpv_player.playlist_entry_data["transition"].path,
                temp / TRANSITION_BG_NAME,
            )
            self.assertEqual(
                mpv_player.playlist_entry_data["song"].path, self.song1_path
            )
            self.assertEqual(
                mpv_player.playlist_entry_data["song"].path_subtitle,
                self.subtitle1_path,
            )

            # start playing
            mpv_player.play("transition")

            # wait for the transition screen to start
            self.wait_is_playing(mpv_player, "transition")

            # post assertions for transition screen
            self.assertIsNotNone(mpv_player.playlist_entry)

            # check media
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, temp / TRANSITION_BG_NAME)

            # check there is no audio track
            self.assertFalse(mpv_player.player.audio)

            # check which subtitle file is read
            self.assertListEqual(
                mpv_player.player.sub_files, [temp / TRANSITION_TEXT_NAME]
            )

            # assert the started transition callback has been called
            mpv_player.callbacks["started_transition"].assert_called_with(
                self.playlist_entry["id"]
            )

            # wait for the media to start
            self.wait_is_playing(mpv_player, "song")

            # check media
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, self.song1_path)

            # check audio track
            self.assertEqual(mpv_player.player.audio, 1)

            # assert the started song callback has been called
            mpv_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry["id"]
            )

    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry_instrumental_track(self):
        """Test to play a playlist entry using instrumental track
        """
        # request to use instrumental track
        self.playlist_entry["use_instrumental"] = True

        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("started_transition", MagicMock())
            mpv_player.set_callback("started_song", MagicMock())

            # pre assertions
            self.assertIsNone(mpv_player.playlist_entry)
            self.assertIsNone(mpv_player.player.path)

            # call the method
            mpv_player.set_playlist_entry(self.playlist_entry)

            # wait for the song to start
            self.wait_is_playing(mpv_player, "song")

            # check the current media has 2 audio tracks
            self.assertListEqual(mpv_player.get_audio_tracks_id(), [1, 2])

            # check media exists
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, self.song1_path)

            # check audio track
            self.assertEqual(mpv_player.player.audio, 2)

            # assert the started song callback has been called
            mpv_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry["id"]
            )

    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry_instrumental_file(self):
        """Test to play a playlist entry using instrumental file
        """
        # request to use instrumental file
        self.playlist_entry["song"]["file_path"] = self.song2_path
        self.playlist_entry["use_instrumental"] = True

        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("started_transition", MagicMock())
            mpv_player.set_callback("started_song", MagicMock())

            # pre assertions
            self.assertIsNone(mpv_player.playlist_entry)
            self.assertIsNone(mpv_player.player.path)

            # call the method
            mpv_player.set_playlist_entry(self.playlist_entry)

            # wait for the song to start
            self.wait_is_playing(mpv_player, "song")

            # check media exists
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, self.song2_path)

            # check audio track
            self.assertEqual(mpv_player.player.audio, 3)

            # assert the started song callback has been called
            mpv_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry["id"]
            )

    @func_set_timeout(TIMEOUT)
    def test_pause(self):
        """Test to pause and unpause the player
        """
        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("paused", MagicMock())
            mpv_player.set_callback("resumed", MagicMock())

            # start the playlist entry
            mpv_player.set_playlist_entry(self.playlist_entry)

            # wait for the song to start
            self.wait_is_playing(mpv_player, "song")

            # call the method to pause the player
            mpv_player.pause(True)
            timing = mpv_player.get_timing()

            # wait for the player to be paused
            self.wait_is_paused(mpv_player)

            # assert the callback
            mpv_player.callbacks["paused"].assert_called_with(
                self.playlist_entry["id"], timing
            )
            mpv_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            mpv_player.callbacks["resumed"].assert_not_called()
            mpv_player.callbacks["paused"].reset_mock()
            mpv_player.callbacks["resumed"].reset_mock()

            # call the method to resume the player
            mpv_player.pause(False)

            # wait for the player to play again
            self.wait_is_playing(mpv_player)

            # assert the callback
            mpv_player.callbacks["paused"].assert_not_called()
            mpv_player.callbacks["resumed"].assert_called_with(
                self.playlist_entry["id"],
                timing,  # on a slow computer, the timing may be inaccurate
            )

    @func_set_timeout(TIMEOUT)
    def test_double_pause(self):
        """Test that double pause and double resume have no effects
        """
        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("paused", MagicMock())
            mpv_player.set_callback("resumed", MagicMock())

            # start the playlist entry
            mpv_player.set_playlist_entry(self.playlist_entry)

            # wait for the song to start
            self.wait_is_playing(mpv_player, "song")

            # call the method to pause the player
            mpv_player.pause(True)

            # wait for the player to be paused
            self.wait_is_paused(mpv_player)

            # assert the callback
            mpv_player.callbacks["paused"].assert_called_with(ANY, ANY)
            mpv_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            mpv_player.callbacks["paused"].reset_mock()
            mpv_player.callbacks["resumed"].reset_mock()

            # re-call the method to pause the player
            mpv_player.pause(True)
            self.wait_is_paused(mpv_player)

            # assert the callback
            mpv_player.callbacks["paused"].assert_not_called()
            mpv_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            mpv_player.callbacks["paused"].reset_mock()
            mpv_player.callbacks["resumed"].reset_mock()

            # call the method to resume the player
            mpv_player.pause(False)

            # wait for the player to play again
            self.wait_is_playing(mpv_player)

            # assert the callback
            mpv_player.callbacks["paused"].assert_not_called()
            mpv_player.callbacks["resumed"].assert_called_with(ANY, ANY)

            # reset the mocks
            mpv_player.callbacks["paused"].reset_mock()
            mpv_player.callbacks["resumed"].reset_mock()

            # re-call the method to resume the player
            mpv_player.pause(False)
            self.wait_is_playing(mpv_player)

            # assert the callback
            mpv_player.callbacks["paused"].assert_not_called()
            mpv_player.callbacks["resumed"].assert_not_called()

    @func_set_timeout(TIMEOUT)
    def test_skip_song(self):
        """Test to skip a playlist entry
        """
        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("started_transition", MagicMock())
            mpv_player.set_callback("started_song", MagicMock())
            mpv_player.set_callback("finished", MagicMock())

            # pre assertions
            self.assertIsNone(mpv_player.playlist_entry)
            self.assertIsNone(mpv_player.player.path)

            # request initial playlist entry to play
            mpv_player.set_playlist_entry(self.playlist_entry)

            # wait for the media to start
            self.wait_is_playing(mpv_player, "song")

            # post assertions for song
            self.assertIsNotNone(mpv_player.playlist_entry)

            # check media
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, self.song1_path)

            # request first playlist entry to stop
            mpv_player.skip()

            # check the song is stopped accordingly
            self.assertIsNone(mpv_player.playlist_entry)
            mpv_player.callbacks["finished"].assert_called_with(
                self.playlist_entry["id"]
            )

            # request second playlist entry to play
            mpv_player.set_playlist_entry(self.playlist_entry2)

            # wait for the media to start
            self.wait_is_playing(mpv_player, "song")

            # post assertions for song
            self.assertIsNotNone(mpv_player.playlist_entry)

            # check media
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, self.song2_path)

    @func_set_timeout(TIMEOUT)
    def test_skip_transition(self):
        """Test to skip a playlist entry transition screen
        """
        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("started_transition", MagicMock())
            mpv_player.set_callback("started_song", MagicMock())
            mpv_player.set_callback("finished", MagicMock())

            # pre assertions
            self.assertIsNone(mpv_player.playlist_entry)
            self.assertIsNone(mpv_player.player.path)

            # request initial playlist entry to play
            mpv_player.set_playlist_entry(self.playlist_entry)

            # wait for the transition to start
            self.wait_is_playing(mpv_player, "transition")

            # request first playlist entry to stop
            mpv_player.skip()

            # check the song is stopped accordingly
            mpv_player.callbacks["finished"].assert_called_with(
                self.playlist_entry["id"]
            )

            # request second playlist entry to play
            mpv_player.set_playlist_entry(self.playlist_entry2)

            # wait for the media to start
            self.wait_is_playing(mpv_player, "song")

            # check media
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, self.song2_path)

    @func_set_timeout(TIMEOUT)
    def test_skip_idle(self):
        """Test to play a playlist entry after idle screen
        """
        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("started_transition", MagicMock())
            mpv_player.set_callback("started_song", MagicMock())
            mpv_player.set_callback("finished", MagicMock())

            # pre assertions
            self.assertIsNone(mpv_player.playlist_entry)
            self.assertIsNone(mpv_player.player.path)

            # request idle screen
            mpv_player.play("idle")

            # wait for the media to start
            self.wait_is_playing(mpv_player, "idle")

            # post assertions for song
            self.assertIsNone(mpv_player.playlist_entry)

            # request second playlist entry to play
            mpv_player.set_playlist_entry(self.playlist_entry)

            # wait for the media to start
            self.wait_is_playing(mpv_player, "song")

            # post assertions for song
            self.assertIsNotNone(mpv_player.playlist_entry)

            # check media
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, self.song1_path)
