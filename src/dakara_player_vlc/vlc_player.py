import logging
import pathlib
from pkg_resources import parse_version
from urllib.parse import unquote, urlparse

# initialize before importing vlc
from dakara_player_vlc.vlc_helper import init

init()

import vlc  # noqa E402
from vlc import Instance  # noqa E402
from path import Path  # noqa E402

from dakara_player_vlc.media_player import (
    MediaPlayer,
    MediaPlayerNotAvailableError,
)  # noqa E402
from dakara_player_vlc.state_manager import State  # noqa E402
from dakara_player_vlc.version import __version__  # noqa E402


logger = logging.getLogger(__name__)


class VlcNotAvailableError(MediaPlayerNotAvailableError):
    """Error raised when trying to use the `VlcMediaPlayer` class if VLC cannot be found
    """


class VlcMediaPlayer(MediaPlayer):
    """Interface for the Python VLC wrapper

    This class allows to manipulate VLC for complex tasks.

    The playlist is virtually handled using song-end callbacks.

    Attributes:
        vlc_callback (dict): dictionary of callbacks associated to VLC events.
            They must be set with `set_vlc_callback`.
        vlc_states (dict): Stores the low level states of the player (i.e.
            playing a transition screen, playing a song, paused, etc.) and is
            updated a posteriori, using VLC callbacks.
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

    player_name = "VLC"
    player_not_available_error_class = VlcNotAvailableError

    @staticmethod
    def is_available():
        """Check if VLC can be used
        """
        return Instance() is not None

    def init_player(self, config, tempdir):
        # states
        self.vlc_states = {}

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
        self.set_vlc_default_states()

        # media containing a song which will be played after the transition
        # screen
        self.media_pending = None

        # ID of the audio track to play of media_pending
        # start at 0
        self.audio_track_id = None

    def load_player(self):
        # set default callbacks
        self.set_default_callbacks()

        # set default states
        self.set_default_states()

        # check VLC
        self.get_version()

        # set VLC fullscreen
        self.player.set_fullscreen(self.fullscreen)

    def get_version(self):
        """Print the VLC version and perform some parameter adjustements

        VLC version is on the form "x.y.z CodeName" in bytes.
        """
        # get and log version
        self.vlc_version = vlc.libvlc_get_version().decode()
        logger.info("VLC %s", self.vlc_version)

        # split the string to have the version number only
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
        self.set_vlc_callback(vlc.EventType.MediaPlayerPlaying, self.handle_playing)
        self.set_vlc_callback(vlc.EventType.MediaPlayerPaused, self.handle_paused)

    def set_vlc_default_states(self):
        """Set all the default states
        """
        self.vlc_states["in_transition"] = State()
        self.vlc_states["in_media"] = State()
        self.vlc_states["in_idle"] = State()
        self.vlc_states["in_pause"] = State()

    def set_vlc_callback(self, event, callback):
        """Assing an arbitrary callback to a VLC event

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

        if self.states["in_song"].is_active():
            if self.vlc_states["in_transition"].is_active():
                # the transition screen has finished, request to play the song
                # itself
                thread = self.create_thread(
                    target=self.play_media, args=(self.media_pending,)
                )

                logger.debug(
                    "Will play '%s'", mrl_to_path(self.media_pending.get_mrl())
                )

                self.vlc_states["in_transition"].finish()
                thread.start()

                return

            if self.vlc_states["in_media"].is_active():
                # the media has finished, so call the according callback
                self.callbacks["finished"](self.playing_id)

                self.vlc_states["in_media"].finish()
                self.states["in_song"].finish()

                return

        if self.states["in_idle"].is_active():
            # the idle screen has finished, simply restart it
            thread = self.create_thread(target=self.play_idle_screen)

            self.vlc_states["in_idle"].finish()
            thread.start()

            return

        # if no state can be determined, raise an error
        raise InvalidStateError("End reached on an undeterminated state")

    def handle_encountered_error(self, event):
        """Callback called when error occurs

        There is no way to capture error message, so only a generic error
        message is provided. Call the callbacks `callbackss["finished"]` and
        `callbacks["error"]`

        Args:
            event (vlc.EventType): VLC event object.
        """
        logger.debug("Error callback called")

        if (
            self.states["in_song"].is_active()
            and self.vlc_states["in_media"].is_active()
        ):
            # the current song media has an error, skip the song, log the
            # error and call error callback
            logger.error(
                "Unable to play '%s'", mrl_to_path(self.media_pending.get_mrl())
            )
            self.callbacks["finished"](self.playing_id)
            self.callbacks["error"](self.playing_id, "Unable to play current song")

            # reset current state
            self.playing_id = None
            self.media_pending = None

            self.vlc_states["in_media"].finish()
            self.states["in_song"].finish()

            return

    def handle_playing(self, event):
        """Callback called when playing has started

        This happens when:
            - The player resumes from pause;
            - A transition screen starts;
            - A song starts, leading to set the requested audio track to play.
            - An idle screen starts.

        Args:
            event (vlc.EventType): VLC event object.
        """
        logger.debug("Playing callback called")

        if self.states["in_song"].is_active():
            if (
                self.vlc_states["in_transition"].is_active()
                or self.vlc_states["in_media"].is_active()
            ) and self.vlc_states["in_pause"].is_active():
                # the media or the transition is resuming from pause
                self.callbacks["resumed"](self.playing_id, self.get_timing())

                logger.debug("Resumed play")
                self.vlc_states["in_pause"].finish()

                return

            media_path = mrl_to_path(self.media_pending.get_mrl())
            if self.vlc_states["in_transition"].has_finished():
                # the media starts to play
                self.callbacks["started_song"](self.playing_id)

                if self.audio_track_id is not None:
                    logger.debug(
                        "Requesting to play audio track %i", self.audio_track_id
                    )
                    self.player.audio_set_track(self.audio_track_id)

                logger.info("Now playing '%s'", media_path)
                self.vlc_states["in_media"].start()

                return

            # the transition screen starts to play
            self.callbacks["started_transition"](self.playing_id)
            logger.info("Playing transition for '%s'", media_path)
            self.vlc_states["in_transition"].start()

            return

        if self.states["in_idle"].is_active():
            # the idle screen starts to play
            logger.debug("Playing idle screen")
            self.vlc_states["in_idle"].start()

            return

        raise InvalidStateError("Playing on an undeterminated state")

    def handle_paused(self, event):
        """Callback called when pause is set

        Args:
            event (vlc.EventType): VLC event object.
        """
        logger.debug("Paused callback called")

        # call paused callback
        self.callbacks["paused"](self.playing_id, self.get_timing())

        logger.debug("Set pause")
        self.vlc_states["in_pause"].start()

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

        # reset states
        self.states["in_idle"].reset()
        self.states["in_song"].reset()
        self.vlc_states["in_transition"].reset()
        self.vlc_states["in_media"].reset()
        self.vlc_states["in_idle"].reset()

        # Check file exists
        if not file_path.exists():
            self.handle_file_not_found(file_path, playlist_entry["id"])
            return

        # create the media
        self.playing_id = playlist_entry["id"]
        self.media_pending = self.instance.media_new_path(file_path)
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

        self.states["in_song"].start()

        # play transition
        self.play_media(media_transition)
        logger.debug("Will play transition for '%s'", file_path)

        # manage instrumental
        self.manage_instrumental(playlist_entry, file_path)

    def manage_instrumental(self, playlist_entry, file_path):
        """Manage the requested instrumental track

        Args:
            playlist_entry (dict): Playlist entry data. Must contain the key
                `use_instrumental`.
            file_path (path.Path): Path of the song file.
        """
        self.audio_track_id = None

        # exit now if there is no instrumental track requested
        if not playlist_entry["use_instrumental"]:
            return

        # get instrumental file is possible
        audio_path = self.get_instrumental_audio_file(file_path)

        # if audio file is present, request to add the file to the media
        # as a slave and register to play this extra track (which will be
        # the last audio track of the media)
        if audio_path:
            number_tracks = self.get_number_tracks(self.media_pending)
            logger.info(
                "Requesting to play instrumental file '%s' for '%s'",
                audio_path,
                file_path,
            )
            try:
                # try to add the instrumental file
                self.media_pending.slaves_add(
                    vlc.MediaSlaveType.audio, 4, path_to_mrl(audio_path).encode()
                )

            except NameError:
                # otherwise fallback to default
                logger.error(
                    "This version of VLC does not support slaves, cannot add "
                    "instrumental file"
                )
                return

            self.audio_track_id = number_tracks
            return

        # get audio tracks
        audio_tracks_id = self.get_audio_tracks_id(self.media_pending)

        # if more than 1 audio track is present, register to play the 2nd one
        if len(audio_tracks_id) > 1:
            logger.info("Requesting to play instrumental track of '%s'", file_path)
            self.audio_track_id = audio_tracks_id[1]
            return

        # otherwise, fallback to register to play the first track and log it
        logger.warning(
            "Cannot find instrumental file or track for file '%s'", file_path
        )

    def play_idle_screen(self):
        # set idle state
        self.playing_id = None

        # reset states
        self.states["in_idle"].reset()
        self.states["in_song"].reset()
        self.vlc_states["in_transition"].reset()
        self.vlc_states["in_media"].reset()
        self.vlc_states["in_idle"].reset()

        # create idle screen media
        media = self.instance.media_new_path(self.background_loader.backgrounds["idle"])

        # create the idle screen
        with self.idle_text_path.open("w", encoding="utf8") as file:
            file.write(
                self.text_generator.create_idle_text(
                    {
                        "notes": [
                            "VLC {}".format(self.vlc_version),
                            "Dakara player {}".format(__version__),
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

        self.states["in_idle"].start()

        self.play_media(media)
        logger.debug("Will play idle screen")

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
        if (
            self.vlc_states["in_idle"].is_active()
            or self.vlc_states["in_transition"].is_active()
        ):
            return 0

        timing = self.player.get_time()

        # correct the way VLC handles when it hasn't started to play yet
        if timing == -1:
            timing = 0

        return timing // 1000

    def set_pause(self, pause):
        """Pause or unpause the player

        Pause playing song when True unpause when False.

        Args:
            pause (bool): flag for pause state requested.
        """
        if self.vlc_states["in_idle"].is_active():
            return

        if pause:
            if self.vlc_states["in_pause"].is_active():
                logger.debug("Player already in pause")
                return

            logger.info("Setting pause")
            self.player.pause()

            return

        if not self.vlc_states["in_pause"].is_active():
            logger.debug("Player already playing")
            return

        logger.info("Resuming play")
        self.player.play()

    def skip(self):
        """Skip the current song
        """
        if self.states["in_song"].is_active():
            self.callbacks["finished"](self.playing_id)
            media_path = mrl_to_path(self.media_pending.get_mrl())
            logger.info("Skipping '%s'", media_path)

            # if transition is playing
            if self.vlc_states["in_transition"].is_active():
                self.vlc_states["in_transition"].finish()
                self.states["in_song"].finish()

                return

            # if song is playing
            if self.vlc_states["in_media"].is_active():
                self.vlc_states["in_media"].finish()
                self.states["in_song"].finish()

                return

    def stop_player(self):
        logger.info("Stopping player")
        self.player.stop()
        logger.debug("Stopped player")

    def get_number_tracks(self, media):
        """Get number of all tracks of the media

        Args:
            media (vlc.Media): Media to investigate.

        Returns:
            int: Number of tracks in the media.
        """
        # parse media to extract tracks
        media.parse()

        return len(list(media.tracks_get()))

    def get_audio_tracks_id(self, media):
        """Get ID of audio tracks of the media

        Args:
            media (vlc.Media): Media to investigate.

        Returns:
            list of int: ID of audio tracks in the media.
        """
        # parse media to extract tracks
        media.parse()
        audio = [
            item.id for item in media.tracks_get() if item.type == vlc.TrackType.audio
        ]

        return audio


def mrl_to_path(file_mrl):
    """Convert a MRL to a filesystem path

    File path is stored as MRL inside a media object, we have to bring it back
    to a more classic looking path format.

    Args:
        file_mrl (str): Path to the resource within MRL format.

    Returns:
        path.Path: Path to the resource.
    """
    path_string = unquote(urlparse(file_mrl).path)

    # remove first '/' if a colon character is found like in '/C:/a/b'
    if path_string[0] == "/" and path_string[2] == ":":
        path_string = path_string[1:]

    return Path(path_string).normpath()


def path_to_mrl(file_path):
    """Convert a filesystem path to MRL

    Args:
        file_path (path.Path or str): Path to the resource.

    Returns:
        str: Path to the resource within MRL format.
    """
    return pathlib.Path(file_path).as_uri()


class InvalidStateError(RuntimeError):
    """Error raised when the state of the application cannot be understood
    """

    pass
