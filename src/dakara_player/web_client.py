"""HTTP and WebSocket clients for the Dakara server."""

import logging

from dakara_base.http_client import HTTPClient, authenticated
from dakara_base.utils import truncate_message
from dakara_base.websocket_client import WebSocketClient

logger = logging.getLogger(__name__)


class HTTPClientDakara(HTTPClient):
    """HTTP client connected to the Dakara server.

    Example of use:

    >>> http_client = HTTPClientDakara(
    ...     {
    ...         "address": "www.example.com",
    ...         "port": 8080,
    ...         "login": "player",
    ...         "password": "pass"
    ...     },
    ...     enpoint_prefix="api/",
    ...     mute_raise=True,
    ... )
    >>> http_client.authenticate()

    Args:
        config (dict): Config of the client.
        endpoint_prefix (str): Prefix of the endpoint, added to the URL.
        mute_raise (bool): If true, no exception will be raised when sending
            requests to the server (but authentication), only logged.
    """

    @authenticated
    def post_player_error(self, playlist_entry_id, message):
        """Report an error to the server.

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.
            message (str): Error message.

        Raises:
            AssertError: If `playlist_entry_id` is `None`.
        """
        assert playlist_entry_id is not None, "Entry with ID None is invalid"

        logger.debug(
            "Telling the server that playlist entry %i cannot be played",
            playlist_entry_id,
        )

        self.post(
            endpoint="playlist/player/errors/",
            data={
                "playlist_entry_id": playlist_entry_id,
                "error_message": truncate_message(message, 255),
            },
            message_on_error="Unable to send player error to server",
        )

    @authenticated
    def put_status_finished(self, playlist_entry_id):
        """Report that a playlist entry has finished.

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.

        Raises:
            AssertError: If `playlist_entry_id` is `None`.
        """
        assert playlist_entry_id is not None, "Entry with ID None is invalid"

        logger.debug(
            "Telling the server that playlist entry %i is finished", playlist_entry_id
        )

        self.put(
            endpoint="playlist/player/status/",
            data={"event": "finished", "playlist_entry_id": playlist_entry_id},
            message_on_error="Unable to report that a playlist entry has finished",
        )

    @authenticated
    def put_status_started_transition(self, playlist_entry_id):
        """Report that the transition of a playlist entry has started.

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.

        Raises:
            AssertError: If `playlist_entry_id` is `None`.
        """
        assert playlist_entry_id is not None, "Entry with ID None is invalid"

        logger.debug(
            "Telling the server that the transition of playlist entry %i has started",
            playlist_entry_id,
        )

        self.put(
            endpoint="playlist/player/status/",
            data={
                "event": "started_transition",
                "playlist_entry_id": playlist_entry_id,
            },
            message_on_error=(
                "Unable to report that the transition of a playlist entry has started"
            ),
        )

    @authenticated
    def put_status_started_song(self, playlist_entry_id):
        """Report that the song of a playlist entry has started.

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.

        Raises:
            AssertError: If `playlist_entry_id` is `None`.
        """
        assert playlist_entry_id is not None, "Entry with ID None is invalid"

        logger.debug(
            "Telling the server that the song of playlist entry %i has started",
            playlist_entry_id,
        )

        self.put(
            endpoint="playlist/player/status/",
            data={"event": "started_song", "playlist_entry_id": playlist_entry_id},
            message_on_error=(
                "Unable to report that the song of a playlist entry has started"
            ),
        )

    @authenticated
    def put_status_could_not_play(self, playlist_entry_id):
        """Report that a playlist entry could not play.

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.

        Raises:
            AssertError: If `playlist_entry_id` is `None`.
        """
        assert playlist_entry_id is not None, "Entry with ID None is invalid"

        logger.debug(
            "Telling the server that the playlist entry %i could not play",
            playlist_entry_id,
        )

        self.put(
            endpoint="playlist/player/status/",
            data={"event": "could_not_play", "playlist_entry_id": playlist_entry_id},
            message_on_error="Unable to report that playlist entry could not play",
        )

    @authenticated
    def put_status_paused(self, playlist_entry_id, timing):
        """Report that the player is paused.

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.
            timing (int): Progress of the player in seconds.

        Raises:
            AssertError: If `playlist_entry_id` is `None`.
        """
        assert playlist_entry_id is not None, "Entry with ID None is invalid"

        logger.debug("Telling the server that the player is paused")

        self.put(
            endpoint="playlist/player/status/",
            data={
                "event": "paused",
                "playlist_entry_id": playlist_entry_id,
                "timing": timing,
            },
            message_on_error="Unable to report that the player is paused",
        )

    @authenticated
    def put_status_resumed(self, playlist_entry_id, timing):
        """Report that the player resumed playing.

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.
            timing (int): Progress of the player in seconds.

        Raises:
            AssertError: If `playlist_entry_id` is `None`.
        """
        assert playlist_entry_id is not None, "Entry with ID None is invalid"

        logger.debug("Telling the server that the player resumed playing")

        self.put(
            endpoint="playlist/player/status/",
            data={
                "event": "resumed",
                "playlist_entry_id": playlist_entry_id,
                "timing": timing,
            },
            message_on_error="Unable to report that the player resumed playing",
        )

    @authenticated
    def put_status_update_timing(self, playlist_entry_id, timing):
        """Report that the player updated its timing.

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.
            timing (int): Progress of the player in seconds.

        Raises:
            AssertError: If `playlist_entry_id` is `None`.
        """
        assert playlist_entry_id is not None, "Entry with ID None is invalid"

        logger.debug("Telling the server that the player updated its timing")

        self.put(
            endpoint="playlist/player/status/",
            data={
                "event": "updated_timing",
                "playlist_entry_id": playlist_entry_id,
                "timing": timing,
            },
            message_on_error="Unable to report that the player updated its timing",
        )


class WebSocketClientDakara(WebSocketClient):
    """WebSocket client connected to the Dakara server.

    Example of use:

    >>> config = {
    ...     "address": "www.example.com",
    ...     "port": 8080,
    ...     "login": "player",
    ...     "password": "pass"
    ... }
    >>> http_client = HTTPClientDakara(
    ...     config,
    ...     enpoint_prefix="api/",
    ... )
    >>> http_client.authenticate()
    >>> header = http_client.get_token_header()
    >>> from thread import Event
    >>> from queue import Queue
    >>> stop = Event()
    >>> errors = Queue()
    >>> ws_client = WebSocketClientDakara(
    ...     stop,
    ...     errors,
    ...     config,
    ...     enpoint="ws/playlist",
    ...     header=header
    ... )
    >>> ws_client.run()

    Args:
        stop (Event): Event to stop the program.
        errors (Queue): Queue of errors.
        config (dict): Configuration for the server, the same as
            HTTPClientDakara.
        endpoint (str): Enpoint of the WebSocket connection, added to the URL.
        header (dict): Header containing the authentication token.
    """

    def set_default_callbacks(self):
        """Set all the default callbacks."""
        self.set_callback("idle", lambda: None)
        self.set_callback("playlist_entry", lambda playlist_entry: None)
        self.set_callback("command", lambda command: None)
        self.set_callback("connection_lost", lambda: None)

    def on_connected(self):
        """Callback when the connection is open."""
        self.send_ready()

    def on_connection_lost(self):
        """Callback when the connection is lost."""
        self.callbacks["connection_lost"]()

    def receive_idle(self, content):
        """Receive idle order.

        Args:
            content (dict): Dictionary of the event
        """
        logger.debug("Received idle order")
        self.callbacks["idle"]()

    def receive_playlist_entry(self, content):
        """Receive new playlist entry.

        Args:
            content (dict): Dictionary of the event
        """
        logger.debug("Received new playlist entry %i order", content["id"])
        self.callbacks["playlist_entry"](content)

    def receive_command(self, content):
        """Receive a command.

        Args:
            content (dict): Dictionary of the event
        """
        command = content["command"]
        logger.debug("Received command %s order", command)
        self.callbacks["command"](command)

    def send_ready(self):
        """Tell the server that the player is ready."""
        logger.debug("Telling the server that the player is ready")
        self.send("ready")
