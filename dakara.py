#!/usr/bin/env python3
import logging
from argparse import ArgumentParser

from dakara_base.exceptions import DakaraError
from dakara_base.config import load_config, create_logger, set_loglevel
from path import Path

from dakara_player_vlc.dakara_player_vlc import DakaraPlayerVlc


CONFIG_FILE_PATH = "config.yaml"


logger = logging.getLogger(__name__)


def get_parser():
    """Get a parser

    Returns:
        argparse.ArgumentParser: parser.
    """
    parser = ArgumentParser(description="Player for the Dakara project")

    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="enable debug output, increase verbosity",
    )

    parser.add_argument(
        "--config",
        help="path to the config file, default: '{}'".format(CONFIG_FILE_PATH),
        default=CONFIG_FILE_PATH,
    )

    return parser


def runplayer(args):
    """Execute the player

    Args:
        args (argparse.Namespace): arguments from command line.
    """
    # prepare execution
    create_logger()
    config = load_config(Path(args.config), args.debug)
    set_loglevel(config)

    # run the player
    dakara = DakaraPlayerVlc(config)
    dakara.run()


if __name__ == "__main__":
    parser = get_parser()
    args = parser.parse_args()

    try:
        runplayer(args)

    except SystemExit:
        logger.info("Quit by system")
        exit(254)

    except DakaraError as error:
        if args.debug:
            raise

        logger.critical(error)
        exit(1)

    except BaseException as error:
        logger.exception("Unexpected error: %s", str(error))
        logger.critical(
            "Please fill a bug report at "
            "https://github.com/DakaraProject/dakara-playel-vlc/issues"
        )
        exit(128)

    exit(0)
