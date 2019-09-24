from unittest import TestCase
from unittest.mock import patch, ANY
from threading import Event
from queue import Queue

from dakara_player_vlc.dakara_player_vlc import DakaraWorker, DakaraPlayerVlc


CONFIG = {
    "player": {
        "kara_folder": "/some/path",
        "fullscreen": True,
        "vlc": {"media_parameters": None, "instance_parameters": None},
        "templates": None,
        "backgrounds": None,
        "durations": None,
    },
    "server": {
        "address": "www.example.com",
        "login": "player_login",
        "password": "player_password",
        "ssl": True,
        "reconnect_interval": 10,
    },
    "loglevel": "info",
}


class DakaraWorkerTestCase(TestCase):
    """Test the `DakaraWorker` class
    """

    def setUp(self):
        # save config
        self.config = CONFIG

        # save instances
        self.stop = Event()
        self.errors = Queue()

        # create Dakara worker
        with self.assertLogs("dakara_player_vlc.dakara_player_vlc", "DEBUG"):
            self.dakara_worker = DakaraWorker(self.stop, self.errors, self.config)

    def test_check_version_release(self):
        """Test to display the version for a release
        """
        with self.assertLogs("dakara_player_vlc.dakara_player_vlc", "DEBUG") as logger:
            with patch.multiple(
                "dakara_player_vlc.dakara_player_vlc",
                __version__="0.0.0",
                __date__="1970-01-01",
            ):
                self.dakara_worker.check_version()

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "INFO:dakara_player_vlc.dakara_player_vlc:"
                "Dakara player 0.0.0 (1970-01-01)"
            ],
        )

    def test_check_version_non_release(self):
        """Test to display the version for a non release
        """
        with self.assertLogs("dakara_player_vlc.dakara_player_vlc", "DEBUG") as logger:
            with patch.multiple(
                "dakara_player_vlc.dakara_player_vlc",
                __version__="0.1.0-dev",
                __date__="1970-01-01",
            ):
                self.dakara_worker.check_version()

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "INFO:dakara_player_vlc.dakara_player_vlc:"
                "Dakara player 0.1.0-dev (1970-01-01)",
                "WARNING:dakara_player_vlc.dakara_player_vlc:"
                "You are running a dev version, use it at your own risks!",
            ],
        )

    @patch("dakara_player_vlc.dakara_player_vlc.TemporaryDirectory")
    @patch("dakara_player_vlc.dakara_player_vlc.FontLoader")
    @patch("dakara_player_vlc.dakara_player_vlc.VlcPlayer")
    @patch("dakara_player_vlc.dakara_player_vlc.DakaraServerHTTPConnection")
    @patch("dakara_player_vlc.dakara_player_vlc.DakaraServerWebSocketConnection")
    @patch("dakara_player_vlc.dakara_player_vlc.DakaraManager")
    def test_run(
        self,
        mocked_dakara_manager_class,
        mocked_dakara_server_websocket_class,
        mocked_dakara_server_http_class,
        mocked_vlc_player_class,
        mocked_font_loader_class,
        mocked_temporary_directory_class,
    ):
        """Test a dummy run
        """
        # create mock instances
        mocked_dakara_server_websocket = (
            mocked_dakara_server_websocket_class.return_value.__enter__.return_value
        )
        mocked_dakara_server_http = mocked_dakara_server_http_class.return_value
        mocked_dakara_server_http.get_token_header.return_value = "token"
        mocked_vlc_player = mocked_vlc_player_class.return_value.__enter__.return_value
        mocked_font_loader = (
            mocked_font_loader_class.return_value.__enter__.return_value
        )

        # set the stop event
        self.stop.set()

        # call the method
        self.dakara_worker.run()

        # assert the call
        mocked_temporary_directory_class.assert_called_with(suffix=".dakara")
        mocked_font_loader_class.assert_called_with()
        mocked_font_loader.load.assert_called_with()
        mocked_vlc_player_class.assert_called_with(
            self.stop, self.errors, self.config["player"], ANY
        )
        mocked_vlc_player.load.assert_called_with()
        mocked_dakara_server_http_class.assert_called_with(
            self.config["server"], endpoint="api/", mute_raise=True
        )
        mocked_dakara_server_http.authenticate.assert_called_with()
        mocked_dakara_server_http.get_token_header.assert_called_with()
        mocked_dakara_server_websocket_class.assert_called_with(
            self.stop,
            self.errors,
            self.config["server"],
            header="token",
            endpoint="ws/playlist/device/",
        )
        mocked_dakara_manager_class.assert_called_with(
            mocked_font_loader,
            mocked_vlc_player,
            mocked_dakara_server_http,
            mocked_dakara_server_websocket,
        )
        mocked_dakara_server_websocket.timer.start.assert_called_with()


class DakaraPlayerVlcTestCase(TestCase):
    """Test the `DakaraPlayerVlc` class
    """

    def setUp(self):
        # save config
        self.config = CONFIG

        # save instance
        with self.assertLogs("dakara_player_vlc.dakara_player_vlc", "DEBUG"):
            self.dakara_player_vlc = DakaraPlayerVlc(self.config)

    @patch.object(DakaraPlayerVlc, "run_safe")
    def test_run(self, mocked_run_safe):
        """Test a dummy run
        """
        # call the method
        self.dakara_player_vlc.run()

        # assert the call
        self.dakara_player_vlc.run_safe.assert_called_with(DakaraWorker, self.config)
