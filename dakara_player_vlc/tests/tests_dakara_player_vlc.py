from unittest import TestCase
from unittest.mock import patch, ANY, MagicMock
from threading import Event
from queue import Queue
import logging

from yaml.parser import ParserError

from dakara_player_vlc.resources_manager import get_test_material
from dakara_player_vlc.dakara_player_vlc import DakaraWorker, DakaraPlayerVlc


class DakaraWorkerTestCase(TestCase):
    """Test the `DakaraWorker` class
    """

    def setUp(self):
        # save config path
        self.config_path = get_test_material("config.yaml")

        # save instances
        self.stop = Event()
        self.errors = Queue()
        self.dakara_worker = DakaraWorker(self.stop, self.errors,
                                          self.config_path, False)

        # save config
        self.config = self.dakara_worker.config

    def test_load_config_success(self):
        """Test to load the config file
        """
        config = DakaraWorker.load_config(self.config_path, False)

        # assert the result
        self.assertTrue(config)
        self.assertNotEqual(config['loglevel'].lower(), 'debug')

    def test_load_config_success_debug(self):
        """Test to load the config file with debug mode enabled
        """
        config = DakaraWorker.load_config(self.config_path, True)

        # assert the result
        self.assertEqual(config['loglevel'].lower(), 'debug')

    def test_load_config_fail_not_found(self):
        """Test to load a not found config file
        """
        with self.assertRaises(IOError):
            DakaraWorker.load_config('nowhere', False)

    @patch('dakara_player_vlc.dakara_player_vlc.yaml.load')
    def test_load_config_fail_parser_error(self, mock_load):
        """Test to load an invalid config file
        """
        # mock the call to yaml
        mock_load.side_effect = ParserError("parser error")

        # call the method
        with self.assertRaises(IOError):
            DakaraWorker.load_config(self.config_path, False)

        # assert the call
        mock_load.assert_called_with(ANY)

    @patch('dakara_player_vlc.dakara_player_vlc.yaml.load')
    def test_load_config_fail_missing_keys(self, mock_load):
        """Test to load a config file without required keys
        """
        for key in ('player', 'server'):
            config = self.config.copy()
            config.pop(key)

            # mock the call to yaml
            mock_load.return_value = config

            # call the method
            with self.assertRaises(ValueError) as error:
                DakaraWorker.load_config(self.config_path, False)
                self.assertIn(key, str(error))

    @patch('dakara_player_vlc.dakara_player_vlc.coloredlogs.set_level')
    def test_configure_logger_success(self, mock_set_level):
        """Test to configure the logger
        """
        # set the loglevel
        self.dakara_worker.config['loglevel'] = 'debug'

        # call the method
        self.dakara_worker.configure_logger()

        # assert the result
        mock_set_level.assert_called_with(logging.DEBUG)

    def test_configure_logger_fail(self):
        """Test to configure the logger with invalid log level
        """
        # set the loglevel
        self.dakara_worker.config['loglevel'] = 'nothing'

        # call the method
        with self.assertRaises(ValueError):
            self.dakara_worker.configure_logger()

    @patch('dakara_player_vlc.dakara_player_vlc.TemporaryDirectory')
    @patch('dakara_player_vlc.dakara_player_vlc.FontLoader')
    @patch('dakara_player_vlc.dakara_player_vlc.TextGenerator')
    @patch('dakara_player_vlc.dakara_player_vlc.VlcPlayer')
    @patch('dakara_player_vlc.dakara_player_vlc.DakaraServerHTTPConnection')
    @patch('dakara_player_vlc.dakara_player_vlc'
           '.DakaraServerWebSocketConnection')
    @patch('dakara_player_vlc.dakara_player_vlc.DakaraManager')
    def test_run(self, mock_dakara_manager_class,
                 mock_dakara_server_websocket_class,
                 mock_dakara_server_http_class,
                 mock_vlc_player_class, mock_text_generator_class,
                 mock_font_loader_class, mock_temporary_directory_class):
        """Test a dummy run
        """
        # create mock instances
        mock_dakara_server_websocket = mock_dakara_server_websocket_class\
            .return_value.__enter__.return_value
        mock_dakara_server_http = mock_dakara_server_http_class.return_value
        mock_dakara_server_http.get_token_header.return_value = 'token'
        mock_vlc_player = mock_vlc_player_class.return_value.__enter__\
            .return_value
        mock_text_generator = mock_text_generator_class.return_value
        mock_font_loader = mock_font_loader_class.return_value\
            .__enter__.return_value

        # set the stop event
        self.stop.set()

        # call the method
        self.dakara_worker.run()

        # assert the call
        mock_temporary_directory_class.assert_called_with(suffix='.dakara')
        mock_font_loader_class.assert_called_with()
        mock_font_loader.load.assert_called_with()
        mock_text_generator_class.assert_called_with({}, ANY)
        mock_vlc_player_class.assert_called_with(self.stop, self.errors,
                                                 self.config['player'],
                                                 mock_text_generator)
        mock_dakara_server_http_class.assert_called_with(self.config['server'])
        mock_dakara_server_http.authenticate.assert_called_with()
        mock_dakara_server_http.get_token_header.assert_called_with()
        mock_dakara_server_websocket_class.assert_called_with(
            self.stop, self.errors, self.config['server'], 'token')
        mock_dakara_server_websocket.create_connection.assert_called_with()
        mock_dakara_manager_class.assert_called_with(
            mock_font_loader, mock_vlc_player, mock_dakara_server_websocket)
        mock_dakara_server_websocket.thread.start.assert_called_with()


class DakaraPlayerVlcTestCase(TestCase):
    """Test the `DakaraPlayerVlc` class
    """

    def setUp(self):
        # save config path
        self.config_path = get_test_material("config.yaml")

        # save instance
        self.dakara_player_vlc = DakaraPlayerVlc(self.config_path, False)

    def test_run(self):
        """Test a dummy run
        """
        # patch the `run_safe` method
        self.dakara_player_vlc.run_safe = MagicMock()

        # call the method
        self.dakara_player_vlc.run()

        # assert the call
        self.dakara_player_vlc.run_safe.assert_called_with(
            DakaraWorker, self.config_path, False
        )
