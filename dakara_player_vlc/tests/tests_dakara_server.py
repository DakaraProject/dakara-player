from unittest import TestCase
from unittest.mock import patch, MagicMock
from threading import Event
from queue import Queue

from requests.exceptions import RequestException
from websocket import (WebSocketBadStatusException,
                       WebSocketConnectionClosedException)

from dakara_player_vlc.dakara_server import (
    DakaraServerHTTPConnection,
    DakaraServerWebSocketConnection,
    DakaraServerWebSocket,
    JsonWebSocket,
    NetworkError,
    AuthenticationError,
    display_message,
    authenticated,
    connected,
)


class DakaraServerHTTPConnectionTestCase(TestCase):
    """Test the HTTP connection with the server
    """
    def setUp(self):
        # create a token
        self.token = "token value"

        # create a server address
        self.address = "www.example.com"

        # create a login and password
        self.login = "test"
        self.password = "test"

        # create an error
        self.error_message = 'error'

        # create a DakaraServerHTTPConnection instance
        self.dakara_server = DakaraServerHTTPConnection({
            'address': self.address,
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
            "http://{}/api/token-auth/".format(self.address),
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

    def test_get_token_header(self):
        """Test the helper to get token header
        """
        # set the token
        self.dakara_server.token = self.token

        # call the method
        result = self.dakara_server.get_token_header()

        # call assertions
        self.assertEqual(result, {
            'Authorization': 'Token ' + self.token
        })


class AuthenticatedTestCase(TestCase):
    """Test the `authenticated` decorator
    """
    class Authenticated:
        def __init__(self):
            self.token = None

        @authenticated
        def dummy(self):
            pass

    def test_authenticated_sucessful(self):
        """Test the authenticated decorator when token is set
        """
        instance = self.Authenticated()

        # set the token
        instance.token = True

        # call a protected method
        instance.dummy()

    def test_authenticated_error(self):
        """Test the authenticated decorator when token is not set
        """
        instance = self.Authenticated()

        # call a protected method
        with self.assertRaises(AuthenticationError):
            instance.dummy()


class JsonWebSocketTestCase(TestCase):
    """Test the WebSocket class with JSON automation
    """
    def setUp(self):
        # create instance
        self.json_web_socket = JsonWebSocket()

    @patch('dakara_player_vlc.dakara_server.super')
    def test_recv_successful(self, mock_super):
        """Test a normal use of the receive method
        """
        event = '{"data": "data"}'
        content = {'data': 'data'}

        # mock the call to the super method
        mock_super.return_value.recv.return_value = event

        # mock the methods
        self.json_web_socket.recv_json = MagicMock()

        # call the method
        result = self.json_web_socket.recv()

        # assert the result
        self.assertEqual(result, event)

        # assert the call
        mock_super.assert_called_with()
        self.json_web_socket.recv_json.assert_called_with(content)

    @patch('dakara_player_vlc.dakara_server.super')
    def test_recv_error(self, mock_super):
        """Test the receive method when data are not a JSON string
        """
        event = 'definitely not a JSON string'

        # mock the call to the super method
        mock_super.return_value.recv.return_value = event

        # mock the methods
        self.json_web_socket.recv_error = MagicMock()

        # call the method
        result = self.json_web_socket.recv()

        # assert the result
        self.assertEqual(result, event)

        # assert the call
        mock_super.assert_called_with()
        self.json_web_socket.recv_error.assert_called_with(event)

    def test_send_json(self):
        """Test a normal use of the function
        """
        event = '{"data": "data"}'
        content = {'data': 'data'}

        # mock the call to the methods
        self.json_web_socket.send = MagicMock()

        # call the method
        self.json_web_socket.send_json(content)

        # assert the call
        self.json_web_socket.send.assert_called_with(event)


class ConnectedTestCase(TestCase):
    """Test the `connected` decorator
    """
    class Connected:
        def __init__(self):
            self.websocket = None

        @connected
        def dummy(self):
            pass

    def test_connected_sucessful(self):
        """Test the connected decorator when websocket is set

        Use the `run` method for the test.
        """
        instance = self.Connected()

        # set the token
        instance.websocket = True

        # call a protected method
        instance.dummy()

    def test_connected_error(self):
        """Test the connected decorator when token is not set

        Use the interal `get_token_header` method for test.
        """
        instance = self.Connected()

        # call a protected method
        with self.assertRaises(ConnectionError):
            instance.dummy()


class DakaraServerWebSocketConnectionTestCase(TestCase):
    """Test the WebSocket connection with the server
    """
    def setUp(self):
        # create a token
        self.websocket = MagicMock()

        # create a server address
        self.address = "www.example.com"

        # create an URL
        self.url = "ws://www.example.com/ws/playlist/device/"

        # create token header
        self.header = {'token': 'token'}

        # create stop event and errors queue
        self.stop = Event()
        self.errors = Queue()

        # create a DakaraServerWebSocketConnection instance
        self.dakara_server = DakaraServerWebSocketConnection(
            self.stop,
            self.errors,
            {'address': self.address},
            self.header,
        )

        self.dakara_server.websocket = MagicMock()

    @patch('dakara_player_vlc.dakara_server.create_connection')
    def test_create_connection_successful(self, mock_create_connection):
        """Test to create a connection
        """
        # mock the call
        mock_create_connection.return_value = {}

        # call the method
        self.dakara_server.create_connection()

        # assert the call
        mock_create_connection.assert_called_with(
            self.url,
            class_=DakaraServerWebSocket,
            header=self.header
        )

    @patch('dakara_player_vlc.dakara_server.create_connection')
    def test_create_connection_error_user(self, mock_create_connection):
        """Test to connect with a user without the sufficent rights
        """
        # mock the call
        mock_create_connection.side_effect = WebSocketBadStatusException(
            'error %s', 0)

        # call the method
        with self.assertRaises(AuthenticationError):
            self.dakara_server.create_connection()

    @patch('dakara_player_vlc.dakara_server.create_connection')
    def test_create_connection_error_network(self, mock_create_connection):
        """Test to connect with when the server is unreachible
        """
        # mock the call
        mock_create_connection.side_effect = ConnectionRefusedError()

        # call the method
        with self.assertRaises(NetworkError):
            self.dakara_server.create_connection()

    def test_run_end(self):
        """Test a normal run untill the end of the connection
        """
        # mock the call
        self.dakara_server.websocket.next.side_effect = \
            WebSocketConnectionClosedException()

        # call the method
        self.dakara_server.run()

        # assert the call
        self.dakara_server.websocket.next.assert_called_with()

    def test_run_stop(self):
        """Test a run untill the stop event is set
        """
        def stop():
            self.stop.set()

        # mock the call
        self.dakara_server.websocket.next.side_effect = stop

        # call the method
        self.dakara_server.run()

        # assert the call
        self.dakara_server.websocket.next.assert_called_with()

    def test_exit_worker(self):
        """Test to exit the worker
        """
        # call the method
        self.dakara_server.exit_worker()

        # assert the call
        self.dakara_server.websocket.abort.assert_called_with()


class DakaraServerWebSocketTestCase(TestCase):
    """Test the WebSocket communications with the server
    """
    def setUp(self):
        # create a playlist entry
        self.playlist_entry_id = 0
        self.playlist_entry = {
            'id': self.playlist_entry_id,
        }

        # create an error
        self.error_message = 'error'

        # create pause
        self.paused = False

        # create timing
        self.timing = 100

        # create a DakaraServerWebSocket instance
        self.dakara_server = DakaraServerWebSocket()

    def test_set_callbacks(self):
        """Test the callback setter methods
        """
        def dummy_function():
            pass

        for name in ('idle', 'new_entry', 'command', 'status_request'):
            method = getattr(self.dakara_server, "{}_callback"
                             .format(name))
            set_method = getattr(self.dakara_server, "set_{}_callback"
                                 .format(name))

            # assert the initial case
            self.assertIsNot(method, dummy_function)

            # call the method
            set_method(dummy_function)

            # assert the result
            method = getattr(self.dakara_server, "{}_callback"
                             .format(name))
            self.assertIs(method, dummy_function)

    def test_recv_json_successful(self):
        """Test the receive method for an existing method
        """
        content = {'type': 'idle', 'data': 'data'}

        # mock the call
        self.dakara_server.recv_idle = MagicMock()

        # call the method
        self.dakara_server.recv_json(content)

        # assert the call
        self.dakara_server.recv_idle.assert_called_with('data')

    def test_recv_json_error(self):
        """Test the receive method for a non-existent method
        """
        content = {'type': 'nothing', 'data': 'data'}

        # call the method
        with self.assertRaises(ValueError):
            self.dakara_server.recv_json(content)

    def test_recv_idle(self):
        """Test the receive idle event method
        """
        # mock the call
        self.dakara_server.idle_callback = MagicMock()

        # call the method
        self.dakara_server.recv_idle({})

        # assert the call
        self.dakara_server.idle_callback.assert_called_with()

    def test_recv_new_entry(self):
        """Test the receive new entry event method
        """
        content = {'id': 0, 'song': None}

        # mock the call
        self.dakara_server.new_entry_callback = MagicMock()

        # call the method
        self.dakara_server.recv_new_entry(content)

        # assert the call
        self.dakara_server.new_entry_callback.assert_called_with(content)

    def test_recv_status_request(self):
        """Test the receive status request event method
        """
        # mock the call
        self.dakara_server.status_request_callback = MagicMock()

        # call the method
        self.dakara_server.recv_status_request({})

        # assert the call
        self.dakara_server.status_request_callback.assert_called_with()

    def test_recv_command(self):
        """Test the receive command event method
        """
        content = {'command': 'command_value'}

        # mock the call
        self.dakara_server.command_callback = MagicMock()

        # call the method
        self.dakara_server.recv_command(content)

        # assert the call
        self.dakara_server.command_callback.assert_called_with('command_value')

    def test_send_entry_error_successful(self):
        """Test to send an entry error event sucessfuly
        """
        # mock the call
        self.dakara_server.send_json = MagicMock()

        # call the method
        self.dakara_server.send_entry_error(0, 'message')

        # assert the call
        self.dakara_server.send_json.assert_called_with({
            'type': 'entry_error',
            'data': {
                'entry_id': 0,
                'error_message': 'message'
            }
        })

    def test_send_entry_error_error(self):
        """Test to send an invalid entry error
        """
        # call the method
        with self.assertRaises(RuntimeError):
            self.dakara_server.send_entry_error(None, 'message')

    def test_send_entry_finished_successful(self):
        """Test to send an entry finished event sucessfuly
        """
        # mock the call
        self.dakara_server.send_json = MagicMock()

        # call the method
        self.dakara_server.send_entry_finished(0)

        # assert the call
        self.dakara_server.send_json.assert_called_with({
            'type': 'entry_finished',
            'data': {
                'entry_id': 0,
            }
        })

    def test_send_entry_finished_error(self):
        """Test to send an invalid entry finished
        """
        # call the method
        with self.assertRaises(RuntimeError):
            self.dakara_server.send_entry_finished(None)

    def test_send_status(self):
        """Test to send the player status
        """
        # mock the call
        self.dakara_server.send_json = MagicMock()

        # call the method
        self.dakara_server.send_status(0, 10000, True)

        # assert the call
        self.dakara_server.send_json.assert_called_with({
            'type': 'status',
            'data': {
                'entry_id': 0,
                'timing': 10,
                'paused': True
            }
        })


class DisplayMessageTestCase(TestCase):
    """Test the message display helper
    """
    def test_small_message(self):
        """Test a small message is completelly displayed
        """
        message = "few characters"
        message_displayed = display_message(message, limit=50)

        self.assertEqual(message_displayed, "few characters")
        self.assertLessEqual(len(message_displayed), 50)

    def test_long_message(self):
        """Test a long message is cut
        """
        message = "few characters"
        message_displayed = display_message(message, limit=5)

        self.assertEqual(message_displayed, "fe...")
        self.assertLessEqual(len(message_displayed), 5)
