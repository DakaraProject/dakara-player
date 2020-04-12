import logging
import urllib
from pkg_resources import parse_version
from threading import Timer

import vlc
from vlc import Instance
from path import Path

from dakara_player_vlc.media_player import MediaPlayer
from dakara_player_vlc.version import __version__
from dakara_base.exceptions import DakaraError


logger = logging.getLogger(__name__)


class VlcMediaPlayer(MediaPlayer):
    """Interface for the Python VLC wrapper

    This class allows to manipulate VLC for complex tasks.

    The playlist is virtually handled using song-end callbacks.

    Attributes:
        vlc_callback (dict): dictionary of callbacks associated to VLC events.
            They must be set with `set_vlc_callback`.
        media_parameters (list): list of parameters for VLC, applied for each
            media.
        media_parameters_text_screen (list): list of parameters for VLC,
            applied for each text screen.
        instance (vlc.Instance): instance of the VLC player.
        player (vlc.MediaPlayer): instance of the VLC media player, attached to
            the player.
        event_manager (vlc.EventManager): instance of the VLC event manager,
            attached to the media player.
        vlc_version (str): version of VLC.
        media_pending (vlc.Media): media containing a song which will be played
            after the transition screen.
    """

    @staticmethod
    def is_available():
        """Check if VLC can be used
        """
        return Instance() is not None

    def init_player(self, config, tempdir):
        # check VLC is available
        if not self.is_available():
            raise VlcNotAvailableError("VLC is not available")

        # set VLC objects
        config_vlc = config.get("vlc") or {}
        self.media_parameters = config_vlc.get("media_parameters") or []
        self.media_parameters_text_screen = []
        self.instance = Instance(config_vlc.get("instance_parameters") or [])
        self.player = self.instance.media_player_new()
        self.event_manager = self.player.event_manager()
        self.vlc_version = None

        # set vlc callbacks
        self.vlc_callbacks = {}
        self.set_vlc_default_callbacks()

        # media containing a song which will be played after the transition
        # screen
        self.media_pending = None

    def load_player(self):
        # check VLC
        self.check_vlc_version()

        # set VLC fullscreen
        self.player.set_fullscreen(self.fullscreen)

    def check_vlc_version(self):
        """Print the VLC version and perform some parameter adjustements
        """
        # get and log version
        self.vlc_version = vlc.libvlc_get_version().decode()
        logger.info("VLC %s", self.vlc_version)

        # VLC version is on the form "x.y.z CodeName"
        # so we split the string to have the version number only
        version_str, _ = self.vlc_version.split()
        version = parse_version(version_str)

        # perform action according to VLC version
        if version >= parse_version("3.0.0"):
            # starting from version 3, VLC prioritizes subtitle files that are
            # nearby the media played, not the ones explicitally added; this
            # option forces VLC to use the explicitally added files only
            self.media_parameters_text_screen.append("no-sub-autodetect-file")

    def set_vlc_default_callbacks(self):
        """Set VLC player default callbacks
        """
        # set VLC callbacks
        self.set_vlc_callback(
            vlc.EventType.MediaPlayerEndReached, self.handle_end_reached
        )
        self.set_vlc_callback(
            vlc.EventType.MediaPlayerEncounteredError, self.handle_encountered_error
        )

    def set_vlc_callback(self, event, callback):
        """Assing an arbitrary callback to an VLC event

        Callback is attached to the VLC event manager and added to the
        `vlc_callbacks` dictionary.

        Args:
            event (vlc.EventType): VLC event to attach the callback to, name of
                the callback in the `vlc_callbacks` attribute.
            callback (function): function to assign.
        """
        self.vlc_callbacks[event] = callback
        self.event_manager.event_attach(event, callback)

    def handle_end_reached(self, event):
        """Callback called when a media ends

        This happens when:
            - A transition screen ends, leading to playing the actual song;
            - A song ends, leading to calling the callback
                `callbacks["finished"]`;
            - An idle screen ends, leading to reloop it.

        A new thread is created in any case.

        Args:
            event (vlc.EventType): VLC event object.
        """
        logger.debug("Song end callback called")

        if self.in_transition:
            # if the transition screen has finished,
            # request to play the song itself
            self.in_transition = False
            thread = self.create_thread(
                target=self.play_media, args=(self.media_pending,)
            )

            thread.start()

            # get file path
            file_path = mrl_to_path(self.media_pending.get_mrl())
            logger.info("Now playing '%s'", file_path)

            # call the callback for when a song starts
            self.callbacks["started_song"](self.playing_id)

            return

        if self.is_idle():
            # if the idle screen has finished, restart it
            thread = self.create_thread(target=self.play_idle_screen)

            thread.start()
            return

        # otherwise, the song has finished,
        # so call the right callback
        self.callbacks["finished"](self.playing_id)

    def handle_encountered_error(self, event):
        """Callback called when error occurs

        Try to get error message and then call the callbacks
        `callbackss["finished"]` and `callbacks["error"]`

        Args:
            event (vlc.EventType): VLC event object.
        """
        logger.debug("Error callback called")

        message = "Unable to play current media"
        logger.error(message)
        self.callbacks["finished"](self.playing_id)
        self.callbacks["error"](self.playing_id, message)

        # reset current state
        self.playing_id = None
        self.in_transition = False

    def play_media(self, media):
        """Play the given media

        Args:
            media (vlc.Media): VLC media object.
        """
        self.player.set_media(media)
        self.player.play()

    def play_playlist_entry(self, playlist_entry):
        # file location
        file_path = self.kara_folder_path / playlist_entry["song"]["file_path"]

        # Check file exists
        if not file_path.exists():
            logger.error("File not found '%s'", file_path)
            self.callbacks["could_not_play"](playlist_entry["id"])
            self.callbacks["error"](
                playlist_entry["id"], "File not found '{}'".format(file_path)
            )

            return

        # create the media
        self.playing_id = playlist_entry["id"]
        self.media_pending = self.instance.media_new_path(str(file_path))
        self.media_pending.add_options(*self.media_parameters)

        # create the transition screen
        with self.transition_text_path.open("w", encoding="utf8") as file:
            file.write(self.text_generator.create_transition_text(playlist_entry))

        media_transition = self.instance.media_new_path(
            self.background_loader.backgrounds["transition"]
        )

        media_transition.add_options(
            *self.media_parameters_text_screen,
            *self.media_parameters,
            "sub-file={}".format(self.transition_text_path),
            "image-duration={}".format(self.durations["transition"]),
        )
        self.in_transition = True

        self.play_media(media_transition)
        logger.info("Playing transition for '%s'", file_path)
        self.callbacks["started_transition"](playlist_entry["id"])

    def play_idle_screen(self):
        # set idle state
        self.playing_id = None
        self.in_transition = False

        # create idle screen media
        media = self.instance.media_new_path(self.background_loader.backgrounds["idle"])

        # create the idle screen
        with self.idle_text_path.open("w", encoding="utf8") as file:
            file.write(
                self.text_generator.create_idle_text(
                    {
                        "notes": [
                            "VLC " + self.vlc_version,
                            "Dakara player " + __version__,
                        ]
                    }
                )
            )

        media.add_options(
            *self.media_parameters_text_screen,
            *self.media_parameters,
            "image-duration={}".format(self.durations["idle"]),
            "sub-file={}".format(self.idle_text_path),
        )

        self.play_media(media)
        logger.debug("Playing idle screen")

    def get_timing(self):
        if self.is_idle() or self.in_transition:
            return 0

        timing = self.player.get_time()

        # correct the way VLC handles when it hasn't started to play yet
        if timing == -1:
            timing = 0

        return timing // 1000

    def is_paused(self):
        return self.player.get_state() == vlc.State.Paused

    def set_pause(self, pause):
        if not self.is_idle():
            if pause:
                if self.is_paused():
                    logger.debug("Player already in pause")
                    return

                logger.info("Setting pause")
                self.player.pause()
                logger.debug("Set pause")
                self.callbacks["paused"](self.playing_id, self.get_timing())

            else:
                if not self.is_paused():
                    logger.debug("Player already playing")
                    return

                logger.info("Resuming play")
                self.player.play()
                logger.debug("Resumed play")
                self.callbacks["resumed"](self.playing_id, self.get_timing())

    def stop_player(self):
        logger.info("Stopping player")

        # send a warning within 3 seconds if VLC has not stopped already
        timer_stop_player_too_long = Timer(3, self.warn_stop_player_too_long)

        timer_stop_player_too_long.start()
        self.player.stop()

        # clear the warning
        timer_stop_player_too_long.cancel()

        logger.debug("Stopped player")

    @staticmethod
    def warn_stop_player_too_long():
        """Notify the user that VLC takes too long to stop
        """
        logger.warning("VLC takes too long to stop")


def mrl_to_path(file_mrl):
    """Convert a MRL to a classic path

    File path is stored as MRL inside a media object, we have to bring it back
    to a more classic looking path format.

    Args:
        file_mrl (str): path to the resource with MRL format.
    """
    path = urllib.parse.urlparse(file_mrl).path
    # remove first '/' if a colon character is found like in '/C:/a/b'
    if path[0] == "/" and path[2] == ":":
        path = path[1:]

    return Path(urllib.parse.unquote(path)).normpath()


class VlcNotAvailableError(DakaraError):
    """Error raised when trying to use the `VlcMediaPlayer` class if VLC cannot be found
    """
