from unittest import TestCase
from unittest.mock import MagicMock

from dakara_player.dakara_manager import DakaraManager


class DakaraManagerTestCase(TestCase):
    """Test the dakara manager class
    """

    def setUp(self):
        # create a mock font loader
        self.font_loader = MagicMock()

        # create a mock VLC player
        self.media_player = MagicMock()

        # create a mock Dakara HTTP server
        self.dakara_server_http = MagicMock()

        # create a mock Dakara websocket server
        self.dakara_server_websocket = MagicMock()

        # create a Dakara manager
        self.dakara_manager = DakaraManager(
            self.font_loader,
            self.media_player,
            self.dakara_server_http,
            self.dakara_server_websocket,
        )

    def test_start_idle(self):
        """Test to launch the dakara manager when there is nothing to play
        """
        # call the methods and prevent to run as thread
        self.dakara_manager.play_idle_screen()

        # call assertions
        self.media_player.play.assert_called_once_with("idle")
        self.media_player.set_playlist_entry.assert_not_called()

    def test_start_play_playlist_entry(self):
        """Test to launch the dakara manager when there is something to play
        """
        playlist_entry = {"id": 42}

        # call the methods and prevent to run as thread
        self.dakara_manager.play_playlist_entry(playlist_entry)

        # call assertions
        self.media_player.play.assert_not_called()
        self.media_player.set_playlist_entry.assert_called_once_with(playlist_entry)

    def test_handle_error(self):
        """Test the callback called on error
        """
        # call the method
        self.dakara_manager.handle_error(999, "message")

        # call assertions
        self.dakara_server_http.create_player_error.assert_called_once_with(
            999, "message"
        )

    def test_handle_finished(self):
        """Test the callback called on song end
        """
        # call the method
        self.dakara_manager.handle_finished(999)

        # call assertions
        self.dakara_server_http.update_finished.assert_called_once_with(999)

    def test_handle_started_transition(self):
        """Test the callback called on transition start
        """
        # call the method
        self.dakara_manager.handle_started_transition(999)

        # call assertions
        self.dakara_server_http.update_started_transition.assert_called_once_with(999)

    def test_handle_started_song(self):
        """Test the callback called on song start
        """
        # call the method
        self.dakara_manager.handle_started_song(999)

        # call assertions
        self.dakara_server_http.update_started_song.assert_called_once_with(999)

    def test_handle_could_not_play(self):
        """Test the callback called when a playlist entry could not play
        """
        # call the method
        self.dakara_manager.handle_could_not_play(999)

        # call assertions
        self.dakara_server_http.update_could_not_play.assert_called_once_with(999)

    def test_handle_paused(self):
        """Test the callback called when the player is paused
        """
        # call the method
        self.dakara_manager.handle_paused(999, 10)

        # call assertions
        self.dakara_server_http.update_paused.assert_called_once_with(999, 10)

    def test_handle_resumed(self):
        """Test the callback called when the player resumed playing
        """
        # call the method
        self.dakara_manager.handle_resumed(999, 10)

        # call assertions
        self.dakara_server_http.update_resumed.assert_called_once_with(999, 10)

    def test_do_command_successful(self):
        """Test the command manager for valid commands
        """
        # mock the playlist entry ID
        self.dakara_manager.media_player.playing_id = 42

        # call the method for pause
        self.dakara_manager.do_command("pause")

        # assert the call
        self.dakara_manager.media_player.pause.assert_called_with(True)

        # reset the mock
        self.dakara_manager.media_player.pause.reset_mock()

        # call the method for pause
        self.dakara_manager.do_command("play")

        # assert the call
        self.dakara_manager.media_player.pause.assert_called_with(False)

        # call the method for skip
        self.dakara_manager.do_command("skip")

        # assert the call
        self.media_player.skip.assert_called_with()

    def test_do_command_error(self):
        """Test the command manager for an invalid command
        """
        # call the method
        with self.assertRaises(AssertionError):
            self.dakara_manager.do_command("invalid")
