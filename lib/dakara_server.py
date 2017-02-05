import requests
import logging


logging.getLogger("requests").setLevel(logging.WARNING)

class DakaraServer:

    def __init__(self, config):
        # create logger
        self.logger = logging.getLogger('DakaraServer')

        # setting config
        self.server_url = config['url'] 
        self.credentials = (config['login'], config['password'])

    def get_next_song(self):
        """ Request next song from the server

            Returns:
                dictionary of next playlist entry or `None` if there
                is no more song in the playlist.
        """
        self.logger.debug("Asking new song to server")
        try:
            response = requests.get(
                    self.server_url + "player/status/",
                    auth=self.credentials
                    )

        except requests.exceptions.RequestException:
            self.logger.error("Network Error")
            return None

        if response.ok:
            json = response.json()
            return json or None

        self.logger.error("Unable to get new song response from server")
        self.logger.debug("""Error code: {code}
Message: {message}""".format(
            code=response.status_code,
            message=response.text
            ))

    def send_error(self, playing_id, error_message):
        """ Send provided error message to the server
        """
        self.logger.debug("""Sending error to server:
Playing entry ID: {playing_id}
Error: {error_message}""".format(
            playing_id=playing_id,
            error_message=error_message
            ))

        data = {
                "playlist_entry": playing_id,
                "error_message": error_message,
                }

        try:
            response = requests.post(
                    self.server_url + "player/error/",
                    auth=self.credentials,
                    json=data
                    )

        except requests.exceptions.RequestException:
            self.logger.error("Network Error")
            return

        if not response.ok:
            self.logger.error("Unable to send error message to server")
            self.logger.debug("""Error code: {code}
Message: {message}""".format(
                code=response.status_code,
                message=response.text
                ))

    def send_status_get_commands(self, playing_id, timing=0, paused=False):
        """ Send current status to the server

            If the connexion with the server cannot be established
            or if the status recieved is not consistent, pause
            the player.

            Returns:
                requested status from the server.
        """
        self.logger.debug("""Sending status to server:
Playing entry ID: {playing_id}
Timing: {timing}
Paused: {paused}""".format(
            playing_id=playing_id,
            timing=timing,
            paused=paused
            ))

        data = {
            "playlist_entry_id": playing_id,
            "timing": timing/1000.,
            "paused": paused
            }

        try:
            response = requests.put(
                    self.server_url + "player/status/",
                    auth=self.credentials,
                    json=data,
                    )

        except requests.exceptions.RequestException:
            self.logger.error("Network Error")
            return {'pause': True, 'skip': False}

        if response.ok:
            return response.json()

        self.logger.error("Unable to send status to server")
        self.logger.debug("""Error code: {code}
Message: {message}""".format(
            code=response.status_code,
            message=response.text
            ))

        return {'pause': True, 'skip': False}
