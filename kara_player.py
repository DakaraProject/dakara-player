import signal
import logging
import coloredlogs
from threading import Timer
from configparser import ConfigParser
from vlc_player import VlcPlayer
from dakara_server import DakaraServer

CONFIG_FILE_PATH = "config.ini"

##
# Loggings
#


class KaraPlayer:

    def __init__(self):
        # load config from file
        config = ConfigParser()
        config.read(CONFIG_FILE_PATH)
        global_config = config['Global']
        server_config = config['Server']
        player_config = config['Player']

        self.configure_logger(global_config)

        self.vlc_player = VlcPlayer(player_config)
        self.dakara_server = DakaraServer(server_config)
        self.vlc_player.set_song_end_callback(self.handle_song_end)
        self.vlc_player.set_error_callback(self.handle_error)
        self.stop_flag = False

    def configure_logger(self, config):
        loglevel = config.get('loglevel')
        logging_level_numeric = getattr(logging, loglevel.upper(), None)
        if not isinstance(logging_level_numeric, int):
            raise ValueError('Invalid log level: {}'.format(loglevel))

        coloredlogs.install(
                fmt='[%(asctime)s] %(levelname)s %(message)s',
                level=logging_level_numeric
                )

    def handle_error(self, playing_id, message):
        """ Callback when a VLC error occurs

            Args:
                playing_id: playlist entry ID.
                message: text describing the error.
        """
        logging.error(message)
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
            self.stop()

        self.start()
        signal.signal(signal.SIGINT, handle_signal)
        signal.pause()

    def start(self):
        """ Query music, then communicate with the server
            (thus, start server polling)
        """
        logging.info("Daemons started")
        self.stop_flag = False
        self.add_next_music()
        self.poll_server()

    def stop(self):
        """ Stop VLC and stop polling server
        """
        self.stop_flag = True
        self.server_timer.cancel()
        self.vlc_player.clean()
        logging.info("Daemon stopped")


if __name__ == '__main__':
    kara_player = KaraPlayer()
    kara_player.deamon()
