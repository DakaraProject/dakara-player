import vlc
import os
import logging
import urllib
from threading import Thread
from .transition_text_generator import TransitionTextGenerator, \
                                       TRANSITION_TEMPLATE_PATH

SHARE_DIR = 'share'

TRANSITION_DURATION = 2
TRANSITION_BG_NAME = "transition.png"
TRANSITION_BG_PATH = os.path.join(SHARE_DIR, TRANSITION_BG_NAME)

IDLE_DURATION = 60
IDLE_BG_NAME = "idle.png"
IDLE_BG_PATH = os.path.join(SHARE_DIR, IDLE_BG_NAME)

class VlcPlayer:

    def __init__(self, config):
        # create logger
        self.logger = logging.getLogger('VlcPlayer')

        # parameters for instanciations or saved objects
        instance_parameter = config.get('instanceParameter', "")
        fullscreen = config.getboolean('fullscreen', False)

        # parameters that will be used later on
        self.kara_folder_path = config.get('karaFolder', "")
        self.media_parameter = config.get('mediaParameter', "")

        # parameters for transition screen
        self.transition_duration = config.getfloat(
                'transitionDuration', TRANSITION_DURATION
                )

        self.load_transition_bg_path(
                config.get('transitionBgPath', TRANSITION_BG_PATH)
                )

        transition_template_path = config.get(
                'transitionTemplatePath',
                TRANSITION_TEMPLATE_PATH
                )

        # parameters for idle screen
        self.load_idle_bg_path(
                config.get('idleBgPath', IDLE_BG_PATH)
                )

        # playlist entry id of the current song
        # if no songs are playing, its value is None
        self.playing_id = None

        # flag set to True is a transition screen is playing
        self.in_transition = False

        # media containing a song which will be played after the transition screen
        self.media_pending = None

        # VLC objects
        self.instance = vlc.Instance(instance_parameter)
        self.player = self.instance.media_player_new()
        self.player.set_fullscreen(fullscreen)
        self.event_manager = self.player.event_manager()

        # transition screen
        self.transition_text_generator = TransitionTextGenerator(
                transition_template_path
                )

        # display vlc version
        version = vlc.libvlc_get_version()
        self.logger.info("VLC " + version.decode())

    def load_transition_bg_path(self, bg_path):
        """ Load transition backgound file path

            Load the customized background path or the
            default background path for the transition
            screen.

            Called once by the constructor.

            Args:
                bg_path: path to the transition background.
        """
        if os.path.isfile(bg_path):
            pass

        elif os.path.isfile(TRANSITION_BG_PATH):
            self.logger.warning("Transition background file not found \"{}\", \
using default one".format(bg_path))

            bg_path = TRANSITION_BG_PATH

        else:
            raise IOError("Unable to find a transition background file")

        self.transition_bg_path = bg_path

        self.logger.debug("Loading transition background file \"{}\"".format(
            bg_path
            ))

    def load_idle_bg_path(self, bg_path):
        """ Load idle backgound file path

            Load the customized background path or the
            default background path for the idle
            screen.

            Called once by the constructor.

            Args:
                bg_path: path to the idle background.
        """
        if os.path.isfile(bg_path):
            pass

        elif os.path.isfile(IDLE_BG_PATH):
            self.logger.warning("Idle background file not found \"{}\", \
using default one".format(bg_path))

            bg_path = IDLE_BG_PATH

        else:
            raise IOError("Unable to find an idle background file")

        self.idle_bg_path = bg_path

        self.logger.debug("Loading idle background file \"{}\"".format(
            bg_path
            ))

    def set_song_end_callback(self, callback):
        """ Assign callback for when player reachs the end of current song

            Args:
                callback: function to assign.
        """
        self.event_manager.event_attach(
                vlc.EventType.MediaPlayerEndReached,
                self.song_end_callback
                )

        self.song_end_external_callback = callback

    def song_end_callback(self, event):
        """ Callback called when song end reached occurs

            This can happen when a transition screen ends,
            leading to playing the actual song file,
            or when the song file ends, leading
            to calling the callback set by `set_song_end_callback`.
            A new thread created in any case.

            Args:
                event: VLC event object.
        """
        self.logger.debug("Song end callback called")

        if self.in_transition:
            # if the transition screen has finished,
            # request to play the song itself
            self.in_transition = False
            thread = Thread(
                    target=self.play_media,
                    args=(self.media_pending, )
                    )

            # get file path
            # the file path ist stored as MRL, we have to bring it back
            # to a more classic looking path format
            file_mrl = self.media_pending.get_mrl()
            file_mrl_parsed = urllib.parse.urlparse(file_mrl)
            file_path = urllib.parse.unquote(file_mrl_parsed.path)
            self.logger.info("Now playing \"{}\"".format(
                file_path
                ))

        else:
            # otherwise, the song has finished,
            # so do what should be done
            thread = Thread(target=self.song_end_external_callback)

        thread.start()

    def set_error_callback(self, callback):
        """ Assign callback for when error occured

            Args:
                callback: function to assign.
        """
        self.event_manager.event_attach(
                vlc.EventType.MediaPlayerEncounteredError,
                self.error_callback
                )

        self.error_external_callback = callback

    def error_callback(self, event):
        """ Callback called when error occurs

            Try to get error message and then
            call the callback set by `set_error_callback`.

            Args:
                event: VLC event object.
        """
        self.logger.debug("Error callback called")

        # according to this post in the VLC forum
        # (https://forum.videolan.org/viewtopic.php?t=90720), it is very
        # unlikely that any error message will be caught this way
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

    def play_media(self, media):
        """ Play the given media

            Args:
                media: VLC media object.
        """
        self.player.set_media(media)
        self.player.play()

    def play_song(self, playlist_entry):
        """ Play music specified

            Prepare the media containing the music to play
            and store it. Add a transition screen and play it
            first. When the transition screen ends, the media
            will be played.

            Args:
                playlist_entry: dictionnary containing at least `id` and `song`
                    attributes. `song` is a dictionary containing at least
                    the key `file_path`.
        """
        # file location
        file_path = os.path.join(
                self.kara_folder_path,
                playlist_entry["song"]["file_path"]
                )

        # Check file exists
        if not os.path.isfile(file_path):
            self.error_external_callback(
                    playlist_entry['id'],
                    "File not found \"{}\"".format(file_path)
                    )
            return

        # create the media
        self.playing_id = playlist_entry["id"]
        self.media_pending = self.instance.media_new_path(file_path)
        self.media_pending.add_options(self.media_parameter)

        # create the transition screen
        transition_text_path = self.transition_text_generator.create_transition_text(playlist_entry)
        media_transition = self.instance.media_new_path(self.transition_bg_path)
        media_transition.add_options(
                self.media_parameter,
                "sub-file={}".format(transition_text_path),
                "image-duration={}".format(self.transition_duration)
                )
        self.in_transition = True

        self.play_media(media_transition)
        self.logger.info("Playing transition for \"{}\"".format(file_path))

    def play_idle_screen(self):
        """ Play idle screen
        """
        self.playing_id = None
        self.in_transition = False
        media = self.instance.media_new_path(
                self.idle_bg_path
                )

        media.add_options("image-duration={}".format(IDLE_DURATION))
        self.play_media(media)
        self.logger.debug("Playing idle screen")

    def is_idle(self):
        """ Get player idling status

            Returns:
                False when playing a song
                or a transition screen,
                True when playing idle screen.
        """
        return self.playing_id is None

    def get_playing_id(self):
        """ Playlist entry ID getter

            Returns:
                Current playing ID or None when
                no song is playing.
        """
        return self.playing_id

    def get_timing(self):
        """ Player timing getter

            Returns:
                Current song timing if a song is playing
                or 0 when idle or during transition screen.
        """
        if self.is_idle() or self.in_transition:
            return 0

        timing = self.player.get_time()

        # correct the way VLC handles when it hasn't started to play yet
        if timing == -1:
            timing = 0

        return timing

    def is_paused(self):
        """ Player pause status getter

            Returns:
                True when playing song is paused.
        """
        return self.player.get_state() == vlc.State.Paused

    def set_pause(self, pause):
        """ Pause playing song when True
            unpause when False

            Args:
                pause: flag for pause state requested.
        """
        if not self.is_idle():
            if pause:
                self.player.pause()
                self.logger.info("Setting pause")

            else:
                self.player.play()
                self.logger.info("Resuming play")

    def stop(self):
        """ Stop playing music
        """
        self.player.stop()
        self.logger.info("Stopping player")

    def clean(self):
        """ Stop playing music and clean generated materials
        """
        self.stop()
        self.transition_text_generator.clean()
