import logging
from tempfile import TemporaryDirectory
from contextlib import ExitStack
from pkg_resources import parse_version

from dakara_base.safe_workers import WorkerSafeThread, Runner

from dakara_player_vlc.version import __version__, __date__
from dakara_player_vlc.text_generator import TextGenerator
from dakara_player_vlc.vlc_player import VlcPlayer
from dakara_player_vlc.dakara_server import (
    DakaraServerHTTPConnection,
    DakaraServerWebSocketConnection,
)
from dakara_player_vlc.dakara_manager import DakaraManager
from dakara_player_vlc.font_loader import get_font_loader_class

FontLoader = get_font_loader_class()


logger = logging.getLogger(__name__)


class DakaraPlayerVlc(Runner):
    """Class associated with the main thread

    It simply starts, launchs the worker and waits for it to terminate or for a
    user Ctrl+C to be fired.
    """

    def init_runner(self, config):
        """Initialization

        Creates the worker stop event.

        Args:
            config (dict): configuration for the program.
        """
        # store arguments
        self.config = config

        logger.debug("Started main")

    def run(self):
        """Launch the worker and wait for the end
        """
        self.run_safe(DakaraWorker, self.config)


class DakaraWorker(WorkerSafeThread):
    """Class associated with the worker thread

    It simply starts, loads configuration, set the different worker, launches
    the main polling thread and waits for the end.
    """

    def init_worker(self, config):
        """Initialization

        Load the config and set the logger loglevel.

        Args:
            config (dict): configuration for the program.
        """
        self.config = config
        logger.debug("Starting Dakara worker")

        # set thread
        self.thread = self.create_thread(target=self.run)

        # check version
        self.check_version()

    def run(self):
        """Worker main method

        It sets up the different workers and uses them as context managers,
        which guarantee that their different clean methods will be called
        prorperly.

        Then it starts the polling thread and waits for the end.

        When `run` is called, the end can come for several reasons:
            * the main thread (who calls the worker thread) has caught a Ctrl+C
              from the user;
            * an exception has been raised within the `run` method (directly in
              the worker thread);
            * an exception has been raised within the polling thread.
        """
        # get the different workers as context managers
        # ExitStack makes the management of multiple context managers simpler
        # This mechanism plus the use of Worker classes allow to gracelly end
        # the execution of any thread within the context manager. It guarantees
        # as well that on leaving this context manager, all cleanup tasks will
        # be executed.
        with ExitStack() as stack:
            # temporary directory
            tempdir = stack.enter_context(TemporaryDirectory(suffix=".dakara"))

            # font loader
            font_loader = stack.enter_context(FontLoader())
            font_loader.load()

            # text screen generator
            text_generator = TextGenerator(
                self.config["player"].get("templates") or {}, tempdir
            )
            text_generator.load()

            # vlc player
            vlc_player = stack.enter_context(
                VlcPlayer(self.stop, self.errors, self.config["player"], text_generator)
            )
            vlc_player.load()

            # communication with the dakara HTTP server
            dakara_server_http = DakaraServerHTTPConnection(
                self.config["server"], route="api/", mute_raise=True
            )
            dakara_server_http.authenticate()
            token_header = dakara_server_http.get_token_header()

            # communication with the dakara WebSocket server
            dakara_server_websocket = stack.enter_context(
                DakaraServerWebSocketConnection(
                    self.stop,
                    self.errors,
                    self.config["server"],
                    header=token_header,
                    route="ws/playlist/device/",
                )
            )

            # manager for the precedent workers
            dakara_manager = DakaraManager(  # noqa F841
                font_loader, vlc_player, dakara_server_http, dakara_server_websocket
            )

            # start the worker timer
            dakara_server_websocket.timer.start()

            # wait for stop event
            self.stop.wait()

            # leaving this method means leaving all the context managers and
            # stopping the program

    def check_version(self):
        """Display version number and check if on release
        """
        # log player versio
        logger.info("Dakara player %s (%s)", __version__, __date__)

        # check version is a release
        version = parse_version(__version__)
        if version.is_prerelease:
            logger.warning("You are running a dev version, use it at your own risks!")
