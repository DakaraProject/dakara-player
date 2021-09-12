from contextlib import ExitStack, contextmanager
from queue import Queue
from threading import Event
from time import sleep
from unittest import skipUnless
from unittest.mock import MagicMock

from func_timeout import func_set_timeout
from path import TempDir

from dakara_player.media_player.base import (
    IDLE_BG_NAME,
    IDLE_TEXT_NAME,
    TRANSITION_BG_NAME,
    TRANSITION_TEXT_NAME,
)
from dakara_player.media_player.mpv import MediaPlayerMpv
from tests.integration.base import TestCasePollerKara


@skipUnless(MediaPlayerMpv.is_available(), "mpv not installed")
class MediaPlayerMpvIntegrationTestCase(TestCasePollerKara):
    """Test the mpv player class in real conditions."""

    TIMEOUT = 30
    DELAY = 0.2

    def setUp(self):
        super().setUp()

        # create fullscreen flag
        self.fullscreen = True

        # create transition duration
        self.transition_duration = 1

    @contextmanager
    def get_instance(self, config=None, check_error=True):
        """Get an instance of MediaPlayerMpv for the available version.

        This method is a context manager that automatically stops the player on
        exit.

        Args:
            config (dict): Configuration passed to the constructor.
            check_error (bool): If true, check if the player stop event is not
                set and the error queue is empty at the end.

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
                        MediaPlayerMpv.from_version(
                            Event(), Queue(), config, temp, warn_long_exit=False
                        )
                    )
                    output = stack.enter_context(
                        self.assertLogs("dakara_player.media_player.mpv", "DEBUG")
                    )
                    mpv_player.load()

                    yield mpv_player, temp, output

                    if check_error:
                        # display errors in queue if any
                        if not mpv_player.errors.empty():
                            _, error, traceback = mpv_player.errors.get(5)
                            error.with_traceback(traceback)
                            raise error

                        # assert no errors to fail test if any
                        self.assertFalse(mpv_player.stop.is_set())

            except OSError:
                # silence closing errors of mpv
                pass

            # sleep to allow slow systems to correctly clean up
            sleep(self.DELAY)

    @func_set_timeout(TIMEOUT)
    def test_play_idle(self):
        """Test to display the idle screen."""
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
        """Test to play a playlist entry.

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
            mpv_player.set_playlist_entry(self.playlist_entry1, autoplay=False)

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
                self.playlist_entry1["id"]
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
                self.playlist_entry1["id"]
            )

    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry_instrumental_track(self):
        """Test to play a playlist entry using instrumental track."""
        # request to use instrumental track
        self.playlist_entry1["use_instrumental"] = True

        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("started_transition", MagicMock())
            mpv_player.set_callback("started_song", MagicMock())

            # pre assertions
            self.assertIsNone(mpv_player.playlist_entry)
            self.assertIsNone(mpv_player.player.path)

            # call the method
            mpv_player.set_playlist_entry(self.playlist_entry1)

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
                self.playlist_entry1["id"]
            )

    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry_instrumental_file(self):
        """Test to play a playlist entry using instrumental file."""
        # request to use instrumental file
        self.playlist_entry1["song"]["file_path"] = self.song2_path
        self.playlist_entry1["use_instrumental"] = True

        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("started_transition", MagicMock())
            mpv_player.set_callback("started_song", MagicMock())

            # pre assertions
            self.assertIsNone(mpv_player.playlist_entry)
            self.assertIsNone(mpv_player.player.path)

            # call the method
            mpv_player.set_playlist_entry(self.playlist_entry1)

            # wait for the song to start
            self.wait_is_playing(mpv_player, "song")

            # check media exists
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, self.song2_path)

            # check audio track
            self.assertEqual(mpv_player.player.audio, 3)

            # assert the started song callback has been called
            mpv_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry1["id"]
            )

    @func_set_timeout(TIMEOUT)
    def test_pause(self):
        """Test to pause and unpause the player."""
        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("paused", MagicMock())
            mpv_player.set_callback("resumed", MagicMock())

            # start the playlist entry
            mpv_player.set_playlist_entry(self.playlist_entry1)

            # wait for the song to start
            self.wait_is_playing(mpv_player, "song")

            # call the method to pause the player
            mpv_player.pause(True)
            timing = mpv_player.get_timing()

            # wait for the player to be paused
            self.wait_is_paused(mpv_player)

            # assert in pause
            self.assertFalse(mpv_player.is_playing())

            # assert the callback
            mpv_player.callbacks["paused"].assert_called_with(
                self.playlist_entry1["id"], timing
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
                self.playlist_entry1["id"],
                timing,  # on a slow computer, the timing may be inaccurate
            )

    @func_set_timeout(TIMEOUT)
    def test_double_pause(self):
        """Test that double pause and double resume have no effects."""
        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("paused", MagicMock())
            mpv_player.set_callback("resumed", MagicMock())

            # start the playlist entry
            mpv_player.set_playlist_entry(self.playlist_entry1)

            # wait for the song to start
            self.wait_is_playing(mpv_player, "song")

            # call the method to pause the player
            mpv_player.pause(True)

            # wait for the player to be paused
            self.wait_is_paused(mpv_player)

            # assert the callback
            mpv_player.callbacks["paused"].assert_called()
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
            mpv_player.callbacks["resumed"].assert_called()

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
        """Test to skip a playlist entry."""
        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("started_transition", MagicMock())
            mpv_player.set_callback("started_song", MagicMock())
            mpv_player.set_callback("finished", MagicMock())

            # pre assertions
            self.assertIsNone(mpv_player.playlist_entry)
            self.assertIsNone(mpv_player.player.path)

            # request initial playlist entry to play
            mpv_player.set_playlist_entry(self.playlist_entry1)

            # wait for the media to start
            self.wait_is_playing(mpv_player, "song")

            # post assertions for song
            self.assertIsNotNone(mpv_player.playlist_entry)

            # check media
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, self.song1_path)

            # request first playlist entry to stop
            mpv_player.skip()

            # check skip flag
            self.assertTrue(mpv_player.player_data["skip"])

            # check the song is stopped accordingly
            self.assertIsNone(mpv_player.playlist_entry)
            mpv_player.callbacks["finished"].assert_called_with(
                self.playlist_entry1["id"]
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

            # check skip flag
            self.assertFalse(mpv_player.player_data["skip"])

    @func_set_timeout(TIMEOUT)
    def test_skip_last_song(self):
        """Test to skip the last playlist entry."""
        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("started_transition", MagicMock())
            mpv_player.set_callback("started_song", MagicMock())
            mpv_player.set_callback("finished", MagicMock())

            # pre assertions
            self.assertIsNone(mpv_player.playlist_entry)
            self.assertIsNone(mpv_player.player.path)

            # request initial playlist entry to play
            mpv_player.set_playlist_entry(self.playlist_entry1)

            # wait for the media to start
            self.wait_is_playing(mpv_player, "song")

            # post assertions for song
            self.assertIsNotNone(mpv_player.playlist_entry)

            # check media
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, self.song1_path)

            # request first playlist entry to stop
            mpv_player.skip()

            # check skip flag
            self.assertTrue(mpv_player.player_data["skip"])

            # check the song is stopped accordingly
            self.assertIsNone(mpv_player.playlist_entry)
            mpv_player.callbacks["finished"].assert_called_with(
                self.playlist_entry1["id"]
            )

            # request idle screen
            mpv_player.play("idle")

            # wait for the media to start
            self.wait_is_playing(mpv_player, "idle")

            # check skip flag
            self.assertFalse(mpv_player.player_data["skip"])

    @func_set_timeout(TIMEOUT)
    def test_skip_song_pause(self):
        """Test to skip playlist entry on pause."""
        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("started_transition", MagicMock())
            mpv_player.set_callback("started_song", MagicMock())
            mpv_player.set_callback("finished", MagicMock())
            mpv_player.set_callback("pause", MagicMock())
            mpv_player.set_callback("resumed", MagicMock())

            # pre assertions
            self.assertIsNone(mpv_player.playlist_entry)
            self.assertIsNone(mpv_player.player.path)

            # request initial playlist entry to play
            mpv_player.set_playlist_entry(self.playlist_entry1)

            # wait for the media to start
            self.wait_is_playing(mpv_player, "song")

            # post assertions for song
            self.assertIsNotNone(mpv_player.playlist_entry)

            # check media
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, self.song1_path)

            # pause song
            mpv_player.pause(True)

            # wait for the media to be paused
            self.wait_is_paused(mpv_player)

            # request first playlist entry to stop
            mpv_player.skip()

            # check skip flag
            self.assertTrue(mpv_player.player_data["skip"])

            # check the song is stopped accordingly
            self.assertIsNone(mpv_player.playlist_entry)
            mpv_player.callbacks["finished"].assert_called_with(
                self.playlist_entry1["id"]
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

            # check skip flag
            self.assertFalse(mpv_player.player_data["skip"])

            # check callbacks
            mpv_player.callbacks["resumed"].assert_not_called()

    @func_set_timeout(TIMEOUT)
    def test_skip_last_song_pause(self):
        """Test to skip the last playlist entry on pause."""
        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("started_transition", MagicMock())
            mpv_player.set_callback("started_song", MagicMock())
            mpv_player.set_callback("finished", MagicMock())
            mpv_player.set_callback("pause", MagicMock())
            mpv_player.set_callback("resumed", MagicMock())

            # pre assertions
            self.assertIsNone(mpv_player.playlist_entry)
            self.assertIsNone(mpv_player.player.path)

            # request initial playlist entry to play
            mpv_player.set_playlist_entry(self.playlist_entry1)

            # wait for the media to start
            self.wait_is_playing(mpv_player, "song")

            # post assertions for song
            self.assertIsNotNone(mpv_player.playlist_entry)

            # check media
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, self.song1_path)

            # pause song
            mpv_player.pause(True)

            # wait for the media to be paused
            self.wait_is_paused(mpv_player)

            # request first playlist entry to stop
            mpv_player.skip()

            # check the song is stopped accordingly
            self.assertIsNone(mpv_player.playlist_entry)
            mpv_player.callbacks["finished"].assert_called_with(
                self.playlist_entry1["id"]
            )

            # request idle screen
            mpv_player.play("idle")

            # wait for the media to start
            self.wait_is_playing(mpv_player, "idle")

            # check callbacks
            mpv_player.callbacks["resumed"].assert_not_called()

    @func_set_timeout(TIMEOUT)
    def test_skip_transition(self):
        """Test to skip a playlist entry transition screen."""
        with self.get_instance() as (mpv_player, _, _):
            # mock the callbacks
            mpv_player.set_callback("started_transition", MagicMock())
            mpv_player.set_callback("started_song", MagicMock())
            mpv_player.set_callback("finished", MagicMock())

            # pre assertions
            self.assertIsNone(mpv_player.playlist_entry)
            self.assertIsNone(mpv_player.player.path)

            # request initial playlist entry to play
            mpv_player.set_playlist_entry(self.playlist_entry1)

            # wait for the transition to start
            self.wait_is_playing(mpv_player, "transition")

            # request first playlist entry to stop
            mpv_player.skip()

            # check the song is stopped accordingly
            mpv_player.callbacks["finished"].assert_called_with(
                self.playlist_entry1["id"]
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
        """Test to play a playlist entry after idle screen."""
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

            # request playlist entry to play
            mpv_player.set_playlist_entry(self.playlist_entry1)

            # wait for the media to start
            self.wait_is_playing(mpv_player, "song")

            # post assertions for song
            self.assertIsNotNone(mpv_player.playlist_entry)

            # check media
            self.assertIsNotNone(mpv_player.player.path)
            self.assertEqual(mpv_player.player.path, self.song1_path)
