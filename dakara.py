#!/usr/bin/env python3
import logging
from argparse import ArgumentParser

import coloredlogs

from dakara_player_vlc.dakara_player_vlc import DakaraPlayerVlc


logger = logging.getLogger('dakara')


CONFIG_FILE_PATH = "config.yaml"


# tweak colors for coloredlogs and install it
field_styles = coloredlogs.DEFAULT_FIELD_STYLES.copy()
field_styles['levelname'] = {
    'color': 'white',
    'bold': True,
}
coloredlogs.install(
    fmt='[%(asctime)s] %(name)s %(levelname)s %(message)s',
    field_styles=field_styles
)


def get_parser():
    parser = ArgumentParser(
        description="Player for the Dakara project"
    )

    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        help="enable debug output, increase verbosity"
    )

    parser.add_argument(
        '--config',
        help="path to the config file, default: '{}'".format(CONFIG_FILE_PATH),
        default=CONFIG_FILE_PATH
    )

    return parser


def runplayer(args):
    try:
        dakara = DakaraPlayerVlc(args.config, args.debug)
        dakara.run()

    except BaseException as error:
        if args.debug:
            raise

        logger.critical(error)
        exit(1)


if __name__ == '__main__':
    parser = get_parser()
    args = parser.parse_args()

    runplayer(args)
