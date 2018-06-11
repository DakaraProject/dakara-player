import logging
import urllib.parse

import requests


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


class DakaraServer:
    """Object representing a connection with the Dakara server

    Args:
        config (dict): config of the server.
    """
    def __init__(self, config):
        # setting config
        self.server_url = urllib.parse.urljoin(config['url'], 'api/')

        # authentication
        self.token = None
        self.login = config['login']
        self.password = config['password']

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
    def _get_token_header(self):
        """Get the connection token as it should appear in the header

        Can be called only once login has been sucessful.

        Returns:
            dict: formatted token.
        """
        return {
            'Authorization': 'Token ' + self.token
        }

    @authenticated
    def get_next_song(self):
        """Request next song from the server

        Returns:
            dict: next playlist entry or `None` if there is no more song
            in the playlist.
        """
        logger.debug("Asking new song to server")
        try:
            response = requests.get(
                self.server_url + "playlist/device/status/",
                headers=self._get_token_header()
            )

        except requests.exceptions.RequestException:
            logger.error("Network error")
            return None

        if response.ok:
            json = response.json()
            return json or None

        logger.error("Unable to get new song response from server")
        logger.debug("Error {code}: {message}".format(
            code=response.status_code,
            message=display_message(response.text)
        ))

        return None

    @authenticated
    def send_error(self, playing_id, error_message):
        """Send provided error message to the server

        Args:
            playing_id (int): ID of the playlist entry that failed.
            error_message (str): message explaining the error.
        """
        logger.debug(("Sending error to server: playing ID {playing_id}, "
                      "{message}").format(
                          playing_id=playing_id,
                          message=error_message
                      ))

        data = {
            "playlist_entry": playing_id,
            "error_message": error_message,
        }

        try:
            response = requests.post(
                self.server_url + "playlist/device/error/",
                headers=self._get_token_header(),
                json=data
            )

        except requests.exceptions.RequestException:
            logger.error("Network error")
            return

        if not response.ok:
            logger.error("Unable to send error message to server")
            logger.debug("Error {code}: {message}".format(
                code=response.status_code,
                message=display_message(response.text)
            ))

    @authenticated
    def send_status_get_commands(self, playing_id, timing=0, paused=False):
        """Send current status to the server

        If the connexion with the server cannot be established or if the status
        recieved is not consistent, pause the player.

        Args:
            playing_id (int): ID of the playlist entry that is currently
                playing. If `None`, the player tells it is not playing
                anything.
            timing (int): amount of milliseconds that has been spent since the
                media started to play.
            paused (bool): flag wether the player is paused or not.

        Returns:
            dict: requested status from the server.
        """
        logger.debug(("Sending status to server: playing ID {playing_id}, at "
                      "{timing} s, {paused}").format(
                          playing_id=playing_id,
                          timing=timing,
                          paused="in pause" if paused else "playing"
                      ))

        data = {
            "playlist_entry_id": playing_id,
            "timing": timing/1000.,
            "paused": paused
            }

        try:
            response = requests.put(
                self.server_url + "playlist/device/status/",
                headers=self._get_token_header(),
                json=data,
            )

        except requests.exceptions.RequestException:
            logger.error("Network error")
            return {'pause': True, 'skip': False}

        if response.ok:
            return response.json()

        logger.error("Unable to send status to server")
        logger.debug("Error {code}: {message}".format(
            code=response.status_code,
            message=display_message(response.text)
        ))

        return {'pause': True, 'skip': False}


def display_message(message, limit=100):
    """Display the 100 first characters of a message
    """
    if len(message) <= limit:
        return message

    return message[:limit].strip() + "..."


class AuthenticationError(Exception):
    """Error raised when authentication fails
    """


class NetworkError(Exception):
    """Error raised when the communication fails during a critical task
    """
