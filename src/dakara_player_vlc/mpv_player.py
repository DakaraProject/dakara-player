import logging
import urllib
from pkg_resources import parse_version
from threading import Timer

import mpv
from dakara_base.exceptions import DakaraError
from dakara_base.safe_workers import Worker
from path import Path

from dakara_player_vlc.background_loader import BackgroundLoader
from dakara_player_vlc.resources_manager import PATH_BACKGROUNDS
from dakara_player_vlc.text_generator import TextGenerator
from dakara_player_vlc.version import __version__


TRANSITION_BG_NAME = "transition.png"
TRANSITION_TEXT_NAME = "transition.ass"
TRANSITION_DURATION = 2

IDLE_BG_NAME = "idle.png"
IDLE_TEXT_NAME = "idle.ass"
IDLE_DURATION = 300

logger = logging.getLogger(__name__)


class VlcPlayer(Worker):
    """Interface for the Python VLC wrapper

    This class allows to manipulate VLC for complex tasks. It manages the
    display of idle/transition screens when playing, manages the VLC callbacks
    and provides some accessors and mutators to get/set the status of the
    player.

    The playlist is virtually handled using song-end callbacks.

    After being instanciated, the object must be loaded with `load`.

    Attributes:
        text_generator (TextGenerator): generator of on-screen texts.
        callbacks (dict): dictionary of external callbacs that are run by VLC
            on certain events. They must be set with `set_callback`.
        vlc_callback (dict): dictionary of callbacks associated to VLC events.
            They must be set with `set_vlc_callback`.
        durations (dict): dictionary of durations for screens.
        fullscreen (bool): is the player running fullscreen flag.
        kara_folder_path (path.Path): path to the root karaoke folder containing
            songs.
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
        playing_id (int): playlist entry id of the current song if no songs are
            playing, its value is None.
        in_transition (bool): flag set to True is a transition screen is
            playing.
        media_pending (vlc.Media): media containing a song which will be played
            after the transition screen.

    Args:
        stop (Event): event to stop the program.
        errors (Queue): queue of errors.
        config (dict): configuration.
        tempdir (path.Path): path to a temporary directory.
    """

    def init_worker(self, config, tempdir):
        """Init the worker
        """
        # callbacks
        self.callbacks = {}
        self.vlc_callbacks = {}

        # karaoke parameters
        self.fullscreen = config.get("fullscreen", False)
        self.kara_folder_path = Path(config.get("kara_folder", ""))

        # set durations
        config_durations = config.get("durations") or {}
        self.durations = {
            "transition": config_durations.get(
                "transition_duration", TRANSITION_DURATION
            ),
            "idle": IDLE_DURATION,
        }

        # set text generator
        config_texts = config.get("templates") or {}
        self.text_generator = TextGenerator(config_texts)

        # set background loader
        # we need to make some adaptations here
        config_backgrounds = config.get("backgrounds") or {}
        self.background_loader = BackgroundLoader(
            directory=Path(config_backgrounds.get("directory", "")),
            default_directory=Path(PATH_BACKGROUNDS),
            background_filenames={
                "transition": config_backgrounds.get("transition_background_name"),
                "idle": config_backgrounds.get("idle_background_name"),
            },
            default_background_filenames={
                "transition": TRANSITION_BG_NAME,
                "idle": IDLE_BG_NAME,
            },
        )

        # set VLC objects
        config_vlc = config.get("vlc") or {}
        self.media_parameters = config_vlc.get("media_parameters") or []
        self.media_parameters_text_screen = []
        self.player = mpv.MPV()

        # set path of ASS files for text screens
        self.idle_text_path = tempdir / IDLE_TEXT_NAME
        self.transition_text_path = tempdir / TRANSITION_TEXT_NAME

        # playlist entry id of the current song
        # if no songs are playing, its value is None
        self.playing_id = None

        # flag set to True is a transition screen is playing
        self.in_transition = False

        # media containing a song which will be played after the transition
        # screen
        self.media_pending = None

        # set default callbacks
        self.set_default_callbacks()

    def load(self):
        """Prepare the instance

        Perform actions with side effects.
        """
        # check MPV version
        self.check_mpv_version()

        # check kara folder
        self.check_kara_folder_path()

        # set VLC fullscreen
        self.player.fullscreen = self.fullscreen

        # load text generator
        self.text_generator.load()

        # load backgrounds
        self.background_loader.load()

    def check_mpv_version(self):
        """Print the mpv version and perform some parameter adjustements
        """
        # get and log version
        logger.info(self.player.mpv_version)

    def check_kara_folder_path(self):
        """Check the kara folder is valid
        """
        if not self.kara_folder_path.exists():
            raise KaraFolderNotFound(
                'Karaoke folder "{}" does not exist'.format(self.kara_folder_path)
            )

    def set_default_callbacks(self):
        """Set all the default callbacks
        """
        # set VLC callbacks
#        self.set_vlc_callback(
#            vlc.EventType.MediaPlayerEncounteredError, self.handle_encountered_error
#        )

        @self.player.event_callback('end_file')
        def end_file_callback(event):
            self.handle_end_reached(event)

        # set dummy callbacks that have to be defined externally
        self.set_callback("started_transition", lambda playlist_entry_id: None)
        self.set_callback("started_song", lambda playlist_entry_id: None)
        self.set_callback("could_not_play", lambda playlist_entry_id: None)
        self.set_callback("finished", lambda playlist_entry_id: None)
        self.set_callback("paused", lambda playlist_entry_id, timing: None)
        self.set_callback("resumed", lambda playlist_entry_id, timing: None)
        self.set_callback("error", lambda playlist_entry_id, message: None)

    def set_callback(self, name, callback):
        """Assign an arbitrary callback

        Callback is added to the `callbacks` dictionary.

        Args:
            name (str): name of the callback in the `callbacks` attribute.
            callback (function): function to assign.
        """
        self.callbacks[name] = callback

    def set_vlc_callback(self, event, callback):
        """Assing an arbitrary callback to an VLC event

        Callback is attached to the VLC event manager and added to the
        `vlc_callbacks` dictionary.

        Args:
            event (vlc.EventType): VLC event to attach the callback to, name of
                the callback in the `vlc_callbacks` attribute.
            callback (function): function to assign.
        """
        pass

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
        if (event['event']['reason'] != mpv.MpvEventEndFile.EOF):
            return

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
#            file_path = mrl_to_path(self.media_pending.get_mrl())
            logger.info("Now playing '%s'", self.media_pending)

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

#    def handle_encountered_error(self, event):
#        """Callback called when error occurs
#
#        Try to get error message and then call the callbacks
#        `callbackss["finished"]` and `callbacks["error"]`
#
#        Args:
#            event (vlc.EventType): VLC event object.
#        """
#        logger.debug("Error callback called")
#
#        message = "Unable to play current media"
#        logger.error(message)
#        self.callbacks["finished"](self.playing_id)
#        self.callbacks["error"](self.playing_id, message)
#
#        # reset current state
#        self.playing_id = None
#        self.in_transition = False

    def play_media(self, media):
        """Play the given media

        Args:
            media (vlc.Media): VLC media object.
        """
        self.player.play(media)

    def play_playlist_entry(self, playlist_entry):
        """Play the specified playlist entry

        Prepare the media containing the song to play and store it. Add a
        transition screen and play it first. When the transition ends, the song
        will be played.

        Args:
            playlist_entry (dict): dictionnary containing at least `id` and
                `song` attributes. `song` is a dictionary containing at least
                the key `file_path`.
        """
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
        self.media_pending = str(file_path)

        # create the transition screen
        with self.transition_text_path.open("w", encoding="utf8") as file:
            file.write(self.text_generator.create_transition_text(playlist_entry))

        media_transition = str(self.background_loader.backgrounds["transition"])

#        media_transition.add_options(
#            *self.media_parameters_text_screen,
#            *self.media_parameters,
#            "sub-file={}".format(self.transition_text_path),
#            "image-duration={}".format(self.durations["transition"]),
#        )

        # Necessary to stop the idle screen
        self.player.command("stop")

        self.in_transition = True

        self.player.image_display_duration = int(self.durations["transition"])
        self.play_media(media_transition)
        logger.info("Playing transition for '%s'", file_path)
        self.callbacks["started_transition"](playlist_entry["id"])

    def play_idle_screen(self):
        """Play idle screen
        """
        # set idle state
        self.playing_id = None
        self.in_transition = False

        # create idle screen media
        media = str(self.background_loader.backgrounds["idle"])

        # create the idle screen
        with self.idle_text_path.open("w", encoding="utf8") as file:
            file.write(
                self.text_generator.create_idle_text(
                    {
                        "notes": [
                            self.player.mpv_version,
                            "Dakara player " + __version__,
                        ]
                    }
                )
            )

#        media.add_options(
#            *self.media_parameters_text_screen,
#            *self.media_parameters,
#            "image-duration={}".format(self.durations["idle"]),
#            "sub-file={}".format(self.idle_text_path),
#        )

        self.player.image_display_duration = "inf"
        self.play_media(media)
        logger.debug("Playing idle screen")

    def is_idle(self):
        """Get player idling status

        Returns:
            bool: False when playing a song or a transition screen, True when
                playing idle screen.
        """
        return self.playing_id is None

    def get_playing_id(self):
        """Playlist entry ID getter

        Returns:
            int: current playing ID or None when no song is playing.
        """
        return self.playing_id

    def get_timing(self):
        """Player timing getter

        Returns:
            int: current song timing in seconds if a song is playing or 0 when
                idle or during transition screen.
        """
        if self.is_idle() or self.in_transition:
            return 0

        return int(self.player.time_pos)

    def is_paused(self):
        """Player pause status getter

        Returns:
            bool: True when playing song is paused.
        """
        return self.player.pause

    def set_pause(self, pause):
        """Pause or unpause the player

        Pause playing song when True unpause when False.

        Args:
            pause (bool): flag for pause state requested.
        """
        if not self.is_idle():
            if pause:
                if self.is_paused():
                    logger.debug("Player already in pause")
                    return

                logger.info("Setting pause")
                self.player.pause = True
                logger.debug("Set pause")
                self.callbacks["paused"](self.playing_id, self.get_timing())

            else:
                if not self.is_paused():
                    logger.debug("Player already playing")
                    return

                logger.info("Resuming play")
                self.player.pause = False
                logger.debug("Resumed play")
                self.callbacks["resumed"](self.playing_id, self.get_timing())

    def stop_player(self):
        """Stop playing music
        """
        logger.info("Stopping player")

        # send a warning within 3 seconds if VLC has not stopped already
        timer_stop_player_too_long = Timer(3, self.warn_stop_player_too_long)

        timer_stop_player_too_long.start()
        self.player.terminate()

        # clear the warning
        timer_stop_player_too_long.cancel()

        logger.debug("Stopped player")

    @staticmethod
    def warn_stop_player_too_long():
        """Notify the user that VLC takes too long to stop
        """
        logger.warning("VLC takes too long to stop")

    def exit_worker(self, exception_type, exception_value, traceback):
        """Exit the worker
        """
        self.stop_player()


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


class KaraFolderNotFound(DakaraError):
    """Error raised when the kara folder cannot be found
    """
