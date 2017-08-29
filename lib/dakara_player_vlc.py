import os
import logging
from threading import Event, Thread
from configparser import ConfigParser
from tempfile import TemporaryDirectory

import coloredlogs

from .daemon import DaemonMaster, stop_on_error
from .text_generator import TextGenerator
from .vlc_player import VlcPlayer
from .dakara_server import DakaraServer
from .dakara_manager import DakaraManager
from .font_loader import get_font_loader_class
FontLoader = get_font_loader_class()


LOGLEVEL = 'INFO'


logger = logging.getLogger("dakara_player_vlc")


coloredlogs.install(
        fmt='[%(asctime)s] %(name)s %(levelname)s %(message)s',
        level=LOGLEVEL
        )


CONFIG_FILE_PATH = "config.ini"


class DakaraPlayerVlc:
    def __init__(self):
        logger.debug("Starting main")
        # create stop event
        self.stop = Event()

    def run(self):
        # create daemon thread
        with DakaraDaemon(self.stop) as daemon:
            error = False
            try:
                logger.debug("Create daemon thread")
                daemon_thread = Thread(target=daemon.run)
                daemon_thread.start()

                # wait for stop event
                logger.debug("Waiting for stop event")
                while not self.stop.wait(1):
                    pass

            # stop on Ctrl+C
            except KeyboardInterrupt:
                logger.debug("User stop caught")
                self.stop.set()

            # stop on error
            else:
                logger.debug("Internal error caught")
                error = True

            # wait for daemon thread to finish
            finally:
                daemon_thread.join()

            return error


class DakaraDaemon(DaemonMaster):
    def init_master(self):
        logger.debug("Starting daemon")

        # load config
        self.config = self.load_config(CONFIG_FILE_PATH)

        # configure loader
        self.configure_logger()

    @stop_on_error
    def run(self):
        # get the different daemon workers
        with TemporaryDirectory(
                suffix='.dakara'
                ) as tempdir:
            with FontLoader(
                    self.stop
                    ) as font_loader:
                with TextGenerator(
                        self.stop,
                        self.config['Player'],
                        tempdir
                        ) as text_generator:
                    with VlcPlayer(
                            self.stop,
                            self.config['Player'],
                            text_generator
                            ) as vlc_player:
                        with DakaraServer(
                                self.stop,
                                self.config['Server']
                                ) as dakara_server:
                            with DakaraManager(
                                    self.stop,
                                    font_loader,
                                    vlc_player,
                                    dakara_server
                                    ) as dakara_player:
                                # start all the workers
                                dakara_player.thread.start()
                                self.threads.append(dakara_player.thread)

                                # wait for stop event
                                self.stop.wait()

    @staticmethod
    def load_config(config_path):
        """ Load the config from config file

            Args:
                config_path: path to the config file.

            Returns:
                dictionary of the config.
        """
        logger.debug("Reading config file '{}'".format(config_path))

        # check the config file is present
        if not os.path.isfile(config_path):
            raise IOError("No config file found")

        config = ConfigParser()
        config.read(config_path)

        return config

    @stop_on_error
    def configure_logger(self):
        """ Set the logger config

            Set a validated logging level from configuration.
        """
        # select logging level
        loglevel = self.config['Global'].get('loglevel', LOGLEVEL)
        loglevel_numeric = getattr(logging, loglevel.upper(), None)
        if not isinstance(loglevel_numeric, int):
            raise ValueError("Invalid log level \"{}\"".format(loglevel))

        coloredlogs.set_level(loglevel_numeric)
