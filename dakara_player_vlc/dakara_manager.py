import logging

from dakara_player_vlc.safe_workers import WorkerSafeTimer


logger = logging.getLogger("dakara_manager")


class DakaraManager(WorkerSafeTimer):
    """Manager for the Dakara player

    This worker is a high-level manager for the Dakara player. It controls the
    different elements of the project with simple commands.

    Args:
        font_loader (font_loader.FontLoader): object for font
            installation/deinstallation.
        vlc_player (vlc_player.VlcPlayer): interface to VLC.
        dakara_server (dakara_server.DakaraServer): interface to the Dakara
            server.
    """
    def init_worker(self, font_loader, vlc_player, dakara_server):
        """Initialization of the worker
        """
        # set modules up
        self.font_loader = font_loader
        self.vlc_player = vlc_player
        self.dakara_server = dakara_server

        # set player callbacks
        self.vlc_player.set_song_end_callback(self.handle_song_end)
        self.vlc_player.set_error_callback(self.handle_error)

        # set timer
        self.timer = self.create_timer(0, self.start)

    def start(self):
        """First timer thread to be launched
        """
        # initialize first steps
        self.add_next_music()

        # start polling
        self.poll_server()

    def handle_error(self, playing_id, message):
        """Callback when a VLC error occurs

        Args:
            playing_id (int): playlist entry ID.
            message (str): text describing the error.
        """
        logger.error(message)
        self.dakara_server.send_error(playing_id, message)
        self.add_next_music()

    def handle_song_end(self):
        """Callback when a song ends
        """
        self.add_next_music()

    def add_next_music(self):
        """Ask for new song to play, otherwise plays the idle screen
        """
        next_song = self.dakara_server.get_next_song()
        if next_song:
            self.vlc_player.play_song(next_song)

        else:
            self.vlc_player.play_idle_screen()
            self.dakara_server.send_status_get_commands(None)

    def poll_server(self):
        """Manage communication with the server

        Query server for a next song if idle, send status to server otherwise.

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
            playing_id = self.vlc_player.get_playing_id()
            timing = self.vlc_player.get_timing()
            paused = self.vlc_player.is_paused()
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
        if not self.stop.is_set():
            self.timer = self.create_timer(1, self.poll_server)
            self.timer.start()
