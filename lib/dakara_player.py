import os
import signal
from threading import Timer
from configparser import ConfigParser
import logging
import coloredlogs
from .vlc_player import VlcPlayer
from .dakara_server import DakaraServer
from .font_loader import get_font_loader_class


FontLoader = get_font_loader_class()


CONFIG_FILE_PATH = "config.ini"
LOGLEVEL = 'INFO'


logger = logging.getLogger(__name__)


coloredlogs.install(
        fmt='[%(asctime)s] %(name)s %(levelname)s %(message)s',
        level=LOGLEVEL
        )


class DakaraPlayer:

    def __init__(self):
        # load the config
        config = self.load_config(CONFIG_FILE_PATH)
        global_config = config['Global']
        server_config = config['Server']
        player_config = config['Player']

        # set logger config
        self.configure_logger(global_config)

        # set modules up
        self.font_loader = FontLoader()
        self.font_loader.load()
        self.vlc_player = VlcPlayer(player_config)
        self.dakara_server = DakaraServer(server_config)
        self.dakara_server.authenticate()
        self.vlc_player.set_song_end_callback(self.handle_song_end)
        self.vlc_player.set_error_callback(self.handle_error)

        # flag to stop the server polling
        self.stop_flag = False

    def load_config(self, config_path):
        """ Load the config from config file

            Args:
                config_path: path to the config file.

            Returns:
                dictionary of the config.
        """
        # check the config file is present
        if not os.path.isfile(config_path):
            raise IOError("No config file found")

        config = ConfigParser()
        config.read(config_path)

        return config

    def configure_logger(self, config):
        """ Set the logger config

            Set a validated logging level from configuration.

            Args:
                config: dictionary containing global parameters, among
                    them logging parameters. It should contain the
                    `loglevel` key.
        """
        # select logging level
        loglevel = config.get('loglevel', LOGLEVEL)
        loglevel_numeric = getattr(logging, loglevel.upper(), None)
        if not isinstance(loglevel_numeric, int):
            raise ValueError("Invalid log level \"{}\"".format(loglevel))

        coloredlogs.set_level(loglevel_numeric)

    def handle_error(self, playing_id, message):
        """ Callback when a VLC error occurs

            Args:
                playing_id: playlist entry ID.
                message: text describing the error.
        """
        logger.error(message)
        self.dakara_server.send_error(playing_id, message)
        self.add_next_music()

    def handle_song_end(self):
        """ Callback when a song ends
        """
        self.add_next_music()

    def add_next_music(self):
        """ Ask for new song to play, otherwise plays the idle screen
        """
        next_song = self.dakara_server.get_next_song()
        if next_song:
            self.vlc_player.play_song(next_song)

        else:
            self.vlc_player.play_idle_screen()
            self.dakara_server.send_status_get_commands(None)

    def poll_server(self):
        """ Manage communication with the server

            Query server for a next song if idle,
            send status to server otherwise.

            The method calls itself every second.
        """
        if self.vlc_player.is_idle():
            # idle : check if there is a song to play
            next_song = self.dakara_server.get_next_song()
            if next_song:
                self.vlc_player.play_song(next_song)

        else:
            # send status to server,
            # and manage pause/skip events
            playing_id  = self.vlc_player.get_playing_id()
            timing = self.vlc_player.get_timing()
            paused  = self.vlc_player.is_paused()
            commands = self.dakara_server.send_status_get_commands(
                    playing_id,
                    timing,
                    paused
                    )

            if commands['pause'] is not paused:
                self.vlc_player.set_pause(commands['pause'])

            if commands['skip']:
                self.add_next_music()

        # create timer calling poll_server
        if not self.stop_flag:
            self.server_timer = Timer(1, self.poll_server)
            self.server_timer.start()

    def deamon(self):
        """ Daemonization looper

            Start, wait for Ctrl+C and then, stop.
        """
        def handle_signal(signum, frame):
            # ignore any other Ctrl C
            signal.signal(signal.SIGINT, signal.SIG_IGN)

        try:
            self.start()
            signal.signal(signal.SIGINT, handle_signal)
            signal.pause()

        finally:
            # stop the daemon
            self.stop()

    def start(self):
        """ Query music, then communicate with the server
            (thus, start server polling)
        """
        logger.info("Daemons started")
        self.stop_flag = False
        self.add_next_music()
        self.poll_server()

    def stop(self):
        """ Stop VLC and stop polling server
        """
        self.stop_flag = True
        self.server_timer.cancel()
        self.vlc_player.clean()
        self.font_loader.unload()
        logger.info("Daemon stopped")
