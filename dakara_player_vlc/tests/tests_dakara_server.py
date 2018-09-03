from unittest import TestCase
from unittest.mock import patch, MagicMock, ANY
from threading import Event
from queue import Queue
import yaml

from requests.exceptions import RequestException
from websocket import (WebSocketBadStatusException,
                       WebSocketConnectionClosedException)

from dakara_player_vlc.dakara_server import (
    DakaraServerHTTPConnection,
    DakaraServerWebSocketConnection,
    NetworkError,
    AuthenticationError,
    display_message,
    authenticated,
    connected,
)
from dakara_player_vlc.resources_manager import get_test_material


class DakaraServerHTTPConnectionTestCase(TestCase):
    """Test the HTTP connection with the server
    """
    def setUp(self):
        # create a token
        self.token = "token value"

        # create a server address
        self.address = "www.example.com"

        # create a server URL
        self.url = "http://www.example.com/api/"

        # create a login and password
        self.login = "test"
        self.password = "test"

        # create a DakaraServerHTTPConnection instance
        self.dakara_server = DakaraServerHTTPConnection({
            'address': self.address,
            'login': self.login,
            'password': self.password,
        })

    def test_init(self):
        """Test the created object
        """
        self.assertEqual(self.dakara_server.server_url, self.url)
        self.assertEqual(self.dakara_server.login, self.login)
        self.assertEqual(self.dakara_server.password, self.password)
        self.assertIsNone(self.dakara_server.token)

    def test_init_from_config(self):
        """Test to create the object from a config file
        """
        # open the config
        config_path = get_test_material("config.yaml")
        with open(config_path) as file:
            config = yaml.load(file)
            config = config['server']

        # create an object
        dakara_server = DakaraServerHTTPConnection(config)

        # test the created object
        self.assertEqual(dakara_server.server_url,
                         "https://www.example.com/api/")
        self.assertEqual(dakara_server.login, "player_login")
        self.assertEqual(dakara_server.password, "player_password")

    @patch('dakara_player_vlc.dakara_server.requests.post')
    def test_send_request_successful(self, mock_post):
        """Test to send a request with the generic method
        """
        # set the token
        self.dakara_server.token = self.token

        # call the method
        self.dakara_server.send_request(
            'post',
            self.url,
            data={'content': 'test'},
            message_on_error='error message'
        )

        # assert the call
        mock_post.assert_called_with(
            self.url,
            headers={'Authorization': 'Token token value'},
            data={'content': 'test'}
        )

    def test_send_request_error_method(self):
        """Test that a wrong method name fails for a generic request
        """
        # set the token
        self.dakara_server.token = self.token

        # call the method
        with self.assertRaises(ValueError):
            self.dakara_server.send_request(
                'invalid',
                self.url,
                data={'content': 'test'},
                message_on_error='error message'
            )

    @patch('dakara_player_vlc.dakara_server.requests.post')
    def test_send_request_error_network(self, mock_post):
        """Test to send a request when there is a network error
        """
        # set the token
        self.dakara_server.token = self.token

        # mock the response of the server
        mock_post.side_effect = RequestException()

        # call the method
        self.dakara_server.send_request(
            'post',
            self.url,
            data={'content': 'test'},
            message_on_error='error message'
        )

    @patch('dakara_player_vlc.dakara_server.requests.get')
    def test_get(self, mock_get):
        """Test the get method
        """
        # set the token
        self.dakara_server.token = self.token

        # mock the response
        response = MagicMock()
        response.data = "data"
        mock_get.return_value = response

        # call the method
        response_obtained = self.dakara_server.get(
            self.url,
        )

        # assert the call
        mock_get.assert_called_with(
            self.url,
            headers=ANY,
        )

        # assert the result
        self.assertEqual(response_obtained.data, 'data')

    @patch('dakara_player_vlc.dakara_server.requests.post')
    def test_post(self, mock_post):
        """Test the post method
        """
        # set the token
        self.dakara_server.token = self.token

        # call the method
        self.dakara_server.post(
            self.url,
            data={'content': 'content'}
        )

        # assert the call
        mock_post.assert_called_with(
            self.url,
            headers=ANY,
            data={'content': 'content'}
        )

    @patch('dakara_player_vlc.dakara_server.requests.patch')
    def test_patch(self, mock_patch):
        """Test the patch method
        """
        # set the token
        self.dakara_server.token = self.token

        # call the method
        self.dakara_server.patch(
            self.url,
            data={'content': 'content'}
        )

        # assert the call
        mock_patch.assert_called_with(
            self.url,
            headers=ANY,
            data={'content': 'content'}
        )

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_put(self, mock_put):
        """Test the put method
        """
        # set the token
        self.dakara_server.token = self.token

        # call the method
        self.dakara_server.put(
            self.url,
            data={'content': 'content'}
        )

        # assert the call
        mock_put.assert_called_with(
            self.url,
            headers=ANY,
            data={'content': 'content'}
        )

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
            self.url + "token-auth/",
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

    @patch('dakara_player_vlc.dakara_server.requests.post')
    def test_create_player_error_successful(self, mock_post):
        """Test to report an error sucessfuly
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        self.dakara_server.create_player_error(42, 'message')

        # assert the call
        mock_post.assert_called_with(
            'http://www.example.com/api/playlist/player/errors/',
            headers=ANY,
            data={
                'playlist_entry_id': 42,
                'error_message': 'message'
            }
        )

    @patch('dakara_player_vlc.dakara_server.requests.post')
    def test_create_player_error_failed(self, mock_post):
        """Test to report an invalid error
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        with self.assertRaises(ValueError):
            self.dakara_server.create_player_error(None, 'message')

        # assert the call
        mock_post.assert_not_called()

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_update_finished_successful(self, mock_put):
        """Test to report that a playlist entry finished
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        self.dakara_server.update_finished(42)

        # assert the call
        mock_put.assert_called_with(
            'http://www.example.com/api/playlist/player/status/',
            headers=ANY,
            data={
                'event': 'finished',
                'playlist_entry_id': 42,
            }
        )

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_send_playlist_entry_finished_failed(self, mock_put):
        """Test to report that an invalid playlist entry finished
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        with self.assertRaises(ValueError):
            self.dakara_server.update_finished(None)

        # assert the call
        mock_put.assert_not_called()

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_update_started_transition_successful(self, mock_put):
        """Test to report that a playlist entry transition started
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        self.dakara_server.update_started_transition(42)

        # assert the call
        mock_put.assert_called_with(
            'http://www.example.com/api/playlist/player/status/',
            headers=ANY,
            data={
                'event': 'started_transition',
                'playlist_entry_id': 42,
            }
        )

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_update_playlist_entry_started_failed(self, mock_put):
        """Test to report that an invalid playlist entry transition started
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        with self.assertRaises(ValueError):
            self.dakara_server.update_started_transition(None)

        # assert the call
        mock_put.assert_not_called()

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_update_started_song_successful(self, mock_put):
        """Test to report that a playlist entry song started
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        self.dakara_server.update_started_song(42)

        # assert the call
        mock_put.assert_called_with(
            'http://www.example.com/api/playlist/player/status/',
            headers=ANY,
            data={
                'event': 'started_song',
                'playlist_entry_id': 42,
            }
        )

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_update_started_song_failed(self, mock_put):
        """Test to report that an invalid playlist entry song started
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        with self.assertRaises(ValueError):
            self.dakara_server.update_started_song(None)

        # assert the call
        mock_put.assert_not_called()

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_update_could_not_play_successful(self, mock_put):
        """Test to report that a playlist entry could not be played
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        self.dakara_server.update_could_not_play(42)

        # assert the call
        mock_put.assert_called_with(
            'http://www.example.com/api/playlist/player/status/',
            headers=ANY,
            data={
                'event': 'could_not_play',
                'playlist_entry_id': 42,
            }
        )

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_update_could_not_play_failed(self, mock_put):
        """Test to report that an invalid playlist entry could not be played
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        with self.assertRaises(ValueError):
            self.dakara_server.update_could_not_play(None)

        # assert the call
        mock_put.assert_not_called()

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_update_paused_successful(self, mock_put):
        """Test to report that the player paused
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        self.dakara_server.update_paused(42, 424242)

        # assert the call
        mock_put.assert_called_with(
            'http://www.example.com/api/playlist/player/status/',
            headers=ANY,
            data={
                'event': 'paused',
                'playlist_entry_id': 42,
                'timing': 424242,
            }
        )

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_update_paused_failed(self, mock_put):
        """Test to report that the player paused with incorrect entry
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        with self.assertRaises(ValueError):
            self.dakara_server.update_paused(None, 424242)

        # assert the call
        mock_put.assert_not_called()

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_update_resumed_successful(self, mock_put):
        """Test to report that the player resumed playing
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        self.dakara_server.update_resumed(42, 424242)

        # assert the call
        mock_put.assert_called_with(
            'http://www.example.com/api/playlist/player/status/',
            headers=ANY,
            data={
                'event': 'resumed',
                'playlist_entry_id': 42,
                'timing': 424242,
            }
        )

    @patch('dakara_player_vlc.dakara_server.requests.put')
    def test_update_resumed_failed(self, mock_put):
        """Test to report that the player resumed playing with incorrect entry
        """
        # simulate authentication
        self.dakara_server.token = "Token"

        # call the method
        with self.assertRaises(ValueError):
            self.dakara_server.update_resumed(None, 424242)

        # assert the call
        mock_put.assert_not_called()


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
        # create a mock websocket
        self.websocket = MagicMock()

        # create a server address
        self.address = "www.example.com"

        # create an URL
        self.url = "ws://www.example.com/ws/playlist/device/"

        # create token header
        self.header = {'token': 'token'}

        # create a reconnect interval
        self.reconnect_interval = 1

        # create stop event and errors queue
        self.stop = Event()
        self.errors = Queue()

        # create a DakaraServerWebSocketConnection instance
        self.dakara_server = DakaraServerWebSocketConnection(
            self.stop,
            self.errors,
            {
                'address': self.address,
                'reconnect_interval': self.reconnect_interval
            },
            self.header,
        )

    def test_init_worker(self):
        """Test the created object
        """
        self.assertEqual(self.dakara_server.server_url, self.url)
        self.assertEqual(self.dakara_server.header, self.header)
        self.assertEqual(self.dakara_server.reconnect_interval,
                         self.reconnect_interval)
        self.assertIsNone(self.dakara_server.websocket)

    def test_init_worker_from_config(self):
        """Test to create the object from a config file
        """
        # open the config
        config_path = get_test_material("config.yaml")
        with open(config_path) as file:
            config = yaml.load(file)
            config = config['server']

        # create an object
        dakara_server = DakaraServerWebSocketConnection(self.stop, self.errors,
                                                        config, self.header)

        # test the created object
        self.assertEqual(dakara_server.server_url,
                         "wss://www.example.com/ws/playlist/device/")
        self.assertEqual(dakara_server.reconnect_interval, 10)

    def test_exit_worker(self):
        """Test to exit the worker
        """
        # mock the abort function
        self.dakara_server.abort = MagicMock()

        # call the method
        self.dakara_server.exit_worker()

        # assert the call
        self.dakara_server.abort.assert_called_with()

    def test_on_open(self):
        """Test the callback on connection open
        """
        # call the method
        self.dakara_server.on_open()

        # assert the call
        self.assertFalse(self.dakara_server.retry)

    def test_on_close_normal(self):
        """Test the callback on connection close when the program is closing
        """
        # pre assert
        self.assertFalse(self.dakara_server.retry)

        # mock the create timer helper that should not be called
        self.dakara_server.create_timer = MagicMock()

        # set the program is closing
        self.stop.set()

        # call the method
        self.dakara_server.on_close(None, None)

        # assert the websocket object has been destroyed
        self.assertIsNone(self.dakara_server.websocket)

        # assert the create timer helper was not called
        self.dakara_server.create_timer.assert_not_called()

    def test_on_close_retry(self):
        """Test the callback on connection close when connection should retry
        """
        # set the retry flag on
        self.dakara_server.retry = True

        # mock the create timer helper
        self.dakara_server.create_timer = MagicMock()

        # call the method
        self.dakara_server.on_close(None, None)

        # assert the different calls
        self.dakara_server.create_timer.assert_called_with(
            self.reconnect_interval, self.dakara_server.run
        )
        self.dakara_server.timer.start.assert_called_with()

    def test_on_message_successful(self):
        """Test a normal use of the on message method
        """
        event = '{"type": "dummy", "data": "data"}'
        content = 'data'

        # mock the method to call for this type
        self.dakara_server.receive_dummy = MagicMock()

        # call the method
        self.dakara_server.on_message(event)

        # assert the dummy method has been called
        self.dakara_server.receive_dummy.assert_called_with(content)

    @patch('dakara_player_vlc.dakara_server.getattr')
    def test_on_message_failed_json(self, mock_getattr):
        """Test the on message method when event is not a JSON string
        """
        event = 'definitely not a JSON string'

        # call the method
        self.dakara_server.on_message(event)

        # assert no method has been called
        mock_getattr.assert_not_called()

    @patch('dakara_player_vlc.dakara_server.getattr')
    def test_on_message_failed_type(self, mock_getattr):
        """Test the on message method when event has an unknown type
        """
        event = '{"type": "dummy", "data": "data"}'

        # call the method
        self.dakara_server.on_message(event)

        # assert no method has been called
        mock_getattr.assert_not_called()

    @patch('dakara_player_vlc.dakara_server.logger')
    def test_on_error_closing(self, mock_logger):
        """Test the callback on error when the program is closing

        The error should be ignored.
        """
        # close the program
        self.stop.set()

        # call the method
        self.dakara_server.on_error(Exception('error message'))

        # assert the call
        mock_logger.assert_not_called()
        self.assertTrue(self.errors.empty())

    def test_on_error_unknown(self):
        """Test the callback on an unknown error

        The error should be logged only.
        """
        # pre assert
        self.assertFalse(self.stop.is_set())

        class CustomError(Exception):
            pass

        # call the method
        self.dakara_server.on_error(CustomError('error message'))

        # assert the call
        self.assertTrue(self.errors.empty())

    def test_on_error_authentication(self):
        """Test the callback on error when the authentication is refused
        """
        # pre assert
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # call the method
        self.dakara_server.on_error(
            WebSocketBadStatusException("error %s", 0))

        # assert the call
        self.assertFalse(self.errors.empty())
        _, error, _ = self.errors.get()
        self.assertIsInstance(error, AuthenticationError)

    def test_on_error_network_normal(self):
        """Test the callback on error when the server is unreachable
        """
        # pre assert
        self.assertFalse(self.dakara_server.retry)
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # call the method
        self.dakara_server.on_error(ConnectionRefusedError("error"))

        # assert the call
        self.assertFalse(self.errors.empty())
        _, error, _ = self.errors.get()
        self.assertIsInstance(error, NetworkError)

    def test_on_error_network_retry(self):
        """Test the callback on error when the server is unreachable on retry

        No exception should be raised, the error should be logged only.
        """
        # pre assert
        self.assertFalse(self.stop.is_set())

        # set retry flag on
        self.dakara_server.retry = True

        # call the method
        self.dakara_server.on_error(ConnectionRefusedError("error"))

        # assert the call
        self.assertTrue(self.errors.empty())

    def test_on_error_route(self):
        """Test the callback on error when the route is invalid
        """
        # pre assert
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # call the method
        self.dakara_server.on_error(ConnectionResetError("error"))

        # assert the call
        self.assertFalse(self.errors.empty())
        _, error, _ = self.errors.get()
        self.assertIsInstance(error, ValueError)

    def test_on_error_closed(self):
        """Test the callback on error when the connection is closed by server
        """
        # pre assert
        self.assertFalse(self.stop.is_set())
        self.assertFalse(self.dakara_server.retry)

        # mock the callback for connection lost
        self.dakara_server.connection_lost_callback = MagicMock()

        # call the methods
        self.dakara_server.on_error(
            WebSocketConnectionClosedException("error"))
        self.dakara_server.on_close(None, None)

        # assert the call
        self.assertTrue(self.dakara_server.retry)
        self.dakara_server.connection_lost_callback.assert_called_with()

    def test_send(self):
        """Test a normal use of the function
        """
        event = '{"data": "data"}'
        content = {'data': 'data'}

        # mock the websocket
        self.dakara_server.websocket = MagicMock()

        # call the method
        self.dakara_server.send(content)

        # assert the call
        self.dakara_server.websocket.send.assert_called_with(event)

    def test_abort_connected(self):
        """Test to abort the connection
        """
        # pre assert
        self.assertFalse(self.dakara_server.retry)

        # mock the websocket
        self.dakara_server.websocket = MagicMock()

        # call the method
        self.dakara_server.abort()

        # assert the call
        self.dakara_server.websocket.sock.abort.assert_called_with()
        self.assertFalse(self.dakara_server.retry)

    def test_abort_disconnected(self):
        """Test to abort the connection when already disconnected
        """
        # pre assert
        self.assertFalse(self.dakara_server.retry)
        self.assertIsNone(self.dakara_server.websocket)

        # call the method
        self.dakara_server.abort()

        # assert the call
        self.assertFalse(self.dakara_server.retry)

    def test_abort_retry(self):
        """Test to abort the connection when retry is set
        """
        # set the retry flag on
        self.dakara_server.retry = True

        # call the method
        self.dakara_server.abort()

        # assert the call
        self.assertFalse(self.dakara_server.retry)

    @patch('dakara_player_vlc.dakara_server.WebSocketApp')
    def test_run(self, mock_websocket_app_class):
        """Test to create and run the connection
        """
        # mock the callback methods
        self.dakara_server.on_open = MagicMock()
        self.dakara_server.on_close = MagicMock()
        self.dakara_server.on_message = MagicMock()
        self.dakara_server.on_error = MagicMock()

        # pre assert
        self.assertIsNone(self.dakara_server.websocket)

        # call the method
        self.dakara_server.run()

        # assert the call
        mock_websocket_app_class.assert_called_with(
            self.url,
            header=self.header,
            on_open=ANY,
            on_close=ANY,
            on_message=ANY,
            on_error=ANY
        )
        self.dakara_server.websocket.run_forever.assert_called_with()

        # assert that the callback are correctly set
        # since the callback methods are adapted, we cannot check directy if
        # the given method reference is the same as the corresponding instance
        # method
        # so, we check that calling the given method calls the instance method
        websocket = MagicMock()
        _, kwargs = mock_websocket_app_class.call_args

        kwargs['on_open'](websocket)
        self.dakara_server.on_open.assert_called_with()

        kwargs['on_close'](websocket, None, None)
        self.dakara_server.on_close.assert_called_with(None, None)

        kwargs['on_message'](websocket, 'message')
        self.dakara_server.on_message.assert_called_with('message')

        kwargs['on_error'](websocket, 'error')
        self.dakara_server.on_error.assert_called_with('error')

        # post assert
        # in real world, this test is impossible, since the websocket object
        # has been destroyed by `on_close`
        # we use the fact this callback is not called to check if the
        # object has been created as expected
        # maybe there is a better scenario to test this
        self.assertIsNotNone(self.dakara_server.websocket)

    def test_set_callbacks(self):
        """Test the callback setter methods
        """
        def dummy_function():
            pass

        for name in ('idle', 'playlist_entry', 'command', 'connection_lost'):
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

    def test_receive_idle(self):
        """Test the receive idle event method
        """
        # mock the call
        self.dakara_server.idle_callback = MagicMock()

        # call the method
        self.dakara_server.receive_idle({})

        # assert the call
        self.dakara_server.idle_callback.assert_called_with()

    def test_receive_playlist_entry(self):
        """Test the receive new playlist entry event method
        """
        content = {'id': 0, 'song': None}

        # mock the call
        self.dakara_server.playlist_entry_callback = MagicMock()

        # call the method
        self.dakara_server.receive_playlist_entry(content)

        # assert the call
        self.dakara_server.playlist_entry_callback.assert_called_with(content)

    def test_receive_command(self):
        """Test the receive command event method
        """
        content = {'command': 'command_value'}

        # mock the call
        self.dakara_server.command_callback = MagicMock()

        # call the method
        self.dakara_server.receive_command(content)

        # assert the call
        self.dakara_server.command_callback.assert_called_with('command_value')

    def test_send_ready(self):
        """Test to notify the server that the player is ready
        """
        # mock the send command
        self.dakara_server.send = MagicMock()

        # call the command
        self.dakara_server.send_ready()

        # assert the call
        self.dakara_server.send.assert_called_with({
            'type': 'ready'
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
