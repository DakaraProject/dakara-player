import logging
import urllib.parse
import json

import requests
from websocket import (WebSocket, create_connection,
                       WebSocketConnectionClosedException,
                       WebSocketBadStatusException)

from dakara_player_vlc.safe_workers import WorkerSafeThread

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
            "Unable to send status to server, error {code}: {message}".format(
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


class JsonWebSocket(WebSocket):
    """Helper class which auto-decode end encode JSON data
    """
    def recv(self):
        event = super().recv()
        try:
            self.recv_json(json.loads(event))

        # if the response is not in JSON format, assume this is an error
        except json.JSONDecodeError:
            self.recv_error(event)

        return event

    def recv_json(self, content):
        """Receive data as a dictionary

        Args:
            content (dict): dictionary representation of the event.
        """
        pass

    def recv_error(self, message):
        """Receive data as an error

        The error is displayed truncated.

        Args:
            message (str): error message from the server
        """
        logger.error("Error from the server: '{}'".format(
            display_message(message)))

    def send_json(self, content, *args, **kwargs):
        """Send data as dictionary

        Convert it to JSON string before send.

        Args:
            content (dict): dictionary of the event.
        """
        return self.send(json.dumps(content), *args, **kwargs)


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


class DakaraServerWebSocketConnection(WorkerSafeThread):
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

        self.thread = self.create_thread(target=self.run)

    def create_connection(self):
        """Create the WebSocket connection with the server

        Raises:
            AuthenticationError: if the user account used does not have enough
                rights.
            NetworkError: if the server is unreachable.
        """
        logger.debug("Creating websocket connection")
        try:
            self.websocket = create_connection(self.server_url,
                                               class_=DakaraServerWebSocket,
                                               header=self.header)

        except WebSocketBadStatusException as error:
            raise AuthenticationError("Unable to connect to server with this "
                                      "login") from error

        except ConnectionRefusedError as error:
            raise NetworkError("Network error, unable to talk to the server "
                               "for WebSocket connection") from error

    @connected
    def run(self):
        """Event loop

        Read new messages from the server. The wait is cancelled by the
        `websocket.abort` method.
        """
        try:
            # one event is read at each loop
            # the loop is blocking
            while not self.stop.is_set():
                self.websocket.next()

        except WebSocketConnectionClosedException:
            pass

    def exit_worker(self, *args, **kwargs):
        logger.debug("Aborting websocket connection")
        self.websocket.abort()


class DakaraServerWebSocket(JsonWebSocket):
    """Object representing the WebSocket communications with the Dakara server
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # initialize the callbacks
        self.idle_callback = lambda: None
        self.new_entry_callback = lambda entry: None
        self.command_callback = lambda command: None
        self.status_request_callback = lambda: None

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

    def recv_json(self, content):
        """Receive all incoming events

        Args:
            content (dict): dictionary of the event

        Raises:
            ValueError: if the event type is not associated with any method of
                the class.
        """
        method_name = "recv_{}".format(content['type'])
        if not hasattr(self, method_name):
            raise ValueError("Event of unknown type received '{}'"
                             .format(content['type']))

        getattr(self, method_name)(content.get('data'))

    def recv_idle(self, content):
        """Receive idle order

        Args:
            content (dict): dictionary of the event
        """
        logger.debug("Received idle order")
        self.idle_callback()

    def recv_new_entry(self, content):
        """Receive new entry

        Args:
            content (dict): dictionary of the event
        """
        logger.debug("Received new entry {} order".format(content['id']))
        self.new_entry_callback(content)

    def recv_status_request(self, content):
        """Receive status request

        Args:
            content (dict): dictionary of the event
        """
        logger.debug("Received status request")
        self.status_request_callback()

    def recv_command(self, content):
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
            RuntimeError: if `entry_id` is `None`.
        """
        if entry_id is None:
            raise RuntimeError("Entry with ID None cannot make error")

        logger.debug("Telling the server that entry {} cannot be played"
                     .format(entry_id))
        self.send_json({
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
            RuntimeError: if `entry_id` is `None`.
        """
        if entry_id is None:
            raise RuntimeError("Entry with ID None cannot be finished")

        logger.debug("Telling the server that entry {} is finished"
                     .format(entry_id))
        self.send_json({
            'type': 'entry_finished',
            'data': {
                'entry_id': entry_id,
            }
        })

        self.entry_id = None

    def send_status(self, entry_id, timing=0, paused=False):
        """Send the player status

        Args:
            entry_id (int): ID of the playlist entry currently played. Can be
                `None` if the player is idle.
            timing (int): position of the player (in ms).
            paused (bool): true if the player is paused.
        """
        logger.debug("Sending status")
        self.send_json({
            'type': 'status',
            'data': {
                'entry_id': entry_id,
                'timing': timing / 1000,
                'paused': paused,
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
