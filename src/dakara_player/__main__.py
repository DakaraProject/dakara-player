"""Command line interface to run the player."""

import logging
import sys
from argparse import ArgumentParser

from dakara_base.config import (
    Config,
    ConfigNotFoundError,
    create_config_file,
    create_logger,
    set_loglevel,
)
from dakara_base.directory import directories
from dakara_base.exceptions import (
    DakaraError,
    generate_exception_handler,
    handle_all_exceptions,
)
from dakara_base.http_client import ParameterError

from dakara_player.player import DakaraPlayer
from dakara_player.user_resources import create_resource_files
from dakara_player.version import __date__, __version__

CONFIG_FILE = "player.yaml"
CONFIG_PREFIX = "DAKARA"


logger = logging.getLogger(__name__)
handle_config_not_found = generate_exception_handler(
    ConfigNotFoundError, "Please run 'dakara-player create-config'"
)
handle_config_incomplete = generate_exception_handler(
    DakaraError,
    "Config may be incomplete, please check '{}'".format(
        directories.user_config_path / CONFIG_FILE
    ),
)
handle_parameter_error = generate_exception_handler(
    ParameterError,
    "Config may be incomplete, please check '{}'".format(
        directories.user_config_path / CONFIG_FILE
    ),
)


def get_parser():
    """Get a parser.

    Returns:
        argparse.ArgumentParser: Parser.
    """
    # main parser
    parser = ArgumentParser(
        prog="dakara-player", description="Player for the Dakara project"
    )

    parser.set_defaults(function=lambda _: parser.print_help())

    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="enable debug output, increase verbosity",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s {} ({})".format(__version__, __date__),
    )

    # subparsers
    subparser = parser.add_subparsers(title="subcommands")

    # play subparser
    play_subparser = subparser.add_parser(
        "play",
        description="Run the player",
        help="run the player",
    )
    play_subparser.set_defaults(function=play)

    # create config subparser
    create_config_subparser = subparser.add_parser(
        "create-config",
        description="Create a new config file in user directory",
        help="create a new config file in user directory",
    )
    create_config_subparser.set_defaults(function=create_config)

    create_config_subparser.add_argument(
        "--force",
        help="overwrite previous config file if it exists",
        action="store_true",
    )

    # create resources subparser
    create_resource_subparser = subparser.add_parser(
        "create-resources",
        description="Create resource files in user directory "
        "(for background screens, text templates)",
        help="create resource files in user directory",
    )
    create_resource_subparser.set_defaults(function=create_resources)

    create_resource_subparser.add_argument(
        "--force",
        help="overwrite existing files if any",
        action="store_true",
    )

    return parser


def play(args):
    """Run the player.

    Args:
        args (argparse.Namespace): Arguments from command line.
    """
    with handle_config_not_found():
        create_logger()
        config = Config(CONFIG_PREFIX)
        config.load_file(directories.user_config_path / CONFIG_FILE)
        config.check_mandatory_keys(["player", "server"])
        config.set_debug(args.debug)
        set_loglevel(config)

    dakara = DakaraPlayer(config)

    with handle_config_incomplete():
        dakara.load()

    # catch HTTP client missing credentials
    with handle_parameter_error():
        dakara.run()


def create_config(args):
    """Create the config file.

    Args:
        args (argparse.Namespace): Arguments from command line.
    """
    create_logger(custom_log_format="%(message)s", custom_log_level="INFO")
    create_config_file("dakara_player.resources", CONFIG_FILE, args.force)
    logger.info("Please edit this file")


def create_resources(args):
    """Create resource files.

    Args:
        args (argparse.Namespace): Arguments from command line.
    """
    create_logger(custom_log_format="%(message)s", custom_log_level="INFO")
    create_resource_files(args.force)
    logger.info("You can now customize those files")


def main():
    """Main command."""
    parser = get_parser()
    args = parser.parse_args()

    with handle_all_exceptions(
        bugtracker_url="https://github.com/DakaraProject/dakara-player/issues",
        logger=logger,
        debug=args.debug,
    ) as exit_value:
        args.function(args)

    sys.exit(exit_value.value)
