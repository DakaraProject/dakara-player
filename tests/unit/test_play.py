from argparse import ArgumentParser, Namespace
from unittest import TestCase
from unittest.mock import ANY, MagicMock, patch

from dakara_base.config import ConfigNotFoundError
from dakara_base.exceptions import DakaraError
from path import Path

from dakara_player import DakaraPlayer
from dakara_player.commands import play


class GetParserTestCase(TestCase):
    """Test the parser creator
    """

    def test(self):
        """Test a parser is created
        """
        parser = play.get_parser()
        self.assertIsNotNone(parser)

    def test_main_function(self):
        """Test the parser calls play by default
        """
        # call the function
        parser = play.get_parser()
        args = parser.parse_args([])

        # check the function
        self.assertIs(args.function, play.play)

    def test_create_config_function(self):
        """Test the parser calls create_config when prompted
        """
        # call the function
        parser = play.get_parser()
        args = parser.parse_args(["create-config"])

        # check the function
        self.assertIs(args.function, play.create_config)


class PlayTestCase(TestCase):
    """Test the play action
    """

    @patch.object(DakaraPlayer, "run")
    @patch.object(DakaraPlayer, "load")
    @patch("dakara_player.commands.play.load_config")
    @patch("dakara_player.commands.play.get_config_file")
    @patch("dakara_player.commands.play.create_logger")
    def test_play_config_not_found(
        self,
        mocked_create_logger,
        mocked_get_config_file,
        mocked_load_config,
        mocked_load,
        mocked_run,
    ):
        """Test when config file is not found
        """
        # create the mocks
        mocked_get_config_file.return_value = Path("path") / "to" / "config"
        mocked_load_config.side_effect = ConfigNotFoundError("Config file not found")

        # call the function
        with self.assertRaisesRegex(
            ConfigNotFoundError,
            "Config file not found, please run 'dakara-play create-config'",
        ):
            play.play(Namespace(debug=False, force=False, progress=True))

        # assert the call
        mocked_load.assert_not_called()
        mocked_run.assert_not_called()

    @patch.object(DakaraPlayer, "run")
    @patch.object(DakaraPlayer, "load")
    @patch("dakara_player.commands.play.set_loglevel")
    @patch("dakara_player.commands.play.load_config")
    @patch("dakara_player.commands.play.get_config_file")
    @patch("dakara_player.commands.play.create_logger")
    def test_play_config_incomplete(
        self,
        mocked_create_logger,
        mocked_get_config_file,
        mocked_load_config,
        mocked_set_loglevel,
        mocked_load,
        mocked_run,
    ):
        """Test when config file is incomplete
        """
        # create the mocks
        mocked_get_config_file.return_value = Path("path") / "to" / "config"
        mocked_load.side_effect = DakaraError("Config-related error")
        config = {
            "player": {"kara_folder": Path("path") / "to" / "folder"},
            "server": {
                "url": "www.example.com",
                "login": "login",
                "password": "password",
            },
        }
        mocked_load_config.return_value = config

        # call the function
        with self.assertRaisesRegex(DakaraError, "Config-related error"):
            with self.assertLogs("dakara_player.commands.play") as logger:
                play.play(Namespace(debug=False, force=False, progress=True))

        # assert the logs
        self.assertListEqual(
            logger.output,
            [
                "WARNING:dakara_player.commands.play:Config may be incomplete, "
                "please check '{}'".format(Path("path") / "to" / "config")
            ],
        )

        # assert the call
        mocked_load.assert_called_with()
        mocked_run.assert_not_called()

    @patch.object(DakaraPlayer, "load")
    @patch.object(DakaraPlayer, "run")
    @patch("dakara_player.commands.play.set_loglevel")
    @patch("dakara_player.commands.play.load_config")
    @patch("dakara_player.commands.play.get_config_file")
    @patch("dakara_player.commands.play.create_logger")
    def test_play(
        self,
        mocked_create_logger,
        mocked_get_config_file,
        mocked_load_config,
        mocked_set_loglevel,
        mocked_run,
        mocked_load,
    ):
        """Test a simple play action
        """
        # setup the mocks
        mocked_get_config_file.return_value = Path("path") / "to" / "config"
        config = {
            "player": {"kara_folder": Path("path") / "to" / "folder"},
            "server": {
                "url": "www.example.com",
                "login": "login",
                "password": "password",
            },
        }
        mocked_load_config.return_value = config

        # call the function
        play.play(Namespace(debug=False))

        # assert the call
        mocked_create_logger.assert_called_with()
        mocked_load_config.assert_called_with(
            Path("path") / "to" / "config", False, mandatory_keys=["player", "server"]
        )
        mocked_set_loglevel.assert_called_with(config)
        mocked_load.assert_called_with()
        mocked_run.assert_called_with()


class CreateConfigTestCase(TestCase):
    """Test the create-config action
    """

    @patch("dakara_player.commands.play.create_logger")
    @patch("dakara_player.commands.play.create_config_file")
    def test_create_config(self, mocked_create_config_file, mocked_create_logger):
        """Test a simple create-config action
        """
        # call the function
        with self.assertLogs("dakara_player.commands.play") as logger:
            play.create_config(Namespace(force=False))

        # assert the logs
        self.assertListEqual(
            logger.output, ["INFO:dakara_player.commands.play:Please edit this file"],
        )

        # assert the call
        mocked_create_logger.assert_called_with(
            custom_log_format=ANY, custom_log_level=ANY
        )
        mocked_create_config_file.assert_called_with(
            "dakara_player.resources", "player.yaml", False
        )


@patch("dakara_player.commands.play.exit")
@patch.object(ArgumentParser, "parse_args")
class MainTestCase(TestCase):
    """Test the main action
    """

    def test_normal_exit(self, mocked_parse_args, mocked_exit):
        """Test a normal exit
        """
        # create mocks
        function = MagicMock()
        mocked_parse_args.return_value = Namespace(function=function, debug=False)

        # call the function
        play.main()

        # assert the call
        function.assert_called_with(ANY)
        mocked_exit.assert_called_with(0)

    def test_known_error(self, mocked_parse_args, mocked_exit):
        """Test a known error exit
        """
        # create mocks
        def function(args):
            raise DakaraError("error")

        mocked_parse_args.return_value = Namespace(function=function, debug=False)

        # call the function
        with self.assertLogs("dakara_player.commands.play", "DEBUG") as logger:
            play.main()

        # assert the call
        mocked_exit.assert_called_with(1)

        # assert the logs
        self.assertListEqual(
            logger.output, ["CRITICAL:dakara_player.commands.play:error"]
        )

    def test_known_error_debug(self, mocked_parse_args, mocked_exit):
        """Test a known error exit in debug mode
        """
        # create mocks
        def function(args):
            raise DakaraError("error message")

        mocked_parse_args.return_value = Namespace(function=function, debug=True)

        # call the function
        with self.assertRaisesRegex(DakaraError, "error message"):
            play.main()

        # assert the call
        mocked_exit.assert_not_called()

    def test_unknown_error(self, mocked_parse_args, mocked_exit):
        """Test an unknown error exit
        """
        # create mocks
        def function(args):
            raise Exception("error")

        mocked_parse_args.return_value = Namespace(function=function, debug=False)

        # call the function
        with self.assertLogs("dakara_player.commands.play", "DEBUG") as logger:
            play.main()

        # assert the call
        mocked_exit.assert_called_with(128)

        # assert the logs
        self.assertListEqual(
            logger.output,
            [
                ANY,
                "CRITICAL:dakara_player.commands.play:Please fill a bug report at "
                "https://github.com/DakaraProject/dakara-player/issues",
            ],
        )

    def test_unknown_error_debug(self, mocked_parse_args, mocked_exit):
        """Test an unknown error exit in debug mode
        """
        # create mocks
        def function(args):
            raise Exception("error message")

        mocked_parse_args.return_value = Namespace(function=function, debug=True)

        # call the function
        with self.assertRaisesRegex(Exception, "error message"):
            play.main()

        # assert the call
        mocked_exit.assert_not_called()
