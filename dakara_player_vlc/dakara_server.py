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

        self.timer = self.create_timer(0, self.run)

        # initialize the callbacks
        self.idle_callback = lambda: None
        self.new_entry_callback = lambda entry: None
        self.command_callback = lambda command: None
        self.status_request_callback = lambda: None
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

    def set_new_entry_callback(self, callback):
        """Assign callback when a new entry is submitted

        Args:
            callback (function): function to assign.
        """
        self.new_entry_callback = callback

    def set_command_callback(self, callback):
        """Assign callback when a command is received

        Args:
            callback (function): function to assign.
        """
        self.command_callback = callback

    def set_status_request_callback(self, callback):
        """Assign callback when the status is requested

        Args:
            callback (function): function to assign.
        """
        self.status_request_callback = callback

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
        logger.info("Connected to websocket")
        self.retry = False

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

        if not self.retry:
            logger.info("Websocket disconnected from server")
            return

        # attempt to reconnect
        logger.warning("Trying to reconnect in 5 s")
        self.timer = self.create_timer(5, self.run)
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
            logger.debug("Normal deconnection")
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
            logger.error("Websocket connection lost")
            self.retry = True
            self.connection_lost_callback()
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

    def receive_new_entry(self, content):
        """Receive new entry

        Args:
            content (dict): dictionary of the event
        """
        logger.debug("Received new entry {} order".format(content['id']))
        self.new_entry_callback(content)

    def receive_status_request(self, content):
        """Receive status request

        Args:
            content (dict): dictionary of the event
        """
        logger.debug("Received status request")
        self.status_request_callback()

    def receive_command(self, content):
        """Receive a command

        Args:
            content (dict): dictionary of the event
        """
        command = content['command']
        logger.debug("Received command: '{}'".format(command))
        self.command_callback(command)

    def send_entry_error(self, entry_id, message):
        """Tell the server that the current entry cannot be played

        Args:
            entry_id (int): ID of the playlist entry. Must not be `None`.
            message (str): error message.

        Raises:
            ValueError: if `entry_id` is `None`.
        """
        if entry_id is None:
            raise ValueError("Entry with ID None cannot make error")

        logger.debug("Telling the server that entry {} cannot be played"
                     .format(entry_id))
        self.send({
            'type': 'entry_error',
            'data': {
                'entry_id': entry_id,
                'error_message': display_message(message, 255)
            }
        })

    def send_entry_finished(self, entry_id):
        """Tell the server that the current entry is finished

        Args:
            entry_id (int): ID of the playlist entry. Must not be `None`.

        Raises:
            ValueError: if `entry_id` is `None`.
        """
        if entry_id is None:
            raise ValueError("Entry with ID None cannot be finished")

        logger.debug("Telling the server that entry {} is finished"
                     .format(entry_id))
        self.send({
            'type': 'entry_finished',
            'data': {
                'entry_id': entry_id,
            }
        })

        self.entry_id = None

    def send_entry_started(self, entry_id):
        """Tell the server that the current entry has started

        Args:
            entry_id (int): ID of the playlist entry. Must not be `None`.

        Raises:
            ValueError: if `entry_id` is `None`.
        """
        if entry_id is None:
            raise ValueError("Entry with ID None cannot be started")

        logger.debug("Telling the server that entry {} has started"
                     .format(entry_id))
        self.send({
            'type': 'entry_started',
            'data': {
                'entry_id': entry_id,
            }
        })

    def send_status(self, entry_id, timing=0,
                    paused=False, in_transition=False):
        """Send the player status

        Args:
            entry_id (int): ID of the playlist entry currently played. Can be
                `None` if the player is idle.
            timing (int): position of the player (in ms).
            paused (bool): true if the player is paused.
        """
        if entry_id is not None:
            logger.debug(
                "Sending status: in {} for entry {} at {} s {}".format(
                    'pause' if paused else 'play',
                    entry_id,
                    timing / 1000,
                    '(in transition)' if in_transition else ''
                )
            )

        else:
            logger.debug("Sending status: player is idle")

        self.send({
            'type': 'status',
            'data': {
                'entry_id': entry_id,
                'timing': int(timing / 1000),
                'paused': paused,
                'in_transition': in_transition
            }
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
