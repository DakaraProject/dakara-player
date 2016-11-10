import vlc
import time
import requests
import os
import logging
import urllib
import shutil
import tempfile
from codecs import open
from enum import Enum
from string import Template
from settings import KARA_FOLDER_PATH, \
                     SERVER_URL, \
                     CREDENTIALS, \
                     LOGGING_LEVEL, \
                     DELAY_BETWEEN_REQUESTS, \
                     REQUESTS_LOGGING_DISABLED, \
                     FULLSCREEN_MODE, \
                     VLC_PARAMETERS_INSTANCE, \
                     VLC_PARAMETERS_MEDIA, \
                     LOADER_TEXT_TEMPLATE_NAME, \
                     LOADER_TEXT_TEMPLATE_DEFAULT_NAME, \
                     LOADER_TEXT_NAME, \
                     LOADER_BG_NAME, \
                     LOADER_BG_DEFAULT_NAME, \
                     LOADER_DURATION


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


class Status(Enum):
    """ Enum for player statuses
    """
    STOPPED, START, PLAYING, ERROR, LOADING = range(5)


##
# Temporary folders
#


tempdir = tempfile.mkdtemp(suffix="dakara")


##
# Routines
#


def send_next_song_status():
    """ Request next song from the server
        return json of next playlist_entry or None if there is no more
        song in the playlist
    """
    logging.debug("Asking new song to server")
    try:
        response = requests.get(
                SERVER_URL + "player/status/",
                auth=CREDENTIALS
                )

    except requests.exceptions.RequestException:
        logging.exception("Network Error")
        return None

    if response.ok:
        json = response.json()
        return json or None

    logging.error("Unable to get new song response from server")
    logging.debug("Error code: {code}\n{message}".format(
        code=response.status_code,
        message=response.text
        ))


def send_error(playing_id, error_message):
    """ Send provided error message to the server
        return nothing
    """
    logging.debug("""Sending error to server:
Playing entry ID:{playing_id}
Error:{error_message}""".format(
        playing_id=playing_id,
        error_message=error_message
        ))

    data = {
            "playlist_entry": playing_id,
            "error_message": error_message,
            }

    try:
        response = requests.post(
                SERVER_URL + "player/error/",
                auth=CREDENTIALS,
                json=data
                )

    except requests.exceptions.RequestException:
        logging.exception("Network Error")
        return

    if not response.ok:
        logging.error("Unable to send error message to server")
        logging.debug("Error code: {code}\n{message}".format(
            code=response.status_code,
            message=response.text
            ))


def send_status(playing_id, timing, paused):
    """ Send current status to the server
        return requested status from the server
    """
    logging.debug("""Sending status to server:
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
                SERVER_URL + "player/status/",
                json=data,
                auth=CREDENTIALS
                )

    except requests.exceptions.RequestException:
        logging.exception("Network Error")
        return {'pause': True, 'skip': False}

    if response.ok:
        return response.json()

    logging.error("Unable to send status to server")
    logging.debug("Error code: {code}\n{message}".format(
        code=response.status_code,
        message=response.text
        ))

    return {'pause': True, 'skip': False}


def get_loader_text_template():
    """ Load the default or customized ASS template for
        transition screen
    """
    if os.path.isfile(LOADER_TEXT_TEMPLATE_NAME):
        loader_ass = LOADER_TEXT_TEMPLATE_NAME

    elif os.path.isfile(LOADER_TEXT_TEMPLATE_DEFAULT_NAME):
        loader_ass = LOADER_TEXT_TEMPLATE_DEFAULT_NAME

    else:
        raise IOError("No ASS file for loader found")

    with open(loader_ass, 'r', encoding='utf8') as file:
        loader_text_template = Template(''.join(file.readlines()))

    return loader_text_template


def get_loader_bg_path():
    """ Give the default or customized background path for
        transition screen
    """
    if os.path.isfile(LOADER_BG_NAME):
        loader_bg = LOADER_BG_NAME

    elif os.path.isfile(LOADER_BG_DEFAULT_NAME):
        loader_bg = LOADER_BG_DEFAULT_NAME

    else:
        raise IOError("No background file for loader found")

    return loader_bg


def daemon():
    if type(VLC_PARAMETERS_INSTANCE) is not str:
        raise ValueError('VLC instance parameters must be a string')
    if type(VLC_PARAMETERS_MEDIA) is not str:
        raise ValueError('VLC media parameters must be a string')
    instance = vlc.Instance(VLC_PARAMETERS_INSTANCE)
    player = instance.media_player_new()
    player.set_fullscreen(FULLSCREEN_MODE)
    version = vlc.libvlc_get_version()
    logging.info("VLC " + version.decode())
    logging.info("Daemon started")

    # load loader template and background
    loader_bg_path = get_loader_bg_path()
    loader_text_template = get_loader_text_template()
    loader_text_path = os.path.join(
            tempdir,
            LOADER_TEXT_NAME
            )

    playing_id = None
    previous_request_time = 0
    previous_status = Status.START
    skip = False
    loader_status = False
    loader_end = 0

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
            if previous_status not in (
                    Status.PLAYING,
                    Status.LOADING,
                    ) or \
                    time.time() - previous_request_time \
                    > DELAY_BETWEEN_REQUESTS:

                # if a loader is playing
                if loader_status:
                    previous_status = Status.LOADING
                    # if loader duration is elapsed
                    if time.time() - loader_end > LOADER_DURATION:
                        # play the preloaded song
                        player.set_media(media)
                        player.play()
                        loader_status = False

                    # no timing for loader
                    timing = 0

                # if a song is playing
                else:
                    previous_status = Status.PLAYING
                    # get timing
                    timing = player.get_time()
                    if timing == -1:
                        timing = 0

                # send status to server
                previous_request_time = time.time()
                requested_status = send_status(
                        playing_id,
                        timing,
                        player.get_state() == vlc.State.Paused
                        )

                # manage pause request
                if requested_status["pause"] and \
                        player.get_state() == vlc.State.Playing:
                    player.pause()
                    logging.info("Player is now paused")

                elif not requested_status["pause"] and \
                        player.get_state() == vlc.State.Paused:
                    player.play()
                    logging.info("Player resumed play")

                # manage skip request
                if requested_status["skip"]:
                    # wanted to do a simple player.stop() but
                    # it closes the window
                    skip = True

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
            if previous_status != Status.STOPPED or \
                    time.time() - previous_request_time \
                    > DELAY_BETWEEN_REQUESTS:
                previous_request_time = time.time()
                # request next music to play from server
                next_song = send_next_song_status()

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

                    # preload media, play loader instead;
                    # the media will be played after, see
                    # first case
                    playing_id = next_song["id"]
                    media = instance.media_new(
                            "file://" + urllib.parse.quote(file_path)
                            )

                    media.add_options(VLC_PARAMETERS_MEDIA)

                    loader_status = True
                    loader_end = time.time() + LOADER_DURATION
                    loader = instance.media_new_path(
                            loader_bg_path
                            )

                    # create custom loader text and save it
                    loader_text = loader_text_template.substitute(
                            title=next_song["song"]["title"],
                            artists=", ".join((a["name"] for a in next_song["song"]["artists"])),
                            works=", ".join((
                                w["work"]["title"] +
                                (" ({})".format(w["work"]["subtitle"]) if w["work"]["subtitle"] else "") +
                                " - " + w["link_type"] +
                                (str(w["link_type_number"]) if w["link_type_number"] else "")
                                for w in next_song["song"]["works"])) \
                                        if next_song["song"]["works"] else ""
                            )

                    with open(loader_text_path, 'w', encoding='utf8') as file:
                        file.write(loader_text)

                    player.set_media(loader)
                    player.play()
                    # have to set subtitle after the video started playing
                    player.video_set_subtitle_file(loader_text_path)

                else:
                    logging.info("Player idle")
                    playing_id = None
                    player.stop()
                    send_status(
                            playing_id,
                            0,
                            False
                            )

            previous_status = Status.STOPPED

        ##
        # Third case
        # error while playing (or not)
        #

        if player.get_state() == vlc.State.Error:
            logging.error("Error while playing {}".format(
                file_path
                ))

            error_message = vlc.libvlc_errmsg().decode() or "No detail"
            player.stop()
            send_error(playing_id, error_message)
            playing_id = None
            previous_status = Status.ERROR

        # wait between each loop
        time.sleep(0.1)

if __name__ == "__main__":
    try:
        daemon()

    except KeyboardInterrupt:
        logging.info("Exiting normally")
        status = 0

    except Exception as e:
        if LOGGING_LEVEL.upper() != "DEBUG":
            logging.critical(e)
            logging.info("Emergency stop")
            status = 1

        else:
            raise

    finally:
        shutil.rmtree(tempdir)

    exit(status)
