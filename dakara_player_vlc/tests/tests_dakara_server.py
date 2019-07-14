from unittest import TestCase
from unittest.mock import ANY, patch, MagicMock
from threading import Event
from queue import Queue

from dakara_player_vlc.dakara_server import (
    DakaraServerHTTPConnection,
    DakaraServerWebSocketConnection,
)


class DakaraServerHTTPConnectionTestCase(TestCase):
    """Test the HTTP connection with the server
    """

    def setUp(self):
        # create a token
        self.token = "token value"

        # create a server address
        self.address = "www.example.com"

        # create a server URL
        self.url = "http://www.example.com/api"

        # create a login and password
        self.login = "test"
        self.password = "test"

        # create a DakaraServerHTTPConnection instance
        self.dakara_server = DakaraServerHTTPConnection(
            {"address": self.address, "login": self.login, "password": self.password},
            route="api",
        )
        self.set_token()

    def set_token(self):
        """Set the token for the test client
        """
        self.dakara_server.token = "Token"

    def test_init_url(self):
        """Test the object has the correct URL
        """
        self.assertEqual(self.dakara_server.server_url, self.url)

    @patch.object(DakaraServerHTTPConnection, "post")
    def test_create_player_error_successful(self, mock_post):
        """Test to report an error sucessfuly
        """
        # call the method
        with self.assertLogs("dakara_player_vlc.dakara_server", "DEBUG") as logger:
            self.dakara_server.create_player_error(42, "message")

        # assert the effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.dakara_server:"
                "Telling the server that playlist entry 42 cannot be played"
            ],
        )

        # assert the call
        mock_post.assert_called_with(
            endpoint="playlist/player/errors/",
            data={"playlist_entry_id": 42, "error_message": "message"},
            message_on_error="Unable to send player error to server",
        )

    @patch.object(DakaraServerHTTPConnection, "post")
    def test_create_player_error_failed(self, mock_post):
        """Test to report an invalid error
        """
        # call the method
        with self.assertRaises(AssertionError):
            self.dakara_server.create_player_error(None, "message")

        # assert the call
        mock_post.assert_not_called()

    @patch.object(DakaraServerHTTPConnection, "put")
    def test_update_finished_successful(self, mock_put):
        """Test to report that a playlist entry finished
        """
        # call the method
        with self.assertLogs("dakara_player_vlc.dakara_server", "DEBUG") as logger:
            self.dakara_server.update_finished(42)

        # assert the effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.dakara_server:"
                "Telling the server that playlist entry 42 is finished"
            ],
        )

        # assert the call
        mock_put.assert_called_with(
            endpoint="playlist/player/status/",
            data={"event": "finished", "playlist_entry_id": 42},
            message_on_error="Unable to report that a playlist entry has finished",
        )

    @patch.object(DakaraServerHTTPConnection, "put")
    def test_update_finished_failed(self, mock_put):
        """Test to report that an invalid playlist entry finished
        """
        # call the method
        with self.assertRaises(AssertionError):
            self.dakara_server.update_finished(None)

        # assert the call
        mock_put.assert_not_called()

    @patch.object(DakaraServerHTTPConnection, "put")
    def test_update_started_transition_successful(self, mock_put):
        """Test to report that a playlist entry transition started
        """
        # call the method
        with self.assertLogs("dakara_player_vlc.dakara_server", "DEBUG") as logger:
            self.dakara_server.update_started_transition(42)

        # assert the effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.dakara_server:"
                "Telling the server that the transition of playlist entry "
                "42 has started"
            ],
        )

        # assert the call
        mock_put.assert_called_with(
            endpoint="playlist/player/status/",
            data={"event": "started_transition", "playlist_entry_id": 42},
            message_on_error=(
                "Unable to report that the transition of a playlist entry has started"
            ),
        )

    @patch.object(DakaraServerHTTPConnection, "put")
    def test_update_started_transition_failed(self, mock_put):
        """Test to report that an invalid playlist entry transition started
        """
        # call the method
        with self.assertRaises(AssertionError):
            self.dakara_server.update_started_transition(None)

        # assert the call
        mock_put.assert_not_called()

    @patch.object(DakaraServerHTTPConnection, "put")
    def test_update_started_song_successful(self, mock_put):
        """Test to report that a playlist entry song started
        """
        # call the method
        with self.assertLogs("dakara_player_vlc.dakara_server", "DEBUG") as logger:
            self.dakara_server.update_started_song(42)

        # assert the effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.dakara_server:"
                "Telling the server that the song of playlist entry 42 has started"
            ],
        )

        # assert the call
        mock_put.assert_called_with(
            endpoint="playlist/player/status/",
            data={"event": "started_song", "playlist_entry_id": 42},
            message_on_error=(
                "Unable to report that the song of a playlist entry has started"
            ),
        )

    @patch.object(DakaraServerHTTPConnection, "put")
    def test_update_started_song_failed(self, mock_put):
        """Test to report that an invalid playlist entry song started
        """
        # call the method
        with self.assertRaises(AssertionError):
            self.dakara_server.update_started_song(None)

        # assert the call
        mock_put.assert_not_called()

    @patch.object(DakaraServerHTTPConnection, "put")
    def test_update_could_not_play_successful(self, mock_put):
        """Test to report that a playlist entry could not be played
        """
        # call the method
        with self.assertLogs("dakara_player_vlc.dakara_server", "DEBUG") as logger:
            self.dakara_server.update_could_not_play(42)

        # assert the effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.dakara_server:"
                "Telling the server that the playlist entry 42 could not play"
            ],
        )

        # assert the call
        mock_put.assert_called_with(
            endpoint="playlist/player/status/",
            data={"event": "could_not_play", "playlist_entry_id": 42},
            message_on_error="Unable to report that playlist entry could not play",
        )

    @patch.object(DakaraServerHTTPConnection, "put")
    def test_update_could_not_play_failed(self, mock_put):
        """Test to report that an invalid playlist entry could not be played
        """
        # call the method
        with self.assertRaises(AssertionError):
            self.dakara_server.update_could_not_play(None)

        # assert the call
        mock_put.assert_not_called()

    @patch.object(DakaraServerHTTPConnection, "put")
    def test_update_paused_successful(self, mock_put):
        """Test to report that the player paused
        """
        # call the method
        with self.assertLogs("dakara_player_vlc.dakara_server", "DEBUG") as logger:
            self.dakara_server.update_paused(42, 424242)

        # assert the effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.dakara_server:"
                "Telling the server that the player is paused"
            ],
        )

        # assert the call
        mock_put.assert_called_with(
            endpoint="playlist/player/status/",
            data={"event": "paused", "playlist_entry_id": 42, "timing": 424242},
            message_on_error="Unable to report that the player is paused",
        )

    @patch.object(DakaraServerHTTPConnection, "put")
    def test_update_paused_failed(self, mock_put):
        """Test to report that the player paused with incorrect entry
        """
        # call the method
        with self.assertRaises(AssertionError):
            self.dakara_server.update_paused(None, 424242)

        # assert the call
        mock_put.assert_not_called()

    @patch.object(DakaraServerHTTPConnection, "put")
    def test_update_resumed_successful(self, mock_put):
        """Test to report that the player resumed playing
        """
        # call the method
        with self.assertLogs("dakara_player_vlc.dakara_server", "DEBUG") as logger:
            self.dakara_server.update_resumed(42, 424242)

        # assert the effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.dakara_server:"
                "Telling the server that the player resumed playing"
            ],
        )

        # assert the call
        mock_put.assert_called_with(
            endpoint="playlist/player/status/",
            data={"event": "resumed", "playlist_entry_id": 42, "timing": 424242},
            message_on_error="Unable to report that the player resumed playing",
        )

    @patch.object(DakaraServerHTTPConnection, "put")
    def test_update_resumed_failed(self, mock_put):
        """Test to report that the player resumed playing with incorrect entry
        """
        # call the method
        with self.assertRaises(AssertionError):
            self.dakara_server.update_resumed(None, 424242)

        # assert the call
        mock_put.assert_not_called()


class DakaraServerWebSocketConnectionTestCase(TestCase):
    """Test the WebSocket connection with the server
    """

    def setUp(self):
        # create a mock websocket
        self.websocket = MagicMock()

        # create a server address
        self.address = "www.example.com"

        # create an URL
        self.url = "ws://www.example.com/ws"

        # create token header
        self.header = {"token": "token"}

        # create a reconnect interval
        self.reconnect_interval = 1

        # create stop event and errors queue
        self.stop = Event()
        self.errors = Queue()

        # create a DakaraServerWebSocketConnection instance
        self.dakara_server = DakaraServerWebSocketConnection(
            self.stop,
            self.errors,
            {"address": self.address, "reconnect_interval": self.reconnect_interval},
            header=self.header,
            route="ws",
        )

    def test_init_url(self):
        """Test the URL of the created object
        """
        self.assertEqual(self.dakara_server.server_url, self.url)

    @patch.object(DakaraServerWebSocketConnection, "send_ready")
    def test_on_connected(self, mocked_send_ready):
        """Test the callback on connection open
        """
        # call the method
        self.dakara_server.on_connected()

        # assert the call
        mocked_send_ready.assert_called_once_with()

    @patch.object(DakaraServerWebSocketConnection, "create_timer")
    def test_on_connection_lost(self, mocked_create_timer):
        """Test the callback on connection lost
        """
        # mock the callback
        mocked_connection_lost = MagicMock()
        self.dakara_server.set_callback("connection_lost", mocked_connection_lost)

        # call the on_close callback
        with self.assertLogs("dakara_base.websocket_client", "DEBUG"):
            self.dakara_server.on_close(None, None)

        # assert the call
        mocked_connection_lost.assert_called_once_with()
        mocked_create_timer.assert_called_once_with(ANY, ANY)

    def test_receive_idle(self):
        """Test the receive idle event method
        """
        # mock the callback
        mocked_idle_callback = MagicMock()
        self.dakara_server.set_callback("idle", mocked_idle_callback)

        # call the method
        with self.assertLogs("dakara_player_vlc.dakara_server", "DEBUG") as logger:
            self.dakara_server.receive_idle({})

        # assert the effect on logs
        self.assertListEqual(
            logger.output, ["DEBUG:dakara_player_vlc.dakara_server:Received idle order"]
        )

        # assert the call
        mocked_idle_callback.assert_called_once_with()

    def test_receive_playlist_entry(self):
        """Test the receive new playlist entry event method
        """
        content = {"id": 0, "song": None}

        # mock the callback
        mocked_playlist_entry_callback = MagicMock()
        self.dakara_server.set_callback(
            "playlist_entry", mocked_playlist_entry_callback
        )

        # call the method
        with self.assertLogs("dakara_player_vlc.dakara_server", "DEBUG") as logger:
            self.dakara_server.receive_playlist_entry(content)

        # assert the effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.dakara_server:"
                "Received new playlist entry 0 order"
            ],
        )

        # assert the call
        mocked_playlist_entry_callback.assert_called_with(content)

    def test_receive_command(self):
        """Test the receive command event method
        """
        content = {"command": "command_value"}

        # mock the callback
        mocked_command_callback = MagicMock()
        self.dakara_server.set_callback("command", mocked_command_callback)

        # call the method
        with self.assertLogs("dakara_player_vlc.dakara_server", "DEBUG") as logger:
            self.dakara_server.receive_command(content)

        # assert the effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.dakara_server:"
                "Received command command_value order"
            ],
        )

        # assert the call
        mocked_command_callback.assert_called_with("command_value")

    @patch.object(DakaraServerWebSocketConnection, "send")
    def test_send_ready(self, mocked_send):
        """Test to notify the server that the player is ready
        """
        # call the command
        with self.assertLogs("dakara_player_vlc.dakara_server", "DEBUG") as logger:
            self.dakara_server.send_ready()

        # assert the effect on logs
        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player_vlc.dakara_server:"
                "Telling the server that the player is ready"
            ],
        )

        # assert the call
        mocked_send.assert_called_with({"type": "ready"})
