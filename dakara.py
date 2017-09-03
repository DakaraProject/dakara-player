#!/usr/bin/env python3
import logging
from argparse import ArgumentParser
from lib.dakara_player import DakaraPlayer


logger = logging.getLogger('dakara')


def get_parser():
    parser = ArgumentParser(
            description="Player for the Dakara project"
            )

    parser.add_argument(
            '-d',
            '--debug',
            action='store_true',
            help="Enable debug output"
            )

    return parser


if __name__ == '__main__':
    parser = get_parser()
    args = parser.parse_args()

    try:
        kara_player = DakaraPlayer()
        kara_player.deamon()

    except Exception as error:
        if args.debug:
            raise

        logger.critical(error)
