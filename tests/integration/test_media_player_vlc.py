from contextlib import ExitStack, contextmanager
from queue import Queue
from threading import Event
from unittest import skipIf, skipUnless
from unittest.mock import MagicMock

try:
    import vlc

except (ImportError, OSError):
    vlc = None

from func_timeout import func_set_timeout
from path import TempDir

from dakara_player.media_player.base import IDLE_BG_NAME, TRANSITION_BG_NAME
from dakara_player.media_player.vlc import METADATA_KEYS_COUNT, MediaPlayerVlc
from dakara_player.mrl import mrl_to_path
from tests.integration.base import TestCasePollerKara

REWIND_FAST_FORWARD_DURATION = 0.5


@skipUnless(MediaPlayerVlc.is_available(), "VLC not installed")
class MediaPlayerVlcIntegrationTestCase(TestCasePollerKara):
    """Test the VLC player class in real conditions."""

    TIMEOUT = 120

    def setUp(self):
        super().setUp()

        # create instance parameter
        self.instance_parameters = [
            "--vout=vdummy",
            "--aout=adummy",
            "--text-renderer=tdummy",
        ]

        # use default window
        self.use_default_window = True

        # create fullscreen flag
        self.fullscreen = True

        # create media parameter
        self.media_parameters = []

        # create transition duration
        self.transition_duration = 1

    @contextmanager
    def get_instance(self, config=None, check_error=True):
        """Get an instance of MediaPlayerVlc.

        This method is a context manager that automatically stops the player on
        exit.

        Args:
            config (dict): Extra configuration passed to the constructor.
            check_error (bool): If true, check if the player stop event is not
                set and the error queue is empty at the end.

        Yields:
            tuple: Containing the following elements:
                MediaPlayerVlc: Instance;
                path.Path: Path of the temporary directory;
                unittest.case._LoggingWatcher: Captured output.
        """

        config_full = {
            "kara_folder": self.kara_folder,
            "fullscreen": self.fullscreen,
            "vlc": {
                "instance_parameters": self.instance_parameters,
                "media_parameters": self.media_parameters,
                "use_default_window": self.use_default_window,
            },
        }

        if config:
            config_full.update(config)

        with ExitStack() as stack:
            temp = stack.enter_context(TempDir())
            vlc_player = stack.enter_context(
                MediaPlayerVlc(
                    Event(), Queue(), config_full, temp, warn_long_exit=False
                )
            )
            output = stack.enter_context(
                self.assertLogs("dakara_player.media_player.vlc", "DEBUG")
            )
            vlc_player.load()

            yield vlc_player, temp, output

            if check_error:
                # display errors in queue if any
                if not vlc_player.errors.empty():
                    _, error, traceback = vlc_player.errors.get(5)
                    error.with_traceback(traceback)
                    raise error

                # assert no errors to fail test if any
                self.assertFalse(vlc_player.stop.is_set())

    def test_metadata_keys_count(self):
        """Test the number of metadata keys."""
        self.assertNotEqual(METADATA_KEYS_COUNT, 0)

    @func_set_timeout(TIMEOUT)
    def test_start(self):
        """Test the initial state of the player without instructions."""
        with self.get_instance() as (vlc_player, _, _):
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertFalse(vlc_player.is_playing_this("idle"))
            self.assertFalse(vlc_player.is_playing_this("transition"))
            self.assertFalse(vlc_player.is_playing_this("song"))

    @func_set_timeout(TIMEOUT)
    def test_play_idle(self):
        """Test to display the idle screen."""
        with self.get_instance() as (vlc_player, temp, _):
            # pre assertions
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # call the method
            vlc_player.play("idle")

            # wait for the idle screen to start
            self.wait_is_playing(vlc_player, "idle")

            # post assertions
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)

            self.assertIsNotNone(vlc_player.player.get_media())
            media = vlc_player.player.get_media()
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, temp / IDLE_BG_NAME)

            # TODO check which subtitle file is read
            # seems impossible to do for now

    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry(self):
        """Test to play a playlist entry.

        First, the transition screen is played, then the song itself.
        """
        with self.get_instance() as (vlc_player, temp, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # call the method
            vlc_player.set_playlist_entry(self.playlist_entry1, autoplay=False)

            # check media did not started
            self.assertFalse(vlc_player.playlist_entry_data["transition"].started)
            self.assertFalse(vlc_player.playlist_entry_data["song"].started)

            # start playing
            vlc_player.play("transition")

            # wait for the transition screen to start
            self.wait_is_playing(vlc_player, "transition")

            # post assertions for transition screen
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)
            self.assertIsNotNone(vlc_player.playlist_entry)

            # check transition media only started
            self.assertTrue(vlc_player.playlist_entry_data["transition"].started)
            self.assertFalse(vlc_player.playlist_entry_data["song"].started)

            # check media exists
            media = vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, temp / TRANSITION_BG_NAME)

            # check there is no audio track
            track = vlc_player.player.audio_get_track()
            self.assertEqual(track, -1)

            # TODO check which subtitle file is read
            # seems impossible to do for now

            # assert the started transition callback has been called
            vlc_player.callbacks["started_transition"].assert_called_with(
                self.playlist_entry1["id"]
            )

            # wait for the media to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)

            # check song media also started
            self.assertTrue(vlc_player.playlist_entry_data["transition"].started)
            self.assertTrue(vlc_player.playlist_entry_data["song"].started)

            # check media exists
            media = vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song1_path)

            # check audio track
            track = vlc_player.player.audio_get_track()
            self.assertEqual(track, 1)

            # assert the started song callback has been called
            vlc_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry1["id"]
            )

            # assert the player is playing a song
            self.assertFalse(vlc_player.is_playing_this("transition"))
            self.assertTrue(vlc_player.is_playing_this("song"))
            self.assertFalse(vlc_player.is_playing_this("idle"))

            # wait for the media to end
            self.wait(lambda: not vlc_player.is_playing())

            # assert the player is not playing anything
            self.assertFalse(vlc_player.is_playing_this("transition"))
            self.assertFalse(vlc_player.is_playing_this("song"))
            self.assertFalse(vlc_player.is_playing_this("idle"))

    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry_instrumental_track(self):
        """Test to play a playlist entry using instrumental track."""
        # request to use instrumental track
        self.playlist_entry1["use_instrumental"] = True

        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # call the method
            vlc_player.set_playlist_entry(self.playlist_entry1)

            # wait for the song to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)

            # check media exists
            media = vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song1_path)

            # check audio track
            track = vlc_player.player.audio_get_track()
            self.assertEqual(track, 2)

            # assert the started song callback has been called
            vlc_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry1["id"]
            )

    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry_instrumental_track_avi(self):
        """Test to play a playlist entry AVI file using instrumental track.

        This type of file is known to have data in the key we use to store
        information in media.
        """
        # request to use instrumental track
        self.playlist_entry3["use_instrumental"] = True

        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # call the method
            vlc_player.set_playlist_entry(self.playlist_entry3)

            # wait for the song to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)

            # check media exists
            media = vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song3_path)

            # check audio track
            track = vlc_player.player.audio_get_track()
            self.assertEqual(track, 2)

            # assert the started song callback has been called
            vlc_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry3["id"]
            )

    @skipIf(
        not hasattr(vlc, "libvlc_media_slaves_add"), "VLC does not support slaves_add"
    )
    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry_instrumental_file(self):
        """Test to play a playlist entry using instrumental file."""
        # request to use instrumental file
        self.playlist_entry1["song"]["file_path"] = self.song2_path
        self.playlist_entry1["use_instrumental"] = True

        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # call the method
            vlc_player.set_playlist_entry(self.playlist_entry1)

            # wait for the song to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)

            # check media exists
            media = vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song2_path)

            # check audio track
            track = vlc_player.player.audio_get_track()
            self.assertEqual(track, 4)

            # assert the started song callback has been called
            vlc_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry1["id"]
            )

    @func_set_timeout(TIMEOUT)
    def test_pause(self):
        """Test to pause and resume the player."""
        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("paused", MagicMock())
            vlc_player.set_callback("resumed", MagicMock())

            # start the playlist entry
            vlc_player.set_playlist_entry(self.playlist_entry1)

            # wait for the song to start
            self.wait_is_playing(vlc_player, "song")

            # call the method to pause the player
            vlc_player.pause()
            timing = vlc_player.get_timing()

            # wait for the player to be paused
            self.wait_is_paused(vlc_player)

            # assert in pause
            self.assertFalse(vlc_player.is_playing())

            # assert the callback
            vlc_player.callbacks["paused"].assert_called_with(
                self.playlist_entry1["id"], timing
            )
            vlc_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            vlc_player.callbacks["paused"].reset_mock()
            vlc_player.callbacks["resumed"].reset_mock()

            # call the method to resume the player
            vlc_player.resume()

            # wait for the player to play again
            self.wait_is_playing(vlc_player)

            # assert the callback
            vlc_player.callbacks["paused"].assert_not_called()
            vlc_player.callbacks["resumed"].assert_called_with(
                self.playlist_entry1["id"],
                timing,  # on a slow computer, the timing may be inaccurate
            )

    @func_set_timeout(TIMEOUT)
    def test_double_pause(self):
        """Test that double pause and double resume have no effects."""
        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("paused", MagicMock())
            vlc_player.set_callback("resumed", MagicMock())

            # start the playlist entry
            vlc_player.set_playlist_entry(self.playlist_entry1)

            # wait for the song to start
            self.wait_is_playing(vlc_player, "song")

            # call the method to pause the player
            vlc_player.pause()

            # wait for the player to be paused
            self.wait_is_paused(vlc_player)

            # assert the callback
            vlc_player.callbacks["paused"].assert_called()
            vlc_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            vlc_player.callbacks["paused"].reset_mock()
            vlc_player.callbacks["resumed"].reset_mock()

            # re-call the method to pause the player
            vlc_player.pause()

            # wait again for the player to be paused
            self.wait_is_paused(vlc_player)

            # assert the callback
            vlc_player.callbacks["paused"].assert_not_called()
            vlc_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            vlc_player.callbacks["paused"].reset_mock()
            vlc_player.callbacks["resumed"].reset_mock()

            # call the method to resume the player
            vlc_player.resume()

            # wait for the player to play again
            self.wait_is_playing(vlc_player)

            # assert the callback
            vlc_player.callbacks["paused"].assert_not_called()
            vlc_player.callbacks["resumed"].assert_called()

            # reset the mocks
            vlc_player.callbacks["paused"].reset_mock()
            vlc_player.callbacks["resumed"].reset_mock()

            # re-call the method to resume the player
            vlc_player.resume()
            self.wait_is_playing(vlc_player)

            # assert the callback
            vlc_player.callbacks["paused"].assert_not_called()
            vlc_player.callbacks["resumed"].assert_not_called()

    @func_set_timeout(TIMEOUT)
    def test_restart_song(self):
        """Test to restart a playlist entry."""
        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())
            vlc_player.set_callback("finished", MagicMock())
            vlc_player.set_callback("updated_timing", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # request playlist entry to play
            vlc_player.set_playlist_entry(self.playlist_entry1)

            # wait for the media to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)
            self.assertIsNotNone(vlc_player.playlist_entry)

            # wait a bit for the player to play
            self.wait(
                lambda: vlc_player.player.get_time()
                >= REWIND_FAST_FORWARD_DURATION * 1000
            )

            # request to restart media
            vlc_player.restart()

            # check timing is 0
            self.assertAlmostEqual(vlc_player.player.get_time(), 0, 0)

            # check the song is not stopped
            self.assertIsNotNone(vlc_player.playlist_entry)
            vlc_player.callbacks["finished"].assert_not_called()

            # assert callback
            vlc_player.callbacks["updated_timing"].assert_called_with(
                self.playlist_entry1["id"], 0
            )

    @func_set_timeout(TIMEOUT)
    def test_skip_song(self):
        """Test to skip a playlist entry."""
        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())
            vlc_player.set_callback("finished", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # request initial playlist entry to play
            vlc_player.set_playlist_entry(self.playlist_entry1)

            # wait for the media to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)
            self.assertIsNotNone(vlc_player.playlist_entry)

            # check media exists
            media = vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song1_path)

            # request first playlist entry to stop
            vlc_player.skip()

            # check the song is stopped accordingly
            self.assertIsNone(vlc_player.playlist_entry)
            vlc_player.callbacks["finished"].assert_called_with(
                self.playlist_entry1["id"]
            )

            # request second playlist entry to play
            vlc_player.set_playlist_entry(self.playlist_entry2)

            # wait for the media to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)
            self.assertIsNotNone(vlc_player.playlist_entry)

            # check media exists
            media = vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song2_path)

    @func_set_timeout(TIMEOUT)
    def test_skip_transition(self):
        """Test to skip a playlist entry transition screen."""
        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())
            vlc_player.set_callback("finished", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # request initial playlist entry to play
            vlc_player.set_playlist_entry(self.playlist_entry1)

            # wait for the transition to start
            self.wait_is_playing(vlc_player, "transition")

            # request first playlist entry to stop
            vlc_player.skip()

            # check the song is stopped accordingly
            vlc_player.callbacks["finished"].assert_called_with(
                self.playlist_entry1["id"]
            )

            # request second playlist entry to play
            vlc_player.set_playlist_entry(self.playlist_entry2)

            # wait for the media to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)

            # check media exists
            media = vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song2_path)

    @func_set_timeout(TIMEOUT)
    def test_rewind_song(self):
        """Test to rewind a playlist entry."""
        with self.get_instance(
            {
                "durations": {
                    "rewind_fast_forward_duration": REWIND_FAST_FORWARD_DURATION
                }
            }
        ) as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())
            vlc_player.set_callback("updated_timing", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # request playlist entry to play
            vlc_player.set_playlist_entry(self.playlist_entry1)

            # wait for the media to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)
            self.assertIsNotNone(vlc_player.playlist_entry)

            # wait a bit for the player to play
            self.wait(
                lambda: vlc_player.player.get_time()
                >= REWIND_FAST_FORWARD_DURATION * 2 * 1000
            )
            timing1 = vlc_player.player.get_time() / 1000

            # request playlist entry to rewind
            vlc_player.rewind()

            # check timing is earlier than previously
            timing2 = vlc_player.player.get_time() / 1000
            self.assertLess(timing2, timing1)
            self.assertAlmostEqual(timing1 - timing2, REWIND_FAST_FORWARD_DURATION, 1)

    @func_set_timeout(TIMEOUT)
    def test_rewind_song_before_start(self):
        """Test to rewind a playlist entry before its start."""
        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # request playlist entry to play
            vlc_player.set_playlist_entry(self.playlist_entry1)

            # wait for the media to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)
            self.assertIsNotNone(vlc_player.playlist_entry)

            # request playlist entry to rewind
            vlc_player.rewind()

            # check timing is 0
            self.assertAlmostEqual(vlc_player.player.get_time(), 0, 0)

    @func_set_timeout(TIMEOUT)
    def test_fast_forward_song(self):
        """Test to advance a playlist entry."""
        with self.get_instance(
            {
                "durations": {
                    "rewind_fast_forward_duration": REWIND_FAST_FORWARD_DURATION
                }
            }
        ) as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())
            vlc_player.set_callback("updated_timing", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # request playlist entry to play
            vlc_player.set_playlist_entry(self.playlist_entry1)

            # wait for the media to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)
            self.assertIsNotNone(vlc_player.playlist_entry)

            # wait a bit for the player to play
            self.wait(
                lambda: vlc_player.player.get_time()
                >= REWIND_FAST_FORWARD_DURATION * 2 * 1000
            )
            timing1 = vlc_player.player.get_time() / 1000

            # request playlist entry to advance
            vlc_player.fast_forward()

            # check timing is earlier than previously
            timing2 = vlc_player.player.get_time() / 1000
            self.assertGreater(timing2, timing1)
            self.assertAlmostEqual(timing2 - timing1, REWIND_FAST_FORWARD_DURATION, 1)

            # assert callback
            vlc_player.callbacks["updated_timing"].assert_called_with(
                self.playlist_entry1["id"], int(timing2)
            )

    @func_set_timeout(TIMEOUT)
    def test_fast_forward_song_after_end(self):
        """Test to advance a playlist entry after its end."""
        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())
            vlc_player.set_callback("finished", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # request playlist entry to play
            vlc_player.set_playlist_entry(self.playlist_entry1)

            # wait for the media to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)
            self.assertIsNotNone(vlc_player.playlist_entry)

            # request playlist entry to advance
            vlc_player.fast_forward()

            # check the song has finished
            vlc_player.callbacks["finished"].assert_called_with(
                self.playlist_entry1["id"]
            )
