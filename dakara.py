#!/usr/bin/env python3
import logging
from argparse import ArgumentParser

from dakara_player_vlc.dakara_player_vlc import DakaraPlayerVlc
from dakara_player_vlc.tests import DakaraTestRunner


logger = logging.getLogger('dakara')


CONFIG_FILE_PATH = "config.ini"


def get_parser():
    parser = ArgumentParser(
            description="Player for the Dakara project"
            )

    subparsers = parser.add_subparsers()

    parser_runplayer = subparsers.add_parser(
            "runplayer",
            help="run the player"
            )

    parser_runplayer.add_argument(
            '-d',
            '--debug',
            action='store_true',
            help="enable debug output"
            )

    parser_runplayer.add_argument(
            '--config',
            help="path to the config file, default: '{}'".format(
                CONFIG_FILE_PATH
                ),
            default=CONFIG_FILE_PATH
            )

    parser_runplayer.set_defaults(func=runplayer)

    parser_test = subparsers.add_parser(
            "test",
            help="test the player"
            )

    parser_test.add_argument(
            'target',
            nargs='?',
            help="select which test to run",
            default=None
            )

    parser_test.set_defaults(func=test)

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


def test(args):
    dakara_test_runner = DakaraTestRunner(args.target)
    dakara_test_runner.run()


if __name__ == '__main__':
    parser = get_parser()
    args = parser.parse_args()

    args.func(args)
