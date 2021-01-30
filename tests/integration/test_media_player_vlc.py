from contextlib import ExitStack, contextmanager
from queue import Queue
from tempfile import TemporaryDirectory
from threading import Event
from unittest import skipIf
from unittest.mock import ANY, MagicMock

import vlc
from dakara_base.resources_manager import get_file
from func_timeout import func_set_timeout
from path import Path

from dakara_player.media_player.vlc import MediaPlayerVlc
from dakara_player.mrl import mrl_to_path
from dakara_player.media_player.base import (
    IDLE_BG_NAME,
    TRANSITION_BG_NAME,
)
from dakara_player.resources_manager import get_background
from tests.integration.base import TestCasePoller


class MediaPlayerVlcIntegrationTestCase(TestCasePoller):
    """Test the VLC player class in real conditions
    """

    TIMEOUT = 30

    def setUp(self):
        # create instance parameter
        self.instance_parameters = [
            "--vout=vdummy",
            "--aout=adummy",
            "--text-renderer=tdummy",
        ]

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
        self.subtitle_path = get_file("tests.resources", "song.ass")

        # create song path
        self.song_file_path = get_file("tests.resources", "song.mkv")
        self.song2_file_path = get_file("tests.resources", "song2.mkv")

        # create playlist entry
        self.playlist_entry = {
            "id": 42,
            "song": {"title": "Song 1", "file_path": self.song_file_path},
            "owner": "me",
            "use_instrumental": False,
        }

        self.playlist_entry2 = {
            "id": 43,
            "song": {"title": "Song 2", "file_path": self.song2_file_path},
            "owner": "me",
            "use_instrumental": False,
        }

    @contextmanager
    def get_instance(self, config=None):
        """Get an instance of MediaPlayerVlc

        This method is a context manager that automatically stops the player on
        exit.

        Args:
            config (dict): Configuration passed to the constructor.

        Yields:
            tuple: Containing the following elements:
                MediaPlayerVlc: Instance;
                path.Path: Path of the temporary directory;
                unittest.case._LoggingWatcher: Captured output.
                """

        if not config:
            config = {
                "kara_folder": self.kara_folder,
                "fullscreen": self.fullscreen,
                "vlc": {
                    "instance_parameters": self.instance_parameters,
                    "media_parameters": self.media_parameters,
                },
            }

        with ExitStack() as stack:
            temp = Path(stack.enter_context(TemporaryDirectory()))
            vlc_player = stack.enter_context(
                MediaPlayerVlc(Event(), Queue(), config, temp, warn_long_exit=False)
            )
            output = stack.enter_context(
                self.assertLogs("dakara_player.media_player.vlc", "DEBUG")
            )
            vlc_player.load()

            yield vlc_player, temp, output

    @func_set_timeout(TIMEOUT)
    def test_play_idle(self):
        """Test to display the idle screen
        """
        with self.get_instance() as (vlc_player, _, _):
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
            self.assertEqual(file_path, self.idle_background_path)

            # TODO check which subtitle file is read
            # seems impossible to do for now

    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry(self):
        """Test to play a playlist entry

        First, the transition screen is played, then the song itself.
        """
        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # call the method
            vlc_player.set_playlist_entry(self.playlist_entry, autoplay=False)

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
            self.assertEqual(file_path, self.transition_background_path)

            # check there is no audio track
            track = vlc_player.player.audio_get_track()
            self.assertEqual(track, -1)

            # TODO check which subtitle file is read
            # seems impossible to do for now

            # assert the started transition callback has been called
            vlc_player.callbacks["started_transition"].assert_called_with(
                self.playlist_entry["id"]
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
            self.assertEqual(file_path, self.song_file_path)

            # check audio track
            track = vlc_player.player.audio_get_track()
            self.assertEqual(track, 1)

            # assert the started song callback has been called
            vlc_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry["id"]
            )

    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry_instrumental_track(self):
        """Test to play a playlist entry using instrumental track
        """
        # request to use instrumental track
        self.playlist_entry["use_instrumental"] = True

        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # call the method
            vlc_player.set_playlist_entry(self.playlist_entry)

            # wait for the song to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)

            # check media exists
            media = vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song_file_path)

            # check audio track
            track = vlc_player.player.audio_get_track()
            self.assertEqual(track, 2)

            # assert the started song callback has been called
            vlc_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry["id"]
            )

    @skipIf(
        not hasattr(vlc, "libvlc_media_slaves_add"), "VLC does not support slaves_add"
    )
    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry_instrumental_file(self):
        """Test to play a playlist entry using instrumental file
        """
        # request to use instrumental file
        self.playlist_entry["song"]["file_path"] = self.song2_file_path
        self.playlist_entry["use_instrumental"] = True

        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.set_callback("started_song", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)
            self.assertIsNone(vlc_player.player.get_media())
            self.assertEqual(vlc_player.player.get_state(), vlc.State.NothingSpecial)

            # call the method
            vlc_player.set_playlist_entry(self.playlist_entry)

            # wait for the song to start
            self.wait_is_playing(vlc_player, "song")

            # post assertions for song
            self.assertEqual(vlc_player.player.get_state(), vlc.State.Playing)

            # check media exists
            media = vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song2_file_path)

            # check audio track
            track = vlc_player.player.audio_get_track()
            self.assertEqual(track, 4)

            # assert the started song callback has been called
            vlc_player.callbacks["started_song"].assert_called_with(
                self.playlist_entry["id"]
            )

    @func_set_timeout(TIMEOUT)
    def test_pause(self):
        """Test to pause and unpause the player
        """
        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("paused", MagicMock())
            vlc_player.set_callback("resumed", MagicMock())

            # start the playlist entry
            vlc_player.set_playlist_entry(self.playlist_entry)

            # wait for the song to start
            self.wait_is_playing(vlc_player, "song")

            # call the method to pause the player
            vlc_player.pause(True)
            timing = vlc_player.get_timing()

            # wait for the player to be paused
            self.wait_is_paused(vlc_player)

            # assert the callback
            vlc_player.callbacks["paused"].assert_called_with(
                self.playlist_entry["id"], timing
            )
            vlc_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            vlc_player.callbacks["resumed"].assert_not_called()
            vlc_player.callbacks["paused"].reset_mock()
            vlc_player.callbacks["resumed"].reset_mock()

            # call the method to resume the player
            vlc_player.pause(False)

            # wait for the player to play again
            self.wait_is_playing(vlc_player)

            # assert the callback
            vlc_player.callbacks["paused"].assert_not_called()
            vlc_player.callbacks["resumed"].assert_called_with(
                self.playlist_entry["id"],
                timing,  # on a slow computer, the timing may be inaccurate
            )

    @func_set_timeout(TIMEOUT)
    def test_double_pause(self):
        """Test that double pause and double resume have no effects
        """
        with self.get_instance() as (vlc_player, _, _):
            # mock the callbacks
            vlc_player.set_callback("paused", MagicMock())
            vlc_player.set_callback("resumed", MagicMock())

            # start the playlist entry
            vlc_player.set_playlist_entry(self.playlist_entry)

            # wait for the song to start
            self.wait_is_playing(vlc_player, "song")

            # call the method to pause the player
            vlc_player.pause(True)

            # wait for the player to be paused
            self.wait_is_paused(vlc_player)

            # assert the callback
            vlc_player.callbacks["paused"].assert_called_with(ANY, ANY)
            vlc_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            vlc_player.callbacks["paused"].reset_mock()
            vlc_player.callbacks["resumed"].reset_mock()

            # re-call the method to pause the player
            vlc_player.pause(True)
            self.wait_is_paused(vlc_player)

            # assert the callback
            vlc_player.callbacks["paused"].assert_not_called()
            vlc_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            vlc_player.callbacks["paused"].reset_mock()
            vlc_player.callbacks["resumed"].reset_mock()

            # call the method to resume the player
            vlc_player.pause(False)

            # wait for the player to play again
            self.wait_is_playing(vlc_player)

            # assert the callback
            vlc_player.callbacks["paused"].assert_not_called()
            vlc_player.callbacks["resumed"].assert_called_with(ANY, ANY)

            # reset the mocks
            vlc_player.callbacks["paused"].reset_mock()
            vlc_player.callbacks["resumed"].reset_mock()

            # re-call the method to resume the player
            vlc_player.pause(False)
            self.wait_is_playing(vlc_player)

            # assert the callback
            vlc_player.callbacks["paused"].assert_not_called()
            vlc_player.callbacks["resumed"].assert_not_called()

    @func_set_timeout(TIMEOUT)
    def test_skip_song(self):
        """Test to skip a playlist entry
        """
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
            vlc_player.set_playlist_entry(self.playlist_entry)

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
            self.assertEqual(file_path, self.song_file_path)

            # request first playlist entry to stop
            vlc_player.skip()

            # check the song is stopped accordingly
            self.assertIsNone(vlc_player.playlist_entry)
            vlc_player.callbacks["finished"].assert_called_with(
                self.playlist_entry["id"]
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
            self.assertEqual(file_path, self.song2_file_path)

    @func_set_timeout(TIMEOUT)
    def test_skip_transition(self):
        """Test to skip a playlist entry transition screen
        """
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
            vlc_player.set_playlist_entry(self.playlist_entry)

            # wait for the transition to start
            self.wait_is_playing(vlc_player, "transition")

            # request first playlist entry to stop
            vlc_player.skip()

            # check the song is stopped accordingly
            vlc_player.callbacks["finished"].assert_called_with(
                self.playlist_entry["id"]
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
            self.assertEqual(file_path, self.song2_file_path)
