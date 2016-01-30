import vlc
import time
import requests
import os
import logging
from settings import KARA_FOLDER_PATH, \
                     SERVER_URL, \
                     CREDENTIALS, \
                     LOGGING_LEVEL, \
                     DELAY_BETWEEN_REQUESTS, \
                     REQUESTS_LOGGING_DISABLED

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

# Disable requests log messages
if REQUESTS_LOGGING_DISABLED:
    logging.getLogger("requests").setLevel(logging.WARNING)

##
# Enums
#

class Status:
    """ Enum for player statuses
    """
    STOPPED, START, PLAYING, ERROR = range(4)

##
# Routines
#

def get_next_song():
    """ Request next song from the server
        return json of next playlist_entry or None if there is no more
        song in the playlist
    """
    logging.debug("Asking new song to server")
    response = requests.get(
            SERVER_URL + "player/status/",
            auth=CREDENTIALS
            )
    if response.ok:
        json = response.json()
        return json or None

    logging.error("Unable to get new song response from server")
    return None

def server_status(playing_id, timing, paused):
    """ Send current status to the server
        return requested status from the server
    """
    logging.debug("Sending status to server")
    data = {
        "playlist_entry": playing_id,
        "timing": timing/1000.,
        "paused": paused
        }
    response = requests.put(
            SERVER_URL + "player/status/",
            json=data,
            auth=CREDENTIALS)
    if response.ok:
        return response.json()

    logging.error("Unable to send status to server")
    return None

def daemon():
    instance = vlc.Instance()
    player = instance.media_player_new()
    logging.info("Daemon started")

    playing_id = None
    previous_request_time = 0
    previous_status = Status.START
    skip = False

    while True:
        ##
        # First case
        # player is playing
        #

        if player.get_state() in (
                vlc.State.Playing,
                vlc.State.Opening,
                vlc.State.Buffering,
                vlc.State.Paused
                ):
            # if we just switched state, or the previous request we
            # sent was more than DELAY_BETWEEN_REQUEST seconds ago
            if previous_status != Status.PLAYING \
                    or time.time() - previous_request \
                        > DELAY_BETWEEN_REQUESTS:
                previous_request = time.time()
                # get timing
                timing = player.get_time()
                if timing == -1:
                    timing = 0 

                # send status to server
                requested_status = server_status(
                        playing_id,
                        timing,
                        player.get_state() == vlc.State.Paused
                        )

                # manage pause request
                if requested_status["pause"] \
                        and player.get_state() == vlc.State.Playing:
                    player.pause()
                    logging.info("Player is now paused")

                elif not requested_status["pause"] \
                        and player.get_state() == vlc.State.Paused:
                    player.play()
                    logging.info("Player resumed play")

                # manage skip request
                if requested_status["skip"]:
                    # wanted to do a simple player.stop() but
                    # it closes the window
                    skip = True

            previous_status = Status.PLAYING

        ##
        # Second case
        # player has stopped or a skip request is issued
        #

        if skip or player.get_state() in (
                vlc.State.Ended,
                vlc.State.NothingSpecial,
                vlc.State.Stopped
                ):
            if skip:
                logging.info("Song skipped")
            skip = False
            # if we juste switched states, or the last request we
            # sent was more than DELAY_BETWEEN_REQUEST seconds ago
            if previous_status != Status.STOPPED \
                    or time.time() - previous_song_request \
                        > DELAY_BETWEEN_REQUESTS:
                previous_song_request = time.time()
                # request next music to play from server
                next_song = get_next_song()

                if next_song:
                    file_path = os.path.join(
                            KARA_FOLDER_PATH,
                            next_song["song"]["file_path"]
                            )
                    logging.info("New song to play: {}".format(
                        file_path
                        ))

                    # don't check file exists: handling any kind of error
                    # (file missing, invalid file...) in the same place;
                    # see third case below

                    media = instance.media_new("file://" + file_path)
                    player.set_media(media)
                    player.play()
                    playing_id = next_song["id"]

                else:
                    logging.info("Player idle")
                    playing_id = None
                    player.stop()
                    server_status(
                            playing_id,
                            0,
                            False
                            )

            previous_status = Status.STOPPED

        ##
        # Third case
        # error while playing
        #

        if player.get_state() == vlc.State.Error:
            logging.error("Error while playing {}".format(
                file_path
                ))
            player.stop()
            playing_id = None
            previous_status = Status.ERROR
            # No error management server side,
            # can only exit to avoid infinite looping trying to
            # play the same file again and again
            raise Exception('Error while playing')

        #wait between each loop
        time.sleep(0.1)


if __name__ == "__main__":
    try:
        daemon()
    except KeyboardInterrupt:
        logging.info("Exiting normally")
        exit(0)
