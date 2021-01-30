import logging
from argparse import ArgumentParser

from dakara_base.exceptions import DakaraError
from dakara_base.config import (
    ConfigNotFoundError,
    create_config_file,
    create_logger,
    get_config_file,
    load_config,
    set_loglevel,
)

from dakara_player import DakaraPlayer
from dakara_player.version import __version__, __date__


CONFIG_FILE = "player.yaml"


logger = logging.getLogger(__name__)


def get_parser():
    """Get a parser

    Returns:
        argparse.ArgumentParser: parser.
    """
    # main parser
    parser = ArgumentParser(
        prog="dakara-play", description="Player for the Dakara project"
    )

    parser.set_defaults(function=play)

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
    subparsers = parser.add_subparsers(title="subcommands")

    # create config subparser
    create_config_subparser = subparsers.add_parser(
        "create-config",
        description="Create a new config file in user directory",
        help="Create a new config file in user directory",
    )
    create_config_subparser.set_defaults(function=create_config)

    create_config_subparser.add_argument(
        "--force",
        help="overwrite previous config file if it exists",
        action="store_true",
    )

    return parser


def play(args):
    """Execute the player

    Args:
        args (argparse.Namespace): arguments from command line.
    """
    create_logger()

    # load the config, display help to create config if it fails
    try:
        config = load_config(
            get_config_file(CONFIG_FILE),
            args.debug,
            mandatory_keys=["player", "server"],
        )

    except ConfigNotFoundError as error:
        raise ConfigNotFoundError(
            "{}, please run 'dakara-play create-config'".format(error)
        ) from error

    set_loglevel(config)
    dakara = DakaraPlayer(config)

    # load the feeder, consider that the config is incomplete if it fails
    try:
        dakara.load()

    except DakaraError:
        logger.warning(
            "Config may be incomplete, please check '{}'".format(
                get_config_file(CONFIG_FILE)
            )
        )
        raise

    # run the player
    dakara.run()


def create_config(args):
    """Create the config

    Args:
        args (argparse.Namespace): arguments from command line.
    """
    create_logger(custom_log_format="%(message)s", custom_log_level="INFO")
    create_config_file("dakara_player.resources", CONFIG_FILE, args.force)
    logger.info("Please edit this file")


def main():
    """Main command
    """
    parser = get_parser()
    args = parser.parse_args()

    try:
        args.function(args)
        value = 0

    except DakaraError as error:
        if args.debug:
            raise

        logger.critical(error)
        value = 1

    except BaseException as error:
        if args.debug:
            raise

        logger.exception("Unexpected error: %s", str(error))
        logger.critical(
            "Please fill a bug report at "
            "https://github.com/DakaraProject/dakara-player/issues"
        )
        value = 128

    exit(value)
