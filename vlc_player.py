import vlc
import os
import logging
import urllib
from threading import Thread
from settings import KARA_FOLDER_PATH, \
                     FULLSCREEN_MODE, \
                     VLC_PARAMETERS_INSTANCE, \
                     VLC_PARAMETERS_MEDIA, \
                     LOADER_BG_DEFAULT_NAME


class VlcPlayer:
    
    def __init__(self):
        if type(VLC_PARAMETERS_INSTANCE) is not str:
            raise ValueError('VLC instance parameters must be a string')

        if type(VLC_PARAMETERS_MEDIA) is not str:
            raise ValueError('VLC media parameters must be a string')

        self.instance = vlc.Instance(VLC_PARAMETERS_INSTANCE)
        self.player = self.instance.media_player_new()
        self.player.set_fullscreen(FULLSCREEN_MODE)
        self.event_manager = self.player.event_manager()
        self.playing_id = None
        # display vlc version
        version = vlc.libvlc_get_version()
        logging.info("VLC " + version.decode())

    def set_song_end_callback(self, callback):
        """ Assign callback for when player reach end of current song
        """
        self.event_manager.event_attach(
                vlc.EventType.MediaPlayerEndReached,
                self.song_end_callback
                )

        self.song_end_external_callback = callback
        
    def song_end_callback(self, event):
        """ Callback called when song end reached occurs
        """
        logging.info("Callback called")
        thread = Thread(target = self.song_end_external_callback)
        thread.start()
    
    def play_song(self, song):
        """ Play music specified
            Args:
                song: dictionnary containing at least id and song['file_path']

        """
        file_path = os.path.join(
                KARA_FOLDER_PATH,
                song["song"]["file_path"]
                )

        # TODO: Check file exists

        logging.info("New song to play: {}".format(
            file_path
            ))

        self.playing_id = song["id"]
        media = self.instance.media_new(
                "file://" + urllib.parse.quote(file_path)
                )

        media.add_options(VLC_PARAMETERS_MEDIA)
        self.player.set_media(media)
        self.player.play()
        logging.info("Playing {name}".format(name=song['song']['title']))

    def play_idle_screen(self):
        """ Play looping idle screen
        """
        self.playing_id = None
        media = self.instance.media_new_path(
                LOADER_BG_DEFAULT_NAME
                )
        media.add_options("image-duration=10000")
        self.player.set_media(media)
        self.player.play()
        logging.info("Playing Idle screen")

    def is_idle(self):
        """ Return false when playing a song
            true when playing idle screen
        """
        return self.playing_id is None

    def get_playing_id(self):
        """ Return current playing id
            or None when no song is playing
        """
        return self.playing_id

    def get_timing(self):
        """ Return current song timing if a song is playing
            or 0 when idle
        """
        if self.is_idle():
            return 0

        timing = self.player.get_time()
        if timing == -1:
            timing = 0

        return timing


    def is_paused(self):
        """ Return true when playing song is paused
        """
        return self.player.get_state() == vlc.State.Paused

    def set_pause(self, pause):
        """ Pause playing song when true
            unpause when false
        """
        if not self.is_idle():
            if pause:
                self.player.pause()
            
            else:
                self.player.play()
        logging.info("Setting pause to " + str(pause))



    def stop(self):
        """ Stop playing music
        """
        self.player.stop()
        logging.info("Stopping player")



