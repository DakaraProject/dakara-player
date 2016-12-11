import vlc
import os
import logging
import urllib
from threading import Thread
from transition_screen import TransitionScreen
from settings import KARA_FOLDER_PATH, \
                     FULLSCREEN_MODE, \
                     VLC_PARAMETERS_INSTANCE, \
                     VLC_PARAMETERS_MEDIA, \
                     LOADER_DURATION, \
                     LOADER_BG_DEFAULT_NAME


class VlcPlayer:
 
    def __init__(self):
        if type(VLC_PARAMETERS_INSTANCE) is not str:
            raise ValueError('VLC instance parameters must be a string')

        if type(VLC_PARAMETERS_MEDIA) is not str:
            raise ValueError('VLC media parameters must be a string')

        # playlist entry id of the current song
        # if no songs are playing, is None
        self.playing_id = None

        # flag set to True is a transition screen is playing
        self.in_transition = False

        # media containing a song which will play after the transition screen
        self.media_pending = None

        # VLC objects
        self.instance = vlc.Instance(VLC_PARAMETERS_INSTANCE)
        self.player = self.instance.media_player_new()
        self.player.set_fullscreen(FULLSCREEN_MODE)
        self.event_manager = self.player.event_manager()

        # transition screen
        self.transition_screen = TransitionScreen()

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
        logging.debug("Song end callback called")

        # if the transition screen has finished,
        # request to play the song itself
        if self.in_transition:
            self.in_transition = False
            thread = Thread(
                    target=self.play_media,
                    args=(self.media_pending, )
                    )

        # otherwise, the song has finished,
        # so do what should be done
        else:
            thread = Thread(target=self.song_end_external_callback)

        thread.start()

    def play_media(self, media):
        """ Play the given media

            Args:
                media: VLC media object
        """
        self.player.set_media(media)
        self.player.play()

    def set_error_callback(self, callback):
        """ Assign callback for when error occured
        """
        self.event_manager.event_attach(
                vlc.EventType.MediaPlayerEncounteredError,
                self.error_callback
                )

        self.error_external_callback = callback

    def error_callback(self, event):
        """ Callback called when error occurs
        """
        logging.debug("Error callback called")
        error_message = vlc.libvlc_errmsg() or "No details, consult player logs"
        if type(error_message) is bytes:
            error_message = error_message.decode()

        thread = Thread(
                target=self.error_external_callback,
                args=(
                    self.playing_id,
                    error_message
                    )
                )

        self.playing_id = None
        self.in_transition = False

        thread.start()

    def play_song(self, playlist_entry):
        """ Play music specified
            Add a transition screen
            Args:
                playlist_entry: dictionnary containing at least id and song['file_path']

        """
        # file location
        file_path = os.path.join(
                KARA_FOLDER_PATH,
                playlist_entry["song"]["file_path"]
                )

        # Check file exists
        if not os.path.isfile(file_path):
            self.error_external_callback(
                    playlist_entry['id'],
                    "File not found: " + file_path
                    )
            return

        # create the media
        self.playing_id = playlist_entry["id"]
        self.media_pending = self.instance.media_new_path(file_path)
        self.media_pending.add_options(VLC_PARAMETERS_MEDIA)

        # create the transition screen
        loader_bg_path, loader_text_path = self.transition_screen.create_loader(playlist_entry)
        media_transition = self.instance.media_new_path(loader_bg_path)
        media_transition.add_options(
                *VLC_PARAMETERS_MEDIA,
                "sub-file={}".format(loader_text_path),
                "image-duration={}".format(LOADER_DURATION)
                )
        self.in_transition = True

        self.play_media(media_transition)
        logging.info("Playing transition for {name}".format(name=playlist_entry['song']['title']))

    def play_idle_screen(self):
        """ Play idle screen
        """
        self.playing_id = None
        self.in_transition = False
        media = self.instance.media_new_path(
                LOADER_BG_DEFAULT_NAME
                )

        media.add_options("image-duration={}".format(10000))
        self.play_media(media)
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
        if self.is_idle() or self.in_transition:
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

    def clean(self):
        self.stop()
        self.transition_screen.clean()
