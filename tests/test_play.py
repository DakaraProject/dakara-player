from argparse import ArgumentParser, Namespace
from unittest import TestCase
from unittest.mock import ANY, MagicMock, patch

from dakara_base.exceptions import DakaraError
from path import Path

from dakara_player_vlc import DakaraPlayerVlc
from dakara_player_vlc.commands import play


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

    @patch.object(DakaraPlayerVlc, "run")
    @patch("dakara_player_vlc.commands.play.set_loglevel")
    @patch("dakara_player_vlc.commands.play.load_config")
    @patch("dakara_player_vlc.commands.play.create_logger")
    def test_play(
        self, mocked_create_logger, mocked_load_config, mocked_set_loglevel, mocked_run
    ):
        """Test a simple play action
        """
        # setup the mocks
        config = {
            "player": {"kara_folder": Path("path/to/folder")},
            "server": {
                "url": "www.example.com",
                "login": "login",
                "password": "password",
            },
        }
        mocked_load_config.return_value = config

        # call the function
        play.play(Namespace(config="player_vlc.yaml", debug=False))

        # assert the call
        mocked_create_logger.assert_called_with()
        mocked_load_config.assert_called_with(
            Path("player_vlc.yaml"), False, mandatory_keys=["player", "server"]
        )
        mocked_set_loglevel.assert_called_with(config)
        mocked_run.assert_called_with()


class CreateConfigTestCase(TestCase):
    """Test the create-config action
    """

    @patch("dakara_player_vlc.commands.play.create_config_file")
    def test_create_config(self, mocked_create_config_file):
        """Test a simple create-config action
        """
        # call the function
        play.create_config(Namespace(force=False))

        # assert the call
        mocked_create_config_file.assert_called_with(
            "dakara_player_vlc.resources", "player_vlc.yaml", False
        )


@patch("dakara_player_vlc.commands.play.exit")
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
        with self.assertLogs("dakara_player_vlc.commands.play", "DEBUG") as logger:
            play.main()

        # assert the call
        mocked_exit.assert_called_with(1)

        # assert the logs
        self.assertListEqual(
            logger.output, ["CRITICAL:dakara_player_vlc.commands.play:error"]
        )

    def test_known_error_debug(self, mocked_parse_args, mocked_exit):
        """Test a known error exit in debug mode
        """
        # create mocks
        def function(args):
            raise DakaraError("error")

        mocked_parse_args.return_value = Namespace(function=function, debug=True)

        # call the function
        with self.assertRaises(DakaraError) as error:
            play.main()

        # assert the call
        mocked_exit.assert_not_called()

        # assert the error
        self.assertEqual(str(error.exception), "error")

    def test_unknown_error(self, mocked_parse_args, mocked_exit):
        """Test an unknown error exit
        """
        # create mocks
        def function(args):
            raise Exception("error")

        mocked_parse_args.return_value = Namespace(function=function, debug=False)

        # call the function
        with self.assertLogs("dakara_player_vlc.commands.play", "DEBUG") as logger:
            play.main()

        # assert the call
        mocked_exit.assert_called_with(128)

        # assert the logs
        self.assertListEqual(
            logger.output,
            [
                ANY,
                "CRITICAL:dakara_player_vlc.commands.play:Please fill a bug report at "
                "https://github.com/DakaraProject/dakara-player-vlc/issues",
            ],
        )

    def test_unknown_error_debug(self, mocked_parse_args, mocked_exit):
        """Test an unknown error exit in debug mode
        """
        # create mocks
        def function(args):
            raise Exception("error")

        mocked_parse_args.return_value = Namespace(function=function, debug=True)

        # call the function
        with self.assertRaises(Exception) as error:
            play.main()

        # assert the call
        mocked_exit.assert_not_called()

        # assert the error
        self.assertEqual(str(error.exception), "error")
