from queue import Queue
from threading import Event
from unittest import TestCase
from unittest.mock import ANY, patch

from dakara_player_vlc.dakara_player_vlc import DakaraPlayerVlc, DakaraWorker


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

    @patch("dakara_player_vlc.dakara_player_vlc.TemporaryDirectory", autospec=True)
    @patch("dakara_player_vlc.dakara_player_vlc.FontLoader", autospec=True)
    @patch("dakara_player_vlc.dakara_player_vlc.VlcPlayer", autospec=True)
    @patch(
        "dakara_player_vlc.dakara_player_vlc.DakaraServerHTTPConnection", autospec=True
    )
    @patch(
        "dakara_player_vlc.dakara_player_vlc.DakaraServerWebSocketConnection",
        autospec=True,
    )
    @patch("dakara_player_vlc.dakara_player_vlc.DakaraManager", autospec=True)
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
            self.config["server"], endpoint_prefix="api/", mute_raise=True
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

    def test_init(self):
        """Test to create the object
        """
        with self.assertLogs("dakara_player_vlc.dakara_player_vlc", "DEBUG") as logger:
            DakaraPlayerVlc(CONFIG)

        # assert effect on logs
        self.assertListEqual(
            logger.output, ["DEBUG:dakara_player_vlc.dakara_player_vlc:Started main"]
        )

    @patch("dakara_player_vlc.dakara_player_vlc.check_version")
    def test_load(self, mocked_check_version):
        """Test to perform side-effect actions
        """
        dakara_player_vlc = DakaraPlayerVlc(CONFIG)
        dakara_player_vlc.load()

        # assert call
        mocked_check_version.assert_called_with()

    @patch.object(DakaraPlayerVlc, "run_safe")
    def test_run(self, mocked_run_safe):
        """Test a dummy run
        """
        dakara_player_vlc = DakaraPlayerVlc(CONFIG)
        dakara_player_vlc.run()

        # assert the call
        mocked_run_safe.assert_called_with(DakaraWorker, CONFIG)
