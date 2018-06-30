import logging


logger = logging.getLogger("dakara_manager")


class DakaraManager:
    """Manager for the Dakara player

    This object is a high-level manager for the Dakara player. It controls the
    different elements of the project with simple commands.

    Args:
        font_loader (font_loader.FontLoader): object for font
            installation/deinstallation.
        vlc_player (vlc_player.VlcPlayer): interface to VLC.
        dakara_server (dakara_server.DakaraServerWebSocketConnection):
            interface to the Dakara server.
    """
    def __init__(self, font_loader, vlc_player, dakara_server):
        """Initialization of the worker
        """
        # set modules up
        self.font_loader = font_loader
        self.vlc_player = vlc_player
        self.dakara_server = dakara_server

        # set player callbacks
        self.vlc_player.set_song_end_callback(self.handle_song_end)
        self.vlc_player.set_error_callback(self.handle_error)

        # set dakara server websocket callbacks
        self.dakara_server.websocket.set_idle_callback(self.be_idle)
        self.dakara_server.websocket.set_new_entry_callback(self.play_entry)
        self.dakara_server.websocket.set_command_callback(self.do_command)
        self.dakara_server.websocket.set_status_request_callback(
            self.get_status)

    def handle_error(self, entry_id, message):
        """Callback when a VLC error occurs

        Args:
            entry_id (int): playlist entry ID.
            message (str): text describing the error.
        """
        logger.error(message)
        self.dakara_server.websocket.send_entry_error(entry_id, message)

    def handle_song_end(self, entry_id):
        """Callback when a song ends

        Args:
            entry_id (int): playlist entry ID.
        """
        self.dakara_server.websocket.send_entry_finished(entry_id)

    def play_entry(self, entry):
        """Play the requested entry

        Args:
            entry (dict): dictionary of the playlist entry.
        """
        self.vlc_player.play_song(entry)

    def be_idle(self):
        """Play the idle screen
        """
        self.vlc_player.play_idle_screen()

    def do_command(self, command):
        """Execute a player command

        Args:
            command (str): name of the command to execute. Must be amont
                'pause' and 'play'.

        Raises:
            ValueError: if the command is not known.
        """
        if command not in ('pause', 'play'):
            raise ValueError("Unknown command requested: '{}'".format(command))

        if command == "pause":
            self.vlc_player.set_pause(True)

        elif command == "play":
            self.vlc_player.set_pause(False)

    def get_status(self):
        """Send status to the server
        """
        playing_id = self.vlc_player.get_playing_id()
        timing = self.vlc_player.get_timing()
        paused = self.vlc_player.is_paused()
        self.dakara_server.websocket.send_status(
            playing_id,
            timing,
            paused
        )
