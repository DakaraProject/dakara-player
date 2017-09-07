import os
import logging
from threading import Event
from configparser import ConfigParser
from tempfile import TemporaryDirectory
from contextlib import ExitStack
from queue import Queue, Empty

import coloredlogs

from .daemon import DaemonMaster
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


class DakaraPlayerVlc:
    """ Class associated with the main thread

        It simply starts, launchs the daemon and waits for it to terminate or
        for a user Ctrl+C to be fired.
    """
    def __init__(self, config_path):
        """ Initialization

            Creates the daemon stop event

            Args:
                config_path (str): path to the config file. Will be passed to
                    the daemon, who uses it.
        """
        logger.debug("Starting main")

        # create stop event
        self.stop = Event()

        # create errors queue
        self.errors = Queue()

        # store arguments
        self.config_path = config_path

    def run(self):
        """ Launch the daemon and wait for the end
        """
        try:
            # create daemon thread
            with DakaraDaemon(
                    self.stop,
                    self.errors,
                    self.config_path
                    ) as daemon:

                logger.debug("Create daemon thread")
                daemon.thread.start()

                # wait for stop event
                logger.debug("Waiting for stop event")
                self.stop.wait()

        # stop on Ctrl+C
        except KeyboardInterrupt:
            logger.debug("User stop caught")
            self.stop.set()

        # stop on error
        else:
            logger.debug("Internal error caught")

            # get the error from the error queue and re-raise it
            try:
                _, error, traceback = self.errors.get(5)
                error.with_traceback(traceback)
                raise error

            # if there is no error in the error queue, raise a general error
            except Empty as empty_error:
                raise RuntimeError("Unknown error happened") from empty_error


class DakaraDaemon(DaemonMaster):
    """ Class associated with the daemon thread

        It simply starts, loads configuration, set the different worker
        daemons, launches the main polling thread and waits for the end.
    """
    def init_master(self, config_path):
        """ Initialization

            Load the config and set the logger loglevel.

            Args:
                config_path (str): path to the config file.
        """
        logger.debug("Starting daemon")

        # load config
        self.config = self.load_config(config_path)

        # configure loader
        self.configure_logger()

    def run(self):
        """ Daemon main method

            It sets up the different worker daemons and uses them as context
            managers, which guarantee that their different clean methods will
            be called prorperly.

            Then its starts the polling thread (unique member of the threads
            pool) and wait for the end.

            When `run` is called, the end can come for several reasons:
                * the main thread (who calls the daemon thread) has caught a
                  Ctrl+C from the user;
                * an exception has been raised within the `run` method
                  (directly in the daemon thread);
                * an exception has been raised within the polling thread.
        """
        # get the different daemon workers as context managers
        # ExitStack makes the management of multiple context managers simpler
        # This mechanism plus the use of Daemon classes allow to gracelly end
        # the execution of any thread within the context manager. It guarantees
        # as well that on leaving this context manager, all cleanup tasks will
        # be executed.
        with ExitStack() as stack:
            # temporary directory
            tempdir = stack.enter_context(TemporaryDirectory(
                    suffix='.dakara'
                    ))

            # font loader
            font_loader = stack.enter_context(FontLoader())
            font_loader.load()

            # text screen generator
            text_generator = TextGenerator(
                    self.config['Player'],
                    tempdir
                    )

            # vlc player
            vlc_player = stack.enter_context(VlcPlayer(
                    self.stop,
                    self.errors,
                    self.config['Player'],
                    text_generator
                    ))

            # communication with the dakara server
            dakara_server = DakaraServer(self.config['Server'])
            dakara_server.authenticate()

            # manager for the precedent workers
            dakara_manager = stack.enter_context(DakaraManager(
                    self.stop,
                    self.errors,
                    font_loader,
                    vlc_player,
                    dakara_server
                    ))

            # start the worker thread
            dakara_manager.timer.start()

            # wait for stop event
            self.stop.wait()

            # leaving this method means leaving all the context managers and
            # stop the program

    @staticmethod
    def load_config(config_path):
        """ Load the config from config file

            Args:
                config_path: path to the config file.

            Returns:
                dictionary of the config.
        """
        logger.info("Reading config file '{}'".format(config_path))

        # check the config file is present
        if not os.path.isfile(config_path):
            raise IOError("No config file found")

        config = ConfigParser()
        config.read(config_path)

        return config

    def configure_logger(self):
        """ Set the logger config

            Set a validated logging level from configuration.
        """
        # select logging level
        loglevel = self.config['Global'].get('loglevel', LOGLEVEL)
        loglevel_numeric = getattr(logging, loglevel.upper(), None)
        if not isinstance(loglevel_numeric, int):
            raise ValueError(
                    "Invalid loglevel in configuration: '{}'".format(loglevel)
                    )

        coloredlogs.set_level(loglevel_numeric)
