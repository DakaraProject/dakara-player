import json
import logging
import urllib.parse

import requests
from websocket import (WebSocketApp,
                       WebSocketBadStatusException,
                       WebSocketConnectionClosedException)

from dakara_player_vlc.safe_workers import WorkerSafeTimer, safe

# enforce loglevel warning for requests log messages
logging.getLogger("requests").setLevel(logging.WARNING)


logger = logging.getLogger("dakara_server")


RECONNECT_INTERVAL = 5


def authenticated(fun):
    """Decorator that ensures the token is set

    It makes sure that the given function is callel once authenticated.

    Args:
        fun (function): function to decorate.

    Returns:
        function: decorated function.
    """
    def call(self, *args, **kwargs):
        if self.token is None:
            raise AuthenticationError("No connection established")

        return fun(self, *args, **kwargs)

    return call


class DakaraServerHTTPConnection:
    """Object representing a HTTP connection with the Dakara server

    Args:
        config (dict): config of the server.
    """
    def __init__(self, config):
        try:
            # setting config
            self.server_url = urllib.parse.urlunparse((
                'https' if config.get('ssl') else 'http',
                config['address'],
                '/api/',
                '', '', ''
            ))

            # authentication
            self.token = None
            self.login = config['login']
            self.password = config['password']

        except KeyError as error:
            raise ValueError("Missing parameter in server config: {}"
                             .format(error)) from error

    @authenticated
    def send_request(self, method, *args, message_on_error="", **kwargs):
        """Generic method to send requests to the server

        It adds token header for authentication and takes care of errors.

        Args:
            method (str): name of the HTTP method to use.
            message_on_error (str): message to display in logs in case of
                error. It should describe what the request was about.

        Raises:
            ValueError: if the method is not supported.
        """
        # handle method function
        if not hasattr(requests, method):
            raise ValueError("Method {} not supported".format(method))

        send_method = getattr(requests, method)

        # handle message on error
        if not message_on_error:
            message_on_error = "Unable to request the server"

        try:
            response = send_method(*args,
                                   headers=self.get_token_header(),
                                   **kwargs)

        except requests.exceptions.RequestException as error:
            logger.error("{}, network error".format(message_on_error))
            return None

        if response.ok:
            return response

        logger.error(message_on_error)
        logger.debug("Error {code}: {message}".format(
            code=response.status_code,
            message=display_message(response.text)
        ))

        return None

    def get(self, *args, **kwargs):
        """Generic method to get data on server
        """
        return self.send_request('get', *args, **kwargs)

    def post(self, *args, **kwargs):
        """Generic method to post data on server
        """
        return self.send_request('post', *args, **kwargs)

    def put(self, *args, **kwargs):
        """Generic method to put data on server
        """
        return self.send_request('put', *args, **kwargs)

    def patch(self, *args, **kwargs):
        """Generic method to patch data on server
        """
        return self.send_request('patch', *args, **kwargs)

    def authenticate(self):
        """Connect to the server

        The authentication process relies on login/password which gives an
        authentication token. This token is stored in the instance.
        """
        data = {
            'username': self.login,
            'password': self.password,
        }

        # connect to the server with login/password
        try:
            response = requests.post(
                self.server_url + "token-auth/",
                data=data
            )

        except requests.exceptions.RequestException as error:
            raise NetworkError((
                "Network error, unable to talk "
                "to the server for authentication"
            )) from error

        # manage sucessful connection response
        # store token
        if response.ok:
            self.token = response.json().get('token')
            logger.info("Login to server successful")
            logger.debug("Token: " + self.token)
            return

        # manage failed connection response
        if response.status_code == 400:
            raise AuthenticationError(("Login to server failed, check the "
                                       "config file"))

        # manage any other error
        raise AuthenticationError(
            "Unable to connect to server, error {code}: {message}".format(
                code=response.status_code,
                message=display_message(response.text)
            )
        )

    @authenticated
    def get_token_header(self):
        """Get the connection token as it should appear in the header

        Can be called only once login has been sucessful.

        Returns:
            dict: formatted token.
        """
        return {
            'Authorization': 'Token ' + self.token
        }

    @authenticated
    def create_player_error(self, playlist_entry_id, message):
        """Report an error to the server

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.
            message (str): error message.

        Raises:
            ValueError: if `playlist_entry_id` is `None`.
        """
        if playlist_entry_id is None:
            raise ValueError("Entry with ID None is invalid")

        logger.debug("Telling the server that playlist entry {} "
                     "cannot be played"
                     .format(playlist_entry_id))

        self.post(
            self.server_url + "playlist/player/errors/",
            data={
                'playlist_entry_id': playlist_entry_id,
                'error_message': display_message(message, 255)
            },
            message_on_error="Unable to send player error to server"
        )

    @authenticated
    def update_finished(self, playlist_entry_id):
        """Report that a playlist entry has finished

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.

        Raises:
            ValueError: if `playlist_entry_id` is `None`.
        """
        if playlist_entry_id is None:
            raise ValueError("Entry with ID None is invalid")

        logger.debug("Telling the server that playlist entry {} is finished"
                     .format(playlist_entry_id))

        self.put(
            self.server_url + "playlist/player/status/",
            data={
                'event': 'finished',
                'playlist_entry_id': playlist_entry_id,
            },
            message_on_error=("Unable to report that a playlist "
                              "entry has finished")
        )

    @authenticated
    def update_started_transition(self, playlist_entry_id):
        """Report that the transition of a playlist entry has started

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.

        Raises:
            ValueError: if `playlist_entry_id` is `None`.
        """
        if playlist_entry_id is None:
            raise ValueError("Entry with ID None is invalid")

        logger.debug("Telling the server that the transition of playlist "
                     "entry {} has started"
                     .format(playlist_entry_id))

        self.put(
            self.server_url + "playlist/player/status/",
            data={
                'event': 'started_transition',
                'playlist_entry_id': playlist_entry_id,
            },
            message_on_error=("Unable to report that the transition of "
                              "a playlist entry has started")
        )

    @authenticated
    def update_started_song(self, playlist_entry_id):
        """Report that the song of a playlist entry has started

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.

        Raises:
            ValueError: if `playlist_entry_id` is `None`.
        """
        if playlist_entry_id is None:
            raise ValueError("Entry with ID None is invalid")

        logger.debug("Telling the server that the song of playlist "
                     "entry {} has started"
                     .format(playlist_entry_id))

        self.put(
            self.server_url + "playlist/player/status/",
            data={
                'event': 'started_song',
                'playlist_entry_id': playlist_entry_id,
            },
            message_on_error=("Unable to report that the song of "
                              "a playlist entry has started")
        )

    @authenticated
    def update_could_not_play(self, playlist_entry_id):
        """Report that a playlist entry could not play

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.

        Raises:
            ValueError: if `playlist_entry_id` is `None`.
        """
        if playlist_entry_id is None:
            raise ValueError("Entry with ID None is invalid")

        logger.debug("Telling the server that the playlist entry {}"
                     "could not play"
                     .format(playlist_entry_id))

        self.put(
            self.server_url + "playlist/player/status/",
            data={
                'event': 'could_not_play',
                'playlist_entry_id': playlist_entry_id,
            },
            message_on_error=("Unable to report that playlist entry could "
                              "not play")
        )

    @authenticated
    def update_paused(self, playlist_entry_id, timing):
        """Report that the player is paused

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.
            timing (int): progress of the player in seconds.

        Raises:
            ValueError: if `playlist_entry_id` is `None`.
        """
        if playlist_entry_id is None:
            raise ValueError("Entry with ID None is invalid")

        logger.debug("Telling the server that the player is paused")

        self.put(
            self.server_url + "playlist/player/status/",
            data={
                'event': 'paused',
                'playlist_entry_id': playlist_entry_id,
                'timing': timing,
            },
            message_on_error=("Unable to report that the player is paused")
        )

    @authenticated
    def update_resumed(self, playlist_entry_id, timing):
        """Report that the player resumed playing

        Args:
            playlist_entry_id (int): ID of the playlist entry. Must not be
                `None`.
            timing (int): progress of the player in seconds.

        Raises:
            ValueError: if `playlist_entry_id` is `None`.
        """
        if playlist_entry_id is None:
            raise ValueError("Entry with ID None is invalid")

        logger.debug("Telling the server that the player resumed playing")

        self.put(
            self.server_url + "playlist/player/status/",
            data={
                'event': 'resumed',
                'playlist_entry_id': playlist_entry_id,
                'timing': timing,
            },
            message_on_error=("Unable to report that the player resumed "
                              "playing")
        )


def connected(fun):
    """Decorator that ensures the websocket is set

    It makes sure that the given function is callel once connected.

    Args:
        fun (function): function to decorate.

    Returns:
        function: decorated function.
    """
    def call(self, *args, **kwargs):
        if self.websocket is None:
            raise ConnectionError("No connection established")

        return fun(self, *args, **kwargs)

    return call


class DakaraServerWebSocketConnection(WorkerSafeTimer):
    """Object representing the WebSocket connection with the Dakara server

    Args:
        config (dict): configuration for the server, the same as
            DakaraServerHTTPConnection.
        header (dict): header containing the authentication token.
    """
    def init_worker(self, config, header):
        self.server_url = urllib.parse.urlunparse((
            'wss' if config.get('ssl') else 'ws',
            config['address'],
            '/ws/playlist/device/',
            '', '', ''
        ))

        self.header = header
        self.websocket = None
        self.retry = False
        self.reconnect_interval = config.get("reconnect_interval",
                                             RECONNECT_INTERVAL)

        self.timer = self.create_timer(0, self.run)

        # initialize the callbacks
        self.idle_callback = lambda: None
        self.playlist_entry_callback = lambda playlist_entry: None
        self.command_callback = lambda command: None
        self.connection_lost_callback = lambda: None

    def exit_worker(self, *args, **kwargs):
        logger.debug("Aborting websocket connection")
        self.abort()

    def set_idle_callback(self, callback):
        """Assign callback when idle is requested

        Args:
            callback (function): function to assign.
        """
        self.idle_callback = callback

    def set_playlist_entry_callback(self, callback):
        """Assign callback when a new playlist entry is submitted

        Args:
            callback (function): function to assign.
        """
        self.playlist_entry_callback = callback

    def set_command_callback(self, callback):
        """Assign callback when a command is received

        Args:
            callback (function): function to assign.
        """
        self.command_callback = callback

    def set_connection_lost_callback(self, callback):
        """Assign callback when the connection is lost

        Args:
            callback (function): function to assign.
        """
        self.connection_lost_callback = callback

    @safe
    def on_open(self):
        """Callback when the connection is open
        """
        logger.info("Websocket connected to server")
        self.retry = False
        self.send_ready()

    @safe
    def on_close(self, code, reason):
        """Callback when the connection is closed

        If the disconnection is not due to the end of the program, consider the
        connection has been lost. In that case, a reconnection will be
        attempted within several seconds.

        Args:
            code (int): error code (often None).
            reason (str): reason of the closed connection (often None).
        """
        if code or reason:
            logger.debug("Code {}: {}".format(code, reason))

        # destroy websocket object
        self.websocket = None

        if self.stop.is_set():
            logger.info("Websocket disconnected from server")
            return

        if not self.retry:
            logger.error("Websocket connection lost")

        self.retry = True
        self.connection_lost_callback()

        # attempt to reconnect
        logger.warning("Trying to reconnect in {} s"
                       .format(self.reconnect_interval))
        self.timer = self.create_timer(self.reconnect_interval, self.run)
        self.timer.start()

    @safe
    def on_message(self, message):
        """Callback when a message is received

        It will call the method which name corresponds to the event type, if
        possible.

        Args:
            message (str): a JSON text of the event.
        """
        # convert the message to an event object
        try:
            event = json.loads(message)

        # if the message is not in JSON format, assume this is an error
        except json.JSONDecodeError:
            logger.error("Unexpected message from the server: '{}'".format(
                display_message(message)))
            return

        # attempt to call the corresponding method
        method_name = "receive_{}".format(event['type'])
        if not hasattr(self, method_name):
            logger.error("Event of unknown type received '{}'"
                         .format(event['type']))
            return

        getattr(self, method_name)(event.get('data'))

    @safe
    def on_error(self, error):
        """Callback when an error occurs

        Args:
            error (BaseException): class of the error.
        """
        # do not analyze error on program exit, as it will mistake the
        # WebSocketConnectionClosedException raised by invoking `abort` for a
        # server connection closed error
        if self.stop.is_set():
            return

        # the connection was refused
        if isinstance(error, WebSocketBadStatusException):
            raise AuthenticationError(
                "Unable to connect to server with this user") from error

        # the server is unreachable
        if isinstance(error, ConnectionRefusedError):
            if self.retry:
                logger.warning("Unable to talk to the server")
                return

            raise NetworkError(
                "Network error, unable to talk to the server") from error

        # the requested endpoint does not exist
        if isinstance(error, ConnectionResetError):
            raise ValueError(
                "Invalid endpoint to the server") from error

        # connection closed by the server (see beginning of the method)
        if isinstance(error, WebSocketConnectionClosedException):
            # this case is handled by the on_close method
            return

        # other unlisted reason
        logger.error("Websocket: {}".format(error))

    @connected
    def send(self, content, *args, **kwargs):
        """Send data from a dictionary

        Convert it to JSON string before send.

        Args:
            content (dict): dictionary of the event.
        """
        return self.websocket.send(json.dumps(content), *args, **kwargs)

    def abort(self):
        """Request to interrupt the connection

        Can be called from anywhere. It will raise an
        `WebSocketConnectionClosedException` which will be passed to
        `on_error`.
        """
        self.retry = False

        # if the connection is lost, the `sock` object may not have the `abort`
        # method
        if self.websocket is not None \
           and hasattr(self.websocket.sock, 'abort'):
            self.websocket.sock.abort()

    def run(self):
        """Event loop

        Create the websocket connection and wait events from it. The method can
        be interrupted with the `abort` method.

        The WebSocketApp class is a genki: it will never complaint of anything.
        Wether it is unable to create a connection or its connection is lost,
        the `run_forever` method ends without any exception or non-None return
        value. Exceptions are handled by the yandere `on_error` callback.
        """
        logger.debug("Preparing websocket connection")
        self.websocket = WebSocketApp(
            self.server_url,
            header=self.header,
            on_open=lambda ws: self.on_open(),
            on_close=lambda ws, code, reason: self.on_close(code, reason),
            on_message=lambda ws, message: self.on_message(message),
            on_error=lambda ws, error: self.on_error(error)
        )
        self.websocket.run_forever()

    def receive_idle(self, content):
        """Receive idle order

        Args:
            content (dict): dictionary of the event
        """
        logger.debug("Received idle order")
        self.idle_callback()

    def receive_playlist_entry(self, content):
        """Receive new playlist entry

        Args:
            content (dict): dictionary of the event
        """
        logger.debug("Received new playlist entry {} order"
                     .format(content['id']))
        self.playlist_entry_callback(content)

    def receive_command(self, content):
        """Receive a command

        Args:
            content (dict): dictionary of the event
        """
        command = content['command']
        logger.debug("Received command: '{}'".format(command))
        self.command_callback(command)

    def send_ready(self):
        """Tell the server that the player is ready
        """
        logger.debug("Telling the server that the player is ready")
        self.send({
            'type': 'ready'
        })


def display_message(message, limit=100):
    """Display the 100 first characters of a message
    """
    if len(message) <= limit:
        return message

    return message[:limit - 3].strip() + "..."


class AuthenticationError(Exception):
    """Error raised when authentication fails
    """


class NetworkError(Exception):
    """Error raised when the communication fails during a critical task
    """
