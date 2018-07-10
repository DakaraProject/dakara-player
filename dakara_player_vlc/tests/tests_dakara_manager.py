from unittest import TestCase
from unittest.mock import MagicMock

from dakara_player_vlc.dakara_manager import DakaraManager


class DakaraManagerTestCase(TestCase):
    """Test the dakara manager class
    """
    def setUp(self):
        # create a mock font loader
        self.font_loader = MagicMock()

        # create a mock VLC player
        self.vlc_player = MagicMock()

        # create a mock Dakara server
        self.dakara_server = MagicMock()

        # create a Dakara manager
        self.dakara_manager = DakaraManager(
            self.font_loader,
            self.vlc_player,
            self.dakara_server
        )

    def test_start_idle(self):
        """Test to launch the dakara manager when there is nothing to play
        """
        # call the methods and prevent to run as thread
        self.dakara_manager.be_idle()

        # call assertions
        self.vlc_player.play_idle_screen.assert_called_once_with()
        self.vlc_player.play_song.assert_not_called()

    def test_start_play_entry(self):
        """Test to launch the dakara manager when there is something to play
        """
        entry = {'id': 0}

        # call the methods and prevent to run as thread
        self.dakara_manager.play_entry(entry)

        # call assertions
        self.vlc_player.play_idle_screen.assert_not_called()
        self.vlc_player.play_song.assert_called_once_with(entry)

    def test_handle_error(self):
        """Test the callback called on error
        """
        # call the method
        self.dakara_manager.handle_error(999, 'message')

        # call assertions
        self.dakara_server.send_entry_error.assert_called_once_with(
            999, 'message')

    def test_handle_song_end(self):
        """Test the callback called on song end
        """
        # call the method
        self.dakara_manager.handle_song_end(999)

        # call assertions
        self.dakara_server.websocket.send_entry_finished\
            .assert_called_once_with(999)

    def test_do_command_successful(self):
        """Test the command manager for valid commands
        """
        # call the method for pause
        self.dakara_manager.do_command('pause')

        # assert the call
        self.dakara_manager.vlc_player.set_pause.assert_called_with(True)

        # reset the mock
        self.dakara_manager.vlc_player = MagicMock()

        # call the method for pause
        self.dakara_manager.do_command('play')

        # assert the call
        self.dakara_manager.vlc_player.set_pause.assert_called_with(False)

    def test_do_command_error(self):
        """Test the command manager for an invalid command
        """
        # call the method
        with self.assertRaises(ValueError):
            self.dakara_manager.do_command('invalid')

    def test_get_status(self):
        """Test to get the player status
        """
        # mock the call
        self.dakara_manager.vlc_player.get_playing_id.return_value = 999
        self.dakara_manager.vlc_player.get_timing.return_value = 10000
        self.dakara_manager.vlc_player.is_paused.return_value = True
        # call the method
        self.dakara_manager.get_status()

        # assert the call
        self.dakara_manager.vlc_player.get_playing_id.assert_called_with()
        self.dakara_manager.vlc_player.get_timing.assert_called_with()
        self.dakara_manager.vlc_player.is_paused.assert_called_with()
        self.dakara_manager.dakara_server.websocket.send_status\
            .assert_called_with(999, 10000, True)
