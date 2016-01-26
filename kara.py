import vlc
import time
import requests
import os
from settings import KARA_FOLDER_PATH, SERVER_URL, CREDENTIALS, LOGGING_LEVEL

import logging
logging_level_numeric = getattr(logging, LOGGING_LEVEL.upper(), None)
if not isinstance(logging_level_numeric, int):
    raise ValueError('Invalid log level: {}'.format(LOGGING_LEVEL))
logging.basicConfig(
        format='[%(asctime)s][%(levelname)s] %(message)s',
        level=logging_level_numeric
        )
# Disable requests log messages
logging.getLogger("requests").setLevel(logging.WARNING)

def get_next_song():
    """ Request next song from the server
        return json of next playlist_entry or None if there is no more song in the playlist
    """
    logging.debug("Asking new song to server")
    response = requests.get(SERVER_URL + "player/status/", auth=CREDENTIALS)
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
    response = requests.put(SERVER_URL + "player/status/", json=data, auth=CREDENTIALS)
    if response.ok:
        return response.json()
    else:
        logging.error("Unable to send status to server")

def daemon():
    instance = vlc.Instance()
    player = instance.media_player_new()
    logging.info("Daemon started")

    i = 0
    playing_id = None
    idle = True

    while True:
        player_state = player.get_state()
        timing = player.get_time()
        if timing == -1:
            timing = 0 

        if player_state == vlc.State.Ended or player_state == vlc.State.NothingSpecial:
            #request next music to play from server
            next_song = get_next_song()

            if next_song:
                file_path = os.path.join(KARA_FOLDER_PATH,next_song["song"]["file_path"])
                logging.info("New song to play: {}".format(file_path))
                if os.path.isfile(file_path):
                    media = instance.media_new("file://" + file_path)
                    player.set_media(media)
                    player.play()
                    playing_id = next_song["id"]
                    idle = False
                    #TODO : error management

                   # while not player.is_playing():
                   #     pass
                else:
                    logging.error("File not found")
            else:
                logging.info("Player idle")
                playing_id = None
                if not idle:
                    server_status(playing_id,0,False)
                    idle = True
                time.sleep(1)

        if i >= 30:
            #send status to server
            requested_status = server_status(playing_id, timing, player_state == vlc.State.Paused)
            if requested_status["pause"] and player_state == vlc.State.Playing:
                player.pause()
            elif not requested_status["pause"] and player_state == vlc.State.Paused:
                player.play()
            i = 0
        else:
            i += 1

        time.sleep(0.1)

if __name__ == "__main__":
    try:
        daemon()
    except KeyboardInterrupt:
        logging.info("Exiting normally")
