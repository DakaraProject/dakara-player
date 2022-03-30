from argparse import ArgumentParser, Namespace
from unittest import TestCase
from unittest.mock import ANY, MagicMock, patch

from dakara_base.config import Config
from dakara_base.exceptions import DakaraHandledError
from dakara_base.http_client import ParameterError

from dakara_player.__main__ import (
    create_config,
    create_resources,
    get_parser,
    main,
    play,
)


class GetParserTestCase(TestCase):
    """Test the parser creator."""

    def test(self):
        """Test a parser is created."""
        parser = get_parser()
        self.assertIsNotNone(parser)

    def test_play_function(self):
        """Test the parser calls play when prompted."""
        # call the function
        parser = get_parser()
        args = parser.parse_args(["play"])

        # check the function
        self.assertIs(args.function, play)

    def test_create_config_function(self):
        """Test the parser calls create_config when prompted."""
        # call the function
        parser = get_parser()
        args = parser.parse_args(["create-config"])

        # check the function
        self.assertIs(args.function, create_config)

    def test_create_resources_function(self):
        """Test the parser calls create_resources when prompted."""
        # call the function
        parser = get_parser()
        args = parser.parse_args(["create-resources"])

        # check the function
        self.assertIs(args.function, create_resources)


@patch("dakara_player.__main__.DakaraPlayer", autospec=True)
@patch("dakara_player.__main__.set_loglevel")
@patch.object(Config, "set_debug")
@patch.object(Config, "check_mandatory_keys")
@patch.object(Config, "load_file")
@patch("dakara_player.__main__.create_logger")
class PlayTestCase(TestCase):
    """Test the play action."""

    def test_play(
        self,
        mocked_create_logger,
        mocked_load_file,
        mocked_check_mandatory_keys,
        mocked_set_debug,
        mocked_set_loglevel,
        mocked_dakara_player_class,
    ):
        """Test the play command."""
        # call the function
        play(Namespace(debug=False))

        # assert the call
        mocked_create_logger.assert_called_with()
        mocked_load_file.assert_called_with(ANY)
        mocked_check_mandatory_keys.assert_called_with(["player", "server"])
        mocked_set_loglevel.assert_called_with(ANY)
        mocked_dakara_player_class.assert_called_with(ANY)
        mocked_dakara_player_class.return_value.load.assert_called_with()
        mocked_dakara_player_class.return_value.run.assert_called_with()

    def test_play_parameter_error(
        self,
        mocked_create_logger,
        mocked_load_file,
        mocked_check_mandatory_keys,
        mocked_set_debug,
        mocked_set_loglevel,
        mocked_dakara_player_class,
    ):
        """Test an error in HTTP server configuration."""
        # raise exception
        mocked_dakara_player_class.return_value.run.side_effect = ParameterError(
            "error message"
        )

        # call the function
        with self.assertRaisesRegex(ParameterError, "error message") as cm:
            play(Namespace(debug=False))

        self.assertIsInstance(cm.exception, ParameterError)
        self.assertIsInstance(cm.exception, DakaraHandledError)


@patch("dakara_player.__main__.create_logger")
@patch("dakara_player.__main__.create_config_file")
class CreateConfigTestCase(TestCase):
    """Test the create-config action."""

    def test_create_config(self, mocked_create_config_file, mocked_create_logger):
        """Test a simple create-config action."""
        # call the function
        with self.assertLogs("dakara_player.__main__") as logger:
            create_config(Namespace(force=False))

        # assert the logs
        self.assertListEqual(
            logger.output,
            ["INFO:dakara_player.__main__:Please edit this file"],
        )

        # assert the call
        mocked_create_logger.assert_called_with(
            custom_log_format=ANY, custom_log_level=ANY
        )
        mocked_create_config_file.assert_called_with(
            "dakara_player.resources", "player.yaml", False
        )


@patch("dakara_player.__main__.create_logger")
@patch("dakara_player.__main__.create_resource_files")
class CreateResourcesTestCase(TestCase):
    """Test the create-resources action."""

    def test_create_config(self, mocked_create_resource_files, mocked_create_logger):
        """Test a simple create-resources action."""
        # call the function
        with self.assertLogs("dakara_player.__main__") as logger:
            create_resources(Namespace(force=False))

        # assert the logs
        self.assertListEqual(
            logger.output,
            ["INFO:dakara_player.__main__:You can now customize those files"],
        )

        # assert the call
        mocked_create_logger.assert_called_with(
            custom_log_format=ANY, custom_log_level=ANY
        )
        mocked_create_resource_files.assert_called_with(False)


@patch("dakara_player.__main__.sys.exit")
@patch.object(ArgumentParser, "parse_args")
class MainTestCase(TestCase):
    """Test the main action."""

    def test_normal_exit(self, mocked_parse_args, mocked_exit):
        """Test a normal exit."""
        # create mocks
        function = MagicMock()
        mocked_parse_args.return_value = Namespace(function=function, debug=False)

        # call the function
        main()

        # assert the call
        function.assert_called_with(ANY)
        mocked_exit.assert_called_with(0)
