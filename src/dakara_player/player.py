"""Player."""

import logging
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

from dakara_base.exceptions import DakaraError
from dakara_base.safe_workers import Runner, WorkerSafeThread

from dakara_player.font import get_font_loader_class
from dakara_player.manager import DakaraManager
from dakara_player.media_player.mpv import MediaPlayerMpv
from dakara_player.media_player.vlc import MediaPlayerVlc
from dakara_player.version import check_version
from dakara_player.web_client import HTTPClientDakara, WebSocketClientDakara

FontLoader = get_font_loader_class()

MEDIA_PLAYER_CLASSES = {
    "mpv": MediaPlayerMpv.from_version,
    "vlc": MediaPlayerVlc,
}

logger = logging.getLogger(__name__)


class DakaraPlayer(Runner):
    """Class associated with the main thread.

    It simply starts, launchs the worker and waits for it to terminate or for a
    user Ctrl+C to be fired.
    """

    def init_runner(self, config):
        """Initialization.

        Creates the worker stop event.

        Args:
            config (dict): Configuration for the program.
        """
        # store arguments
        self.config = config

        # inform the user
        logger.debug("Started main")

    def load(self):
        """Execute side-effect actions."""
        # check version
        check_version()

    def run(self):
        """Launch the worker and wait for the end."""
        self.run_safe(DakaraWorker, self.config)


class DakaraWorker(WorkerSafeThread):
    """Class associated with the worker thread.

    It simply starts, loads configuration, set the different worker, launches
    the main thread and waits for the end.
    """

    def init_worker(self, config):
        """Initialization.

        Load the config and set the logger loglevel.

        Args:
            config (dict): Configuration for the program.
        """
        self.config = config

        # set thread
        self.thread = self.create_thread(target=self.run)

        # inform the user
        logger.debug("Starting Dakara worker")

    def get_media_player_class(self):
        """Get the class of the requested media player.

        Fallback to VLC if none was provided in config. If the requested media
        player is not known, raise an error.

        Returns:
            dakara_player.media_player.base.MediaPlayer: Specialized class of
            the media player.
        """
        media_player_name = self.config["player"].get("player_name", "vlc")

        try:
            return MEDIA_PLAYER_CLASSES[media_player_name.lower()]

        except KeyError as error:
            raise UnsupportedMediaPlayerError(
                "No media player for '{}'".format(media_player_name)
            ) from error

    def run(self):
        """Worker main method.

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
            tempdir = Path(stack.enter_context(TemporaryDirectory(suffix=".dakara")))

            # font loader
            font_loader = stack.enter_context(
                FontLoader("dakara_player.resources.fonts")
            )
            font_loader.load()

            # media player
            media_player = stack.enter_context(
                self.get_media_player_class()(
                    self.stop,
                    self.errors,
                    self.config["player"],
                    tempdir,
                )
            )
            media_player.load()

            # communication with the dakara HTTP server
            http_client = HTTPClientDakara(
                self.config["server"], endpoint_prefix="api/", mute_raise=True
            )
            http_client.load()
            http_client.authenticate()
            token_header = http_client.get_token_header()

            # communication with the dakara WebSocket server
            websocket_client = stack.enter_context(
                WebSocketClientDakara(
                    self.stop,
                    self.errors,
                    self.config["server"],
                    header=token_header,
                    endpoint="ws/playlist/device/",
                )
            )

            # manager for the precedent workers
            dakara_manager = DakaraManager(  # noqa F841
                font_loader, media_player, http_client, websocket_client
            )

            # start the worker timer
            websocket_client.timer.start()

            # wait for stop event
            self.stop.wait()

            # leaving this method means leaving all the context managers and
            # stopping the program


class UnsupportedMediaPlayerError(DakaraError):
    """Raised if an unknown media player is requested."""
