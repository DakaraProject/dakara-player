from unittest import TestCase
from unittest.mock import Mock
from threading import Event
from queue import Queue
import logging

from dakara_player_vlc.dakara_manager import DakaraManager


# shut down dakara manager logging
logging.getLogger('dakara_manager').setLevel(logging.CRITICAL)


class DakaraManagerTestCase(TestCase):
    """Test the dakara manager class
    """
    def setUp(self):
        # create a mock font loader
        self.font_loader = Mock()

        # create a mock VLC player
        self.vlc_player = Mock()

        # create a mock Dakara server
        self.dakara_server = Mock()

        # create stop event and errors queue
        self.stop = Event()
        self.errors = Queue()

        # create a Dakara manager
        self.dakara_manager = DakaraManager(
                self.stop,
                self.errors,
                self.font_loader,
                self.vlc_player,
                self.dakara_server
                )

    def test_start_idle(self):
        """Test to launch the dakara manager when there is nothing to play
        """
        # mock server calls
        self.dakara_server.get_next_song.return_value = None

        # mock player calls
        self.vlc_player.is_idle.return_value = True
        self.vlc_player.get_timing.return_value = 0
        self.vlc_player.is_paused.return_value = False

        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # call the methods and prevent to run as thread
        self.stop.set()
        self.dakara_manager.start()

        # call assertions
        self.dakara_server.get_next_song.assert_called()
        self.vlc_player.play_idle_screen.assert_called_once_with()
        self.dakara_server.send_status_get_commands.\
            assert_called_once_with(None)

        self.vlc_player.is_idle.assert_called_once_with()
        self.vlc_player.play_song.assert_not_called()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())
        self.assertFalse(self.dakara_manager.timer.is_alive())

    def test_start_not_idle(self):
        """Test to launch the dakara manager when there is something to play
        """
        # mock server calls
        playlist_entry = {'id': 999}
        self.dakara_server.get_next_song.return_value = playlist_entry

        # mock player calls
        self.vlc_player.is_idle.return_value = False
        self.vlc_player.get_playing_id.return_value = playlist_entry['id']
        self.vlc_player.get_timing.return_value = 0
        self.vlc_player.is_paused.return_value = False
        self.dakara_server.send_status_get_commands.return_value = {
                'pause': False,
                'skip': False,
                }

        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # call the methods and prevent to run as thread
        self.stop.set()
        self.dakara_manager.start()

        # call assertions
        self.dakara_server.get_next_song.assert_called_once_with()
        self.vlc_player.is_idle.assert_called_once_with()
        self.vlc_player.get_playing_id.assert_called_once_with()
        self.vlc_player.get_timing.assert_called_once_with()
        self.vlc_player.play_idle_screen.assert_not_called()
        self.dakara_server.send_status_get_commands.assert_called_once_with(
                playlist_entry['id'], 0, False
                )

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())
        self.assertFalse(self.dakara_manager.timer.is_alive())

    def test_handle_error(self):
        """Test the callback called on error
        """
        # mock the call to get the next song
        self.dakara_manager.add_next_music = Mock()

        # call the method
        self.dakara_manager.handle_error(999, 'message')

        # call assertions
        self.dakara_server.send_error.assert_called_once_with(999, 'message')
        self.dakara_manager.add_next_music.assert_called_once_with()

    def test_handle_song_end(self):
        """Test the callback called on song end
        """
        # mock the call to get the next song
        self.dakara_manager.add_next_music = Mock()

        # call the method
        self.dakara_manager.handle_song_end()

        # call assertions
        self.dakara_manager.add_next_music.assert_called_once_with()
