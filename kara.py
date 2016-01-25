import vlc
import time
import requests
import os
from settings import KARA_FOLDER_PATH, SERVER_URL, CREDENTIALS


def get_next_song():
    response = requests.get(SERVER_URL + "player/status/", auth=CREDENTIALS)
    if response.ok:
        json = response.json()
        return json or None
    else:
        print("ca marche pas")


def server_status(playing_id, timing):
    data = {
        "playlist_entry": playing_id,
        "timing": timing/1000.
        }
    response = requests.put(SERVER_URL + "player/status/", json=data, auth=CREDENTIALS)
    if response.ok:
        pass
    else:
        print("server error")

def daemon():
    instance = vlc.Instance()
    player = instance.media_player_new()

    i = 0
    playing_id = None

    while True:
        playing_status = player.is_playing()
        timing = player.get_time()
        if timing == -1:
            timing = 0 

        if not playing_status:
            #request next music to play from server
            next_song = get_next_song()

            if next_song:
                file_path = KARA_FOLDER_PATH + next_song["song"]["file_path"]
                print("song to play : " + file_path)
                if os.path.isfile(file_path):
                    media = instance.media_new("file://" + file_path)
                    player.set_media(media)
                    player.play()
                    playing_id = next_song["id"]
                    #TODO : error management

                    while not player.is_playing():
                        pass
                else:
                    print("file not found")
            else:
                print("idle : nothing to play")
                playing_id = None
                server_status(playing_id,0)    
                time.sleep(1)

        if i >= 30:
            #send status to server
            print("sending status to server")
            server_status(playing_id, timing)
            i = 0
        else:
            i += 1

        time.sleep(0.1)

if __name__ == "__main__":
    daemon()
