#!/usr/bin/env python3
import logging
from argparse import ArgumentParser
from dakara_player_vlc.dakara_player_vlc import DakaraPlayerVlc


logger = logging.getLogger('dakara')


CONFIG_FILE_PATH = "config.ini"


def get_parser():
    parser = ArgumentParser(
            description="Player for the Dakara project"
            )

    parser.add_argument(
            '-d',
            '--debug',
            action='store_true',
            help="Enable debug output."
            )

    parser.add_argument(
            '--config',
            help="Path to the config file. Default: '{}'".format(CONFIG_FILE_PATH),
            default=CONFIG_FILE_PATH
            )

    return parser


if __name__ == '__main__':
    parser = get_parser()
    args = parser.parse_args()

    try:
        dakara = DakaraPlayerVlc(
                args.config
                )

        dakara.run()

    except Exception as error:
        if args.debug:
            raise

        logger.critical(error)
        exit(1)
