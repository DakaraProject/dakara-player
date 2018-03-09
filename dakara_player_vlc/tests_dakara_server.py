from unittest import TestCase
from unittest.mock import patch, ANY
import logging

from requests.exceptions import RequestException

from dakara_player_vlc.dakara_server import (
        DakaraServer,
        NetworkError,
        AuthenticationError,
        )


# shut down dakara_server logging
logging.getLogger('dakara_server').setLevel(logging.CRITICAL)


class DakaraServerTestCase(TestCase):
    """Test the connection with the server
    """
    def setUp(self):
        # create a token
        self.token = "token value"

        # create a login and password
        self.login = "test"
        self.password = "test"

        # create a playlist entry
        self.playlist_entry_id = 0
        self.playlist_entry = {
                'id': self.playlist_entry_id,
                }

        # create an error
        self.error_message = 'error'

        # create commands
        self.commands = {
                'pause': False,
                'skip': False,
                }

        # create pause
        self.paused = False

        # create timing
        self.timing = 100

        # create a DakaraServer instance
        self.dakara_server = DakaraServer({
            'url': "http://www.example.com",
            'login': self.login,
            'password': self.password,
            })

    @patch('dakara_player_vlc.dakara_server.requests.post')
    def test_authenticate_successful(self, mock_post):
        """Test a successful authentication with the server
        """
        # mock the response of the server
        mock_post.return_value.ok = True
        mock_post.return_value.json.return_value = {'token': self.token}

        # pre assertions
        self.assertFalse(self.dakara_server.token)

        # call the method
        self.dakara_server.authenticate()

        # call assertions
        mock_post.assert_called_with(
                ANY,
                data={
                    'username': self.login,
                    'password': self.password,
                    }
                )

        # post assertions
        self.assertTrue(self.dakara_server.token)
        self.assertEqual(self.dakara_server.token, self.token)

    @patch('dakara_player_vlc.dakara_server.requests.post')
    def test_authenticate_error_network(self, mock_post):
        """Test a network error when authenticating
        """
        # mock the response of the server
        mock_post.side_effect = RequestException()

        # call the method
        with self.assertRaises(NetworkError):
            self.dakara_server.authenticate()

    @patch('dakara_player_vlc.dakara_server.requests.post')
    def test_authenticate_error_authentication(self, mock_post):
        """Test an authentication error when authenticating
        """
        # mock the response of the server
        mock_post.return_value.ok = False
        mock_post.return_value.status_code = 400

        # call the method
        with self.assertRaises(AuthenticationError):
            self.dakara_server.authenticate()

    @patch('dakara_player_vlc.dakara_server.requests.post')
    def test_authenticate_error_other(self, mock_post):
        """Test a server error when authenticating
        """
        # mock the response of the server
        mock_post.return_value.ok = False
        mock_post.return_value.status_code = 999
        mock_post.return_value.test = 'error'

        # call the method
        with self.assertRaises(AuthenticationError):
            self.dakara_server.authenticate()

    def test_authenticated_sucessful(self):
        """Test the authenticated decorator when token is set

        Use the interal `_get_token_header` method for test.
        """
        # set the token
        self.dakara_server.token = self.token

        # call a protected method
        self.dakara_server._get_token_header()

    def test_authenticated_error(self):
        """Test the authenticated decorator when token is not set

        Use the interal `_get_token_header` method for test.
        """
        # call a protected method
        with self.assertRaises(AuthenticationError):
            self.dakara_server._get_token_header()

    def test__get_token_header(self):
        """Test the helper to get token header
        """
        # set the token
        self.dakara_server.token = self.token

        # call the method
        result = self.dakara_server._get_token_header()

        # call assertions
        self.assertEqual(result, {
            'Authorization': 'Token ' + self.token
            })

    @patch('dakara_player_vlc.dakara_server.requests.get')
    def test_get_next_song_successful(self, mock_get):
        """Test the request of a song from the server
        """
        # mock the response of the server
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = self.playlist_entry

        # set the token
        self.dakara_server.token = self.token

        # call the method
        result = self.dakara_server.get_next_song()

        # call assertions
        self.assertEqual(result, self.playlist_entry)

    @patch('dakara_player_vlc.dakara_server.requests.get')
    def test_get_next_song_error_network(self, mock_get):
        """Test a connection error when requesting a song
        """
        # mock the response of the server
        mock_get.side_effect = RequestException()

        # set the token
        self.dakara_server.token = self.token

        # call the method
        result = self.dakara_server.get_next_song()

        # call assertions
        self.assertIs(result, None)

    @patch('dakara_player_vlc.dakara_server.requests.get')
    def test_get_next_song_error_other(self, mock_get):
        """Test a server error when requesting a song
        """
        # mock the response of the server
        mock_get.return_value.ok = False
        mock_get.return_value.status_code = 999
        mock_get.return_value.text = 'error'

        # set the token
        self.dakara_server.token = self.token

        # call the method
        result = self.dakara_server.get_next_song()

        # call assertions
        self.assertIs(result, None)

    @patch('dakara_player_vlc.dakara_server.requests.post')
    def test_send_error_successful(self, mock_post):
        """Test the sending of an error
        """
        # mock the response of the server
        mock_post.return_value.ok = True

        # set the token
        self.dakara_server.token = self.token

        # call the method
        self.dakara_server.send_error(self.playlist_entry_id,
                                      self.error_message)

        # call assertions
        mock_post.assert_called_with(
                ANY,
                headers=ANY,
                json={
                    'playlist_entry': self.playlist_entry_id,
                    'error_message': self.error_message
                    }
                )

    @patch('dakara_player_vlc.dakara_server.requests.post')
    def test_send_error_error_network(self, mock_post):
        """Test a network error when sending an error
        """
        # mock the response of the server
        mock_post.side_effect = RequestException()

        # set the token
        self.dakara_server.token = self.token

        # call the method
        self.dakara_server.send_error(self.playlist_entry_id,
                                      self.error_message)

    @patch('dakara_player_vlc.dakara_server.requests.post')
    def test_send_error_error_other(self, mock_post):
        """Test a server error when sending an error
        """
        # mock the response of the server
        mock_post.return_value.ok = False

        # set the token
        self.dakara_server.token = self.token

        # call the method
        self.dakara_server.send_error(self.playlist_entry_id,
                                      self.error_message)

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_send_status_get_commands_successful(self, mock_put):
        """Test the sending of the status and retrieving of the commands
        """
        # mock the response of the server
        mock_put.return_value.ok = True
        mock_put.return_value.json.return_value = self.commands

        # set the token
        self.dakara_server.token = self.token

        # call the method
        result = self.dakara_server.send_status_get_commands(
                self.playlist_entry_id,
                self.timing,
                self.paused,
                )

        # call assertions
        self.assertEqual(result, self.commands)
        mock_put.assert_called_with(
                ANY,
                headers=ANY,
                json={
                    'playlist_entry_id': self.playlist_entry_id,
                    'timing': self.timing / 1000.,
                    'paused': self.paused,
                    }
                )

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_send_status_get_commands_error_network(self, mock_put):
        """Test a network error when sending status and retrieving commands
        """
        # mock the response of the server
        mock_put.side_effect = RequestException()

        # set the token
        self.dakara_server.token = self.token

        # call the method
        result = self.dakara_server.send_status_get_commands(
                self.playlist_entry_id,
                self.timing,
                self.paused,
                )

        # call assertions
        self.assertEqual(result, {'pause': True, 'skip': False})

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_send_status_get_commands_error_other(self, mock_put):
        """Test a server error when sending status and retrieving commands
        """
        # mock the response of the server
        mock_put.return_value.ok = False
        mock_put.return_value.status_code = 999
        mock_put.return_value.text = 'error'

        # set the token
        self.dakara_server.token = self.token

        # call the method
        result = self.dakara_server.send_status_get_commands(
                self.playlist_entry_id,
                self.timing,
                self.paused,
                )

        # call assertions
        self.assertEqual(result, {'pause': True, 'skip': False})
