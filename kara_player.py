import signal
import logging
from threading import Timer
from vlc_player import VlcPlayer
from dakara_server import DakaraServer
from settings import LOGGING_LEVEL

##
# Loggings
#


logging_level_numeric = getattr(logging, LOGGING_LEVEL.upper(), None)
if not isinstance(logging_level_numeric, int):
    raise ValueError('Invalid log level: {}'.format(LOGGING_LEVEL))
logging.basicConfig(
        format='[%(asctime)s][%(levelname)s] %(message)s',
        level=logging_level_numeric
        )

class KaraPlayer:

    def __init__(self):

        self.vlc_player =  VlcPlayer()
        self.dakara_server = DakaraServer()
        self.vlc_player.set_song_end_callback(self.add_next_music)
        self.vlc_player.set_error_callback(self.handle_error)

    def handle_error(self, playing_id, message):
        logging.error(message)
        self.dakara_server.send_error(playing_id, message)
        self.add_next_music()

    def add_next_music(self):
        next_song = self.dakara_server.get_next_song()
        if next_song:
            self.vlc_player.play_song(next_song)

        else:
            self.vlc_player.play_idle_screen()
            self.dakara_server.send_status_get_commands(None)

    def poll_server(self):
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
                    paused)
            if commands['pause'] is not paused:
                self.vlc_player.set_pause(commands['pause'])
            
            if commands['skip']:
                self.add_next_music()

        # create timer calling poll_server
        self.server_timer = Timer(1, self.poll_server)
        self.server_timer.start()

    def deamon(self):
        def signal_handler(signal, frame):
            self.stop()

        self.start()
        signal.signal(signal.SIGINT, signal_handler)
        signal.pause()

    def start(self):
        logging.info("Daemons started")
        self.add_next_music()
        self.poll_server()

    def stop(self):
        self.server_timer.cancel()
        self.vlc_player.stop()
        logging.info("Daemon stopped")
        

if __name__ == '__main__':
    kara_player = KaraPlayer()
    kara_player.deamon()
