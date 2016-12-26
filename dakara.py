#!/usr/bin/env python3
import logging
from lib.dakara_player import DakaraPlayer


if __name__ == '__main__':
    try:
        kara_player = DakaraPlayer()
        kara_player.deamon()

    except Exception as error:
        # if the error was raised after the constructor call,
        # display the exception with backtrace in debug mode,
        # or display the error message only in any other mode
        try:
            if kara_player.loglevel == 'DEBUG':
                kara_player.logger.exception(error)

            else:
                kara_player.logger.critical(error)

        # if the error was raised during the conscructor call,
        # just display the error message only in the root logger
        except:
            logging.critical(error)
