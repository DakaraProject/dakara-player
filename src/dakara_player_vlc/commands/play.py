#!/usr/bin/env python3
import logging
from argparse import ArgumentParser

from dakara_base.exceptions import DakaraError

# TODO reactivate with dakarabase 1.2.0
# get_config_file,
# create_config_file,
from dakara_base.config import load_config, create_logger, set_loglevel
from path import Path

from dakara_player_vlc import DakaraPlayerVlc
from dakara_player_vlc.version import __version__, __date__


CONFIG_FILE = "player_vlc.yaml"


logger = logging.getLogger(__name__)


def get_config_file(filename):
    """Temporary
    """
    # TODO remove with dakarabase 1.2.0
    return Path(".") / filename


def create_config_file(resource, filename, force=False):
    """Temporary
    """
    # TODO remove with dakarabase 1.2.0


def get_parser():
    """Get a parser

    Returns:
        argparse.ArgumentParser: parser.
    """
    # main parser
    parser = ArgumentParser(
        prog="play-vlc", description="VLC based player for the Dakara project"
    )

    parser.set_defaults(function=play)

    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="enable debug output, increase verbosity",
    )

    parser.add_argument(
        "--config",
        help="path to the config file, default: '{}'".format(
            get_config_file(CONFIG_FILE)
        ),
        default=get_config_file(CONFIG_FILE),
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
        "create-config", help="Create a new config file in user directory"
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
    # prepare execution
    create_logger()
    config = load_config(
        Path(args.config), args.debug, mandatory_keys=["player", "server"]
    )
    set_loglevel(config)

    # run the player
    dakara = DakaraPlayerVlc(config)
    dakara.load()
    dakara.run()


def create_config(args):
    """Create the config

    Args:
        args (argparse.Namespace): arguments from command line.
    """
    create_config_file("dakara_player_vlc.resources", CONFIG_FILE, args.force)


def main():
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
            "https://github.com/DakaraProject/dakara-player-vlc/issues"
        )
        value = 128

    exit(value)


if __name__ == "__main__":
    main()
