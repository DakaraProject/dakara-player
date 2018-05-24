#!/usr/bin/env python3
import logging
from argparse import ArgumentParser

from dakara_player_vlc.dakara_player_vlc import DakaraPlayerVlc


logger = logging.getLogger('dakara')


CONFIG_FILE_PATH = "config.yaml"


def get_parser():
    parser = ArgumentParser(
            description="Player for the Dakara project"
            )

    parser.add_argument(
            '-d',
            '--debug',
            action='store_true',
            help="enable debug output"
            )

    parser.add_argument(
            '--config',
            help="path to the config file, default: '{}'".format(
                CONFIG_FILE_PATH
                ),
            default=CONFIG_FILE_PATH
            )

    parser.set_defaults(func=runplayer)

    return parser


def runplayer(args):
    try:
        dakara = DakaraPlayerVlc(args.config)
        dakara.run()

    except Exception as error:
        if args.debug:
            raise

        logger.critical(error)
        exit(1)


if __name__ == '__main__':
    parser = get_parser()
    args = parser.parse_args()

    args.func(args)
