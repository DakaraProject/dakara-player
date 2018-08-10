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
        dakara_server_http (dakara_server.DakaraServerHTTPConnection):
            interface to the Dakara server for the HTTP protocol.
        dakara_server_websocket
            (dakara_server.DakaraServerWebSocketConnection): interface to the
            Dakara server for the Websocket protocol.
    """
    def __init__(self, font_loader, vlc_player,
                 dakara_server_http, dakara_server_websocket):
        # set modules up
        self.font_loader = font_loader
        self.vlc_player = vlc_player
        self.dakara_server_http = dakara_server_http
        self.dakara_server_websocket = dakara_server_websocket

        # set player callbacks
        self.vlc_player.set_song_end_callback(self.handle_song_end)
        self.vlc_player.set_song_start_callback(self.handle_song_start)
        self.vlc_player.set_error_callback(self.handle_error)

        # set dakara server websocket callbacks
        self.dakara_server_websocket.set_idle_callback(self.be_idle)
        self.dakara_server_websocket.set_playlist_entry_callback(
            self.play_playlist_entry)
        self.dakara_server_websocket.set_command_callback(self.do_command)
        self.dakara_server_websocket.set_status_request_callback(
            self.get_status)
        self.dakara_server_websocket.set_connection_lost_callback(self.be_idle)

    def handle_error(self, playlist_entry_id, message):
        """Callback when a VLC error occurs

        Args:
            playlist_entry_id (int): playlist entry ID.
            message (str): text describing the error.
        """
        logger.error(message)
        self.dakara_server_http.create_player_error(playlist_entry_id, message)

    def handle_song_end(self, playlist_entry_id):
        """Callback when a song ends

        Args:
            playlist_entry_id (int): playlist entry ID.
        """
        self.dakara_server_http.update_playlist_entry_finished(
            playlist_entry_id)

    def handle_song_start(self, playlist_entry_id):
        """Callback when a song starts

        Args:
            playlist_entry_id (int): playlist entry ID.
        """
        self.dakara_server_http.update_playlist_entry_started(
            playlist_entry_id)

    def play_playlist_entry(self, playlist_entry):
        """Play the requested playlist entry

        Args:
            playlist_entry (dict): dictionary of the playlist entry.
        """
        self.vlc_player.play_song(playlist_entry)

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
        in_transition = self.vlc_player.in_transition
        self.dakara_server_http.update_status(
            playing_id,
            timing,
            paused,
            in_transition
        )
