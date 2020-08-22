import shutil
import tempfile
from queue import Queue
from threading import Event
from unittest import skipIf, TestCase
from unittest.mock import ANY, MagicMock

import vlc
from dakara_base.resources_manager import get_file
from func_timeout import func_set_timeout
from path import Path

from dakara_player_vlc.vlc_player import (
    IDLE_BG_NAME,
    mrl_to_path,
    TRANSITION_BG_NAME,
    VlcPlayer,
)
from dakara_player_vlc.resources_manager import get_background


class VlcPlayerIntegrationTestCase(TestCase):
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
            "use_instrumental": False,
        }

        self.playlist_entry2 = {
            "id": 43,
            "song": {"file_path": self.song2_file_path},
            "owner": "me",
            "use_instrumental": False,
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
        # stop player
        self.vlc_player.player.stop()

        # remove temporary directory
        shutil.rmtree(self.temp, ignore_errors=True)

    @func_set_timeout(TIMEOUT)
    def test_play_idle_screen(self):
        """Test the display of the idle screen
        """
        # pre assertions
        self.assertIsNone(self.vlc_player.player.get_media())
        self.assertEqual(self.vlc_player.player.get_state(), vlc.State.NothingSpecial)

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.play_idle_screen()

            # wait for the idle screen to start
            self.vlc_player.vlc_states["in_idle"].wait_start()

            # post assertions
            self.assertEqual(self.vlc_player.player.get_state(), vlc.State.Playing)

            self.assertIsNotNone(self.vlc_player.player.get_media())
            media = self.vlc_player.player.get_media()
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.idle_background_path)
            # TODO check which subtitle file is read
            # seems impossible to do for now

    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry(self):
        """Test to play a playlist entry

        First, the transition screen is played, then the song itself.
        """
        # mock the callbacks
        self.vlc_player.set_callback("started_transition", MagicMock())
        self.vlc_player.set_callback("started_song", MagicMock())

        # pre assertions
        self.assertIsNone(self.vlc_player.playing_id)
        self.assertFalse(self.vlc_player.vlc_states["in_transition"].is_active())
        self.assertIsNone(self.vlc_player.player.get_media())
        self.assertEqual(self.vlc_player.player.get_state(), vlc.State.NothingSpecial)

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # wait for the transition screen to start
            self.vlc_player.vlc_states["in_transition"].wait_start()

            # post assertions for transition screen
            self.assertEqual(self.vlc_player.player.get_state(), vlc.State.Playing)

            self.assertIsNotNone(self.vlc_player.playing_id)

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

            # wait for the media to start
            self.vlc_player.vlc_states["in_media"].wait_start()

            # post assertions for song
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

    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry_instrumental_track(self):
        """Test to play a playlist entry using instrumental track
        """
        # mock the callbacks
        self.vlc_player.set_callback("started_transition", MagicMock())
        self.vlc_player.set_callback("started_song", MagicMock())

        # pre assertions
        self.assertIsNone(self.vlc_player.playing_id)
        self.assertFalse(self.vlc_player.vlc_states["in_transition"].is_active())
        self.assertIsNone(self.vlc_player.player.get_media())
        self.assertEqual(self.vlc_player.player.get_state(), vlc.State.NothingSpecial)

        # request to use instrumental track
        self.playlist_entry["use_instrumental"] = True

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # wait for the song to start
            self.vlc_player.vlc_states["in_media"].wait_start()

            # post assertions for song
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

    @skipIf(
        not hasattr(vlc, "libvlc_media_slaves_add"), "VLC does not support slaves_add"
    )
    @func_set_timeout(TIMEOUT)
    def test_play_playlist_entry_instrumental_file(self):
        """Test to play a playlist entry using instrumental file
        """
        # mock the callbacks
        self.vlc_player.set_callback("started_transition", MagicMock())
        self.vlc_player.set_callback("started_song", MagicMock())

        # pre assertions
        self.assertIsNone(self.vlc_player.playing_id)
        self.assertFalse(self.vlc_player.vlc_states["in_transition"].is_active())
        self.assertIsNone(self.vlc_player.player.get_media())
        self.assertEqual(self.vlc_player.player.get_state(), vlc.State.NothingSpecial)

        # request to use instrumental file
        self.playlist_entry["song"]["file_path"] = self.song2_file_path
        self.playlist_entry["use_instrumental"] = True

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # wait for the song to start
            self.vlc_player.vlc_states["in_media"].wait_start()

            # post assertions for song
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

    @func_set_timeout(TIMEOUT)
    def test_set_pause(self):
        """Test to pause and unpause the player
        """
        # mock the callbacks
        self.vlc_player.set_callback("paused", MagicMock())
        self.vlc_player.set_callback("resumed", MagicMock())

        # start the playlist entry
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # wait for the song to start
            self.vlc_player.vlc_states["in_media"].wait_start()

            # pre asserts
            self.assertFalse(self.vlc_player.vlc_states["in_pause"].is_active())
            self.assertFalse(self.vlc_player.vlc_states["in_idle"].is_active())

            # call the method to pause the player
            self.vlc_player.set_pause(True)
            timing = self.vlc_player.get_timing()

            # wait for the player to be paused
            self.vlc_player.vlc_states["in_pause"].wait_start()

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

            # wait for the player to play again
            self.vlc_player.vlc_states["in_pause"].wait_finish()

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_not_called()
            self.vlc_player.callbacks["resumed"].assert_called_with(
                self.playlist_entry["id"],
                timing,  # on a slow computer, the timing may be inaccurate
            )

    @func_set_timeout(TIMEOUT)
    def test_set_double_pause(self):
        """Test that double pause and double resume have no effects
        """
        # mock the callbacks
        self.vlc_player.set_callback("paused", MagicMock())
        self.vlc_player.set_callback("resumed", MagicMock())

        # start the playlist entry
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # wait for the song to start
            self.vlc_player.vlc_states["in_media"].wait_start()

            # pre asserts
            self.assertFalse(self.vlc_player.vlc_states["in_pause"].is_active())
            self.assertFalse(self.vlc_player.vlc_states["in_idle"].is_active())

            # call the method to pause the player
            self.vlc_player.set_pause(True)

            # wait for the player to be paused
            self.vlc_player.vlc_states["in_pause"].wait_start()

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_called_with(ANY, ANY)
            self.vlc_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            self.vlc_player.callbacks["paused"].reset_mock()
            self.vlc_player.callbacks["resumed"].reset_mock()

            # re-call the method to pause the player
            self.vlc_player.set_pause(True)
            self.vlc_player.vlc_states["in_pause"].wait_start()

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_not_called()
            self.vlc_player.callbacks["resumed"].assert_not_called()

            # reset the mocks
            self.vlc_player.callbacks["paused"].reset_mock()
            self.vlc_player.callbacks["resumed"].reset_mock()

            # call the method to resume the player
            self.vlc_player.set_pause(False)

            # wait for the player to play again
            self.vlc_player.vlc_states["in_pause"].wait_finish()

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_not_called()
            self.vlc_player.callbacks["resumed"].assert_called_with(ANY, ANY)

            # reset the mocks
            self.vlc_player.callbacks["paused"].reset_mock()
            self.vlc_player.callbacks["resumed"].reset_mock()

            # re-call the method to resume the player
            self.vlc_player.set_pause(False)
            self.vlc_player.vlc_states["in_pause"].wait_finish()

            # assert the callback
            self.vlc_player.callbacks["paused"].assert_not_called()
            self.vlc_player.callbacks["resumed"].assert_not_called()

    @func_set_timeout(TIMEOUT)
    def test_skip(self):
        """Test to skip a playlist entry
        """
        # mock the callbacks
        self.vlc_player.set_callback("started_transition", MagicMock())
        self.vlc_player.set_callback("started_song", MagicMock())
        self.vlc_player.set_callback("finished", MagicMock())

        # pre assertions
        self.assertIsNone(self.vlc_player.playing_id)
        self.assertFalse(self.vlc_player.vlc_states["in_transition"].is_active())
        self.assertIsNone(self.vlc_player.player.get_media())
        self.assertEqual(self.vlc_player.player.get_state(), vlc.State.NothingSpecial)

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            # request initial playlist entry to play
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # wait for the media to start
            self.vlc_player.vlc_states["in_media"].wait_start()

            # post assertions for song
            self.assertEqual(self.vlc_player.player.get_state(), vlc.State.Playing)

            # check media exists
            media = self.vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song_file_path)

            # request first playlist entry to stop
            self.vlc_player.skip()

            # check the song is stopped accordingly
            self.vlc_player.callbacks["finished"].assert_called_with(
                self.playlist_entry["id"]
            )
            self.assertFalse(self.vlc_player.vlc_states["in_media"].is_active())
            self.assertFalse(self.vlc_player.vlc_states["in_transition"].is_active())
            self.assertFalse(self.vlc_player.states["in_song"].is_active())

            # request second playlist entry to play
            self.vlc_player.play_playlist_entry(self.playlist_entry2)

            # wait for the media to start
            self.vlc_player.vlc_states["in_transition"].wait_finish()
            self.vlc_player.vlc_states["in_media"].wait_start()

            # post assertions for song
            self.assertEqual(self.vlc_player.player.get_state(), vlc.State.Playing)

            # check media exists
            media = self.vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song2_file_path)

    @func_set_timeout(TIMEOUT)
    def test_skip_transition(self):
        """Test to skip a playlist entry transition screen
        """
        # mock the callbacks
        self.vlc_player.set_callback("started_transition", MagicMock())
        self.vlc_player.set_callback("started_song", MagicMock())
        self.vlc_player.set_callback("finished", MagicMock())

        # pre assertions
        self.assertIsNone(self.vlc_player.playing_id)
        self.assertFalse(self.vlc_player.vlc_states["in_transition"].is_active())
        self.assertIsNone(self.vlc_player.player.get_media())
        self.assertEqual(self.vlc_player.player.get_state(), vlc.State.NothingSpecial)

        # call the method
        with self.assertLogs("dakara_player_vlc.vlc_player", "DEBUG"):
            # request initial playlist entry to play
            self.vlc_player.play_playlist_entry(self.playlist_entry)

            # wait for the transition to start
            self.vlc_player.vlc_states["in_transition"].wait_start()

            # request first playlist entry to stop
            self.vlc_player.skip()

            # check the song is stopped accordingly
            self.vlc_player.callbacks["finished"].assert_called_with(
                self.playlist_entry["id"]
            )
            self.assertFalse(self.vlc_player.vlc_states["in_media"].is_active())
            self.assertFalse(self.vlc_player.vlc_states["in_transition"].is_active())
            self.assertFalse(self.vlc_player.states["in_song"].is_active())

            # request second playlist entry to play
            self.vlc_player.play_playlist_entry(self.playlist_entry2)

            # wait for the media to start
            self.vlc_player.vlc_states["in_transition"].wait_finish()
            self.vlc_player.vlc_states["in_media"].wait_start()

            # post assertions for song
            self.assertEqual(self.vlc_player.player.get_state(), vlc.State.Playing)

            # check media exists
            media = self.vlc_player.player.get_media()
            self.assertIsNotNone(media)

            # check media path
            file_path = mrl_to_path(media.get_mrl())
            self.assertEqual(file_path, self.song2_file_path)
