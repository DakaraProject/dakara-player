from copy import deepcopy
from queue import Queue
from threading import Event
from unittest import TestCase
from unittest.mock import ANY, patch

from dakara_player.dakara_player import (
    DakaraPlayer,
    DakaraWorker,
    UnsupportedMediaPlayerError,
)
from dakara_player.media_player.vlc import MediaPlayerVlc
from dakara_player.media_player.mpv import MediaPlayerMpv


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

    def test_init(self):
        """Test to create the object
        """
        stop = Event()
        errors = Queue()

        # create Dakara worker
        with self.assertLogs("dakara_player.dakara_player", "DEBUG") as logger:
            DakaraWorker(stop, errors, CONFIG)

        # assert effect on logs
        self.assertListEqual(
            logger.output, ["DEBUG:dakara_player.dakara_player:Starting Dakara worker"],
        )

    def test_get_media_player_class_vlc(self):
        """Test to get VLC as media player
        """
        stop = Event()
        errors = Queue()
        config = deepcopy(CONFIG)
        config["player"]["player_name"] = "Vlc"

        worker = DakaraWorker(stop, errors, config)
        media_player_class = worker.get_media_player_class()

        self.assertIs(media_player_class, MediaPlayerVlc)

    def test_get_media_player_class_mpv(self):
        """Test to get MPV as media player
        """
        stop = Event()
        errors = Queue()
        config = deepcopy(CONFIG)
        config["player"]["player_name"] = "Mpv"

        worker = DakaraWorker(stop, errors, config)
        media_player_class = worker.get_media_player_class()

        self.assertIs(media_player_class, MediaPlayerMpv.from_version)

    def test_get_media_player_class_default(self):
        """Test to get the default media player
        """
        stop = Event()
        errors = Queue()

        worker = DakaraWorker(stop, errors, CONFIG)
        media_player_class = worker.get_media_player_class()

        self.assertIs(media_player_class, MediaPlayerVlc)

    def test_get_media_player_class_unsupported(self):
        """Test to get an unsupported media player
        """
        stop = Event()
        errors = Queue()
        config = deepcopy(CONFIG)
        config["player"]["player_name"] = "Unknown"

        worker = DakaraWorker(stop, errors, config)

        with self.assertRaisesRegex(
            UnsupportedMediaPlayerError, "No media player for 'Unknown'"
        ):
            worker.get_media_player_class()

    @patch("dakara_player.dakara_player.TempDir", autospec=True)
    @patch("dakara_player.dakara_player.FontLoader", autospec=True)
    @patch("dakara_player.dakara_player.MediaPlayerVlc", autospec=True)
    @patch("dakara_player.dakara_player.DakaraServerHTTPConnection", autospec=True)
    @patch(
        "dakara_player.dakara_player.DakaraServerWebSocketConnection", autospec=True,
    )
    @patch("dakara_player.dakara_player.DakaraManager", autospec=True)
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

        # create safe worker control objects
        stop = Event()
        errors = Queue()

        # create Dakara worker
        dakara_worker = DakaraWorker(stop, errors, CONFIG)

        # set the stop event
        stop.set()

        # call the method
        with patch.dict(
            "dakara_player.dakara_player.MEDIA_PLAYER_CLASSES",
            {"vlc": mocked_vlc_player_class},
        ):
            dakara_worker.run()

        # assert the call
        mocked_temporary_directory_class.assert_called_with(suffix=".dakara")
        mocked_font_loader_class.assert_called_with()
        mocked_font_loader.load.assert_called_with()
        mocked_vlc_player_class.assert_called_with(stop, errors, CONFIG["player"], ANY)
        mocked_vlc_player.load.assert_called_with()
        mocked_dakara_server_http_class.assert_called_with(
            CONFIG["server"], endpoint_prefix="api/", mute_raise=True
        )
        mocked_dakara_server_http.authenticate.assert_called_with()
        mocked_dakara_server_http.get_token_header.assert_called_with()
        mocked_dakara_server_websocket_class.assert_called_with(
            stop,
            errors,
            CONFIG["server"],
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


class DakaraPlayerTestCase(TestCase):
    """Test the `DakaraPlayer` class
    """

    def test_init(self):
        """Test to create the object
        """
        with self.assertLogs("dakara_player.dakara_player", "DEBUG") as logger:
            DakaraPlayer(CONFIG)

        # assert effect on logs
        self.assertListEqual(
            logger.output, ["DEBUG:dakara_player.dakara_player:Started main"]
        )

    @patch("dakara_player.dakara_player.check_version")
    def test_load(self, mocked_check_version):
        """Test to perform side-effect actions
        """
        dakara_player = DakaraPlayer(CONFIG)
        dakara_player.load()

        # assert call
        mocked_check_version.assert_called_with()

    @patch.object(DakaraPlayer, "run_safe")
    def test_run(self, mocked_run_safe):
        """Test a dummy run
        """
        dakara_player = DakaraPlayer(CONFIG)
        dakara_player.run()

        # assert the call
        mocked_run_safe.assert_called_with(DakaraWorker, CONFIG)
