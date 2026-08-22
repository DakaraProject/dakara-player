"""VLC media player."""

import json
import logging
import platform
import re

from dakara_base.exceptions import DakaraError
from dakara_base.safe_workers import safe
from packaging.version import parse

from dakara_player.media_player.base import (
    InvalidStateError,
    MediaPlayer,
    MediaPlayerItemIdle,
    MediaPlayerItemSong,
    MediaPlayerItemTransition,
    VersionNotFoundError,
    on_playing_this,
)
from dakara_player.mrl import mrl_to_path
from dakara_player.vlc.check import is_vlc_available
from dakara_player.window import DummyWindowManager, WindowManager

if is_vlc_available():
    import vlc

else:
    from dakara_player.vlc import dummy_interface as vlc

    vlc.display_module_warning()


METADATA_KEYS_COUNT = len(vlc.Meta.__dict__["_enum_names_"])
METADATA_MARKER_KEY = "set_by"
METADATA_MARKER_VALUE = "dakara"

IDLE_DURATION = 3600


logger = logging.getLogger(__name__)


class MediaPlayerVlc(MediaPlayer):
    """Class to manipulate VLC.

    The class can be used as a context manager that closes VLC
    automatically on exit.

    Any exception in callbacks make the application to crash.

    Args:
        stop (threading.Event): Stop event that notify to stop the entire
            program when set.
        errors (queue.Queue): Error queue to communicate the exception to the
            main thread.
        config (dict): Dictionary of configuration.
        tempdir (pathlib.Path): Path of the temporary directory.

    Attributes:
        stop (threading.Event): Stop event that notify to stop the entire
            program when set.
        errors (queue.Queue): Error queue to communicate the exception to the
            main thread.
        player_name (str): Name of VLC.
        fullscreen (bool): If `True`, VLC will be fullscreen.
        kara_folder_path (pathlib.Path): Path to the karaoke folder.
        callbacks (dict): High level callbacks associated with the media
            player.
        warn_long_exit (bool): If `True`, display a warning message if the media
            player takes too long to stop.
        durations (dict of int): Duration of the different screens in seconds.
        text_paths (dict of pathlib.Path): Path of the different text screens.
        text_generator (dakara_player.text_generator.TextGenerator): Text
            generator instance.
        background_loader
        (dakara_player.background_loader.BackgroundLoader): Background
            loader instance.
        media_parameters (list of str): Extra parameters passed to the media.
        instance (vlc.Instance): Instance of VLC.
        player (vlc.MediaPlayer): VLC player.
        event_manager (vlc.EventManager): VLC event manager.
        vlc_callbacks (dict): Low level callbacks associated with VLC.
    """

    player_name = "VLC"

    @staticmethod
    def is_available():
        """Indicate if VLC is available.

        Returns:
            bool: `True` if VLC is useable.
        """
        return is_vlc_available()

    def init_player(self, config, tempdir):
        """Initialize the objects of VLC.

        Actions performed in this method should not have any side effects
        (query file system, etc.).

        Args:
            config (dict): Dictionary of configuration.
            tempdir (pathlib.Path): Path of the temporary directory.
        """
        # parameters
        config_vlc = config.get("vlc") or {}
        self.media_parameters = config_vlc.get("media_parameters") or []

        # window for VLC
        if config_vlc.get("use_default_window", False):
            window_manager_class = DummyWindowManager

        else:
            window_manager_class = WindowManager

        self.window = window_manager_class(
            title="Dakara Player VLC",
            fullscreen=self.fullscreen,
        )

        # VLC objects
        self.instance = get_instance(config_vlc.get("instance_parameters"))
        self.player = self.instance.media_player_new()
        self.event_manager = self.player.event_manager()

        # vlc callbacks
        self.vlc_callbacks = {}

    def load_player(self):
        """Perform actions with side effects for VLC initialization."""
        # check VLC version
        self.check_version()

        # assign window to VLC
        self.window.open()
        self.set_window(self.window.get_id())

        # set VLC callbacks
        self.set_vlc_default_callbacks()

        # print VLC version
        logger.info("VLC %s", self.get_version_str())

    @on_playing_this(["song"], default_return=0)
    def get_timing(self):
        """Get VLC timing.

        Returns:
            int: Current song timing in seconds if a song is playing, or 0 when
                idle or during transition screen.
        """
        timing = self.player.get_time()

        # correct the way VLC handles when it hasn't started to play yet
        if timing == -1:
            timing = 0

        return timing // 1000

    @staticmethod
    def get_version():
        """Get VLC version.

        VLC version given by the lib is on the form "x.y.z CodeName" in bytes.

        Returns:
            packaging.version.Version: Parsed version of VLC.

        Raises:
            VersionNotFoundError: If the version cannot be parsed.
        """
        match = re.search(
            r"(\d+\.\d+\.\d+(?:\.\d+)*)", vlc.libvlc_get_version().decode()
        )
        if match:
            return parse(match.group(1))

        raise VersionNotFoundError("Unable to get VLC version")

    def check_version(self):
        """Check that VLC is at least version 3.

        Raises:
            VlcTooOldError: If VLC version is lower than 3.
        """
        version = self.get_version()

        if version.major < 3:
            raise VlcTooOldError("VLC is too old (version 3 and higher supported)")

        if version.minor == 0 and 13 <= version.micro <= 16:
            logger.warning(
                "This version of VLC is known to not work with Dakara player"
            )

    def set_vlc_default_callbacks(self):
        """Set VLC default callbacks."""
        self.set_vlc_callback(
            vlc.EventType.MediaPlayerEndReached, self.handle_end_reached
        )
        self.set_vlc_callback(
            vlc.EventType.MediaPlayerEncounteredError, self.handle_encountered_error
        )
        self.set_vlc_callback(vlc.EventType.MediaPlayerPlaying, self.handle_playing)
        self.set_vlc_callback(vlc.EventType.MediaPlayerPaused, self.handle_paused)

    def set_vlc_callback(self, event, callback):
        """Assing an arbitrary callback to a VLC event.

        Callback is attached to the VLC event manager and added to the
        `vlc_callbacks` dictionary.

        Args:
            event (vlc.EventType): VLC event to attach the callback to, name of
                the callback in the `vlc_callbacks` attribute.
            callback (function): Function to assign.
        """
        self.vlc_callbacks[event] = callback
        self.event_manager.event_attach(event, callback)

    def is_playing(self):
        """Query if VLC is playing something.

        Returns:
            bool: `True` if VLC is playing something.
        """
        return self.player.get_state() == vlc.State.Playing

    def is_paused(self):
        """Query if VLC is paused.

        Returns:
            bool: True if VLC is paused.
        """
        return self.player.get_state() == vlc.State.Paused

    def is_playing_this(self, what):
        """Query if VLC is playing the requested media type.

        Args:
            what (str): Tell if VLC current track is of the requested type, but
                not if it is actually playing it (it can be in pause).

        Returns:
            bool: `True` if VLC is playing the requested type.
        """
        media = self.player.get_media()

        # if no media is in the player
        if not media:
            return False

        # if no playlist entry is supposed to play
        if what in ("transition", "song") and (
            self.entry is None or not self.entry.is_loaded()
        ):
            return False

        return get_metadata(media)["type"] == what

    def play(self, what):
        """Request VLC to play something.

        Args:
            what (str): What media to play.

        Raises:
            ValueError: If the action to play is unknown.
        """
        if what == "idle":
            media = get_idle_media(self.idle_item, self.media_parameters)

        elif what == "transition":
            media = get_transition_media(
                self.entry.items["transition"], self.media_parameters
            )

        elif what == "song":
            media = get_song_media(self.entry.items["song"], self.media_parameters)

        else:
            raise ValueError("Unexpected action to play: {}".format(what))

        self.player.set_media(media)
        self.player.play()

    @on_playing_this(["transition", "song"])
    def pause(self):
        """Request VLC to pause.

        Can only work on transition screens or songs. Pausing should have no
        effect if VLC is already paused.
        """
        if self.is_paused():
            logger.debug("Player already in pause")
            return

        logger.info("Setting pause")
        self.player.pause()

    @on_playing_this(["transition", "song"])
    def resume(self):
        """Request VLC to resume playing.

        Can only work on transition screens or songs. Resuming should have no
        effect if VLC is already playing.
        """
        if not self.is_paused():
            logger.debug("Player already playing")
            return

        logger.info("Resuming play")
        self.player.play()

    @on_playing_this(["song"])
    def restart(self):
        """Request to restart the current media.

        Can only work on songs.
        """
        logger.info("Restarting media")
        self.player.set_time(0)
        self.callbacks["updated_timing"](self.entry.id, self.get_timing())

    @on_playing_this(["transition", "song"])
    def skip(self, no_callback=False):
        """Request to skip the current media.

        Can only work on transition screens or songs. VLC should continue
        playing, but media has to be considered already finished.

        Args:
            no_callback (bool): If `True`, no callback to signal the song has
                finished will be executed.
        """
        logger.info("Skipping '%s'", self.entry.title)
        if not no_callback:
            self.callbacks["finished"](self.entry.id)

        self.clear_playlist_entry()

    @on_playing_this(["song"])
    def rewind(self):
        """Request to rewind a few seconds the media.

        Can only work on songs. It cannot rewind before the beginning of the
        media. In that case, restart the song.
        """
        timing = int(
            self.player.get_time() - self.durations["rewind_fast_forward"] * 1000
        )

        if timing < 0:
            self.restart()
            return

        logger.info("Rewinding media")
        self.player.set_time(timing)
        self.callbacks["updated_timing"](self.entry.id, self.get_timing())

    @on_playing_this(["song"])
    def fast_forward(self):
        """Request to fast forward a few seconds the media.

        Can only work on songs. It cannot advance passed the end of the media.
        In that case, skip the song.
        """
        timing = int(
            self.player.get_time() + self.durations["rewind_fast_forward"] * 1000
        )

        if timing > self.player.get_media().get_duration():
            self.skip()
            return

        logger.info("Fast forwarding media")
        self.player.set_time(timing)
        self.callbacks["updated_timing"](self.entry.id, self.get_timing())

    def stop_player(self):
        """Request to stop VLC."""
        # stopping VLC
        logger.info("Stopping player")
        self.player.stop()
        logger.debug("Stopped player")

        # closing window
        self.window.close()

    @safe
    def handle_end_reached(self, event):
        """Callback called when a media ends.

        This happens when:
            - A transition screen ends, leading to playing the actual song;
            - A song ends normally, leading to calling the callback
                `callbacks["finished"]`;
            - An idle screen ends, leading to reloop it.

        A new thread is created in any case.

        Args:
            event (vlc.EventType): VLC event object.

        Raises:
            InvalidStateError: If the context of call of this callback is
                unexpected.
        """
        logger.debug("End reached callback called")

        # the transition screen has finished, request to play the song itself
        if self.is_playing_this("transition"):
            logger.debug("Finished playing transition for '%s'", self.entry.title)
            thread = self.create_thread(target=self.play, args=("song",))
            thread.start()

            return

        # the song has finished, so clean memory and call the according callback
        if self.is_playing_this("song"):
            playlist_entry_id = self.entry.id
            self.clear_playlist_entry()
            self.callbacks["finished"](playlist_entry_id)

            return

        # the idle screen has finished, simply restart it
        if self.is_playing_this("idle"):
            thread = self.create_thread(target=self.play, args=("idle",))
            thread.start()

            return

        # if no state can be determined, raise an error
        raise InvalidStateError("End reached on an undeterminated state")

    @safe
    def handle_encountered_error(self, event):
        """Callback called when error occurs

        There is no way to capture error message, so only a generic error
        message is provided. Call the callbacks `callbacks["finished"]` and
        `callbacks["error"]`

        Args:
            event (vlc.EventType): VLC event object.
        """
        logger.debug("Error callback called")

        # the current song media has an error, skip the song, log the error and
        # call error callback
        if self.is_playing_this("song"):
            logger.error(
                "Unable to play '%s'", mrl_to_path(self.player.get_media().get_mrl())
            )
            self.callbacks["error"](self.entry.id, "Unable to play current song")
            self.skip()

            return

        # do not assess other errors

    @safe
    def handle_playing(self, event):
        """Callback called when playing has started.

        This happens when:
            - The player resumes from pause;
            - A transition screen starts;
            - A song starts, leading to set the requested audio track to play;
            - An idle screen starts.

        Args:
            event (vlc.EventType): VLC event object.

        Raises:
            InvalidStateError: If the context of call of this callback is
                unexpected.
        """
        logger.debug("Playing callback called")
        media = self.player.get_media()

        # the media or the transition is resuming from pause
        # it is pretty hard to detect this case, as we do not have a previous
        # state in memory
        # we rely on a specific flag stored in the media metadata which is set
        # to True when the corresponding media starts
        if (
            self.is_playing_this("transition") or self.is_playing_this("song")
        ) and get_metadata(media)["started"]:
            self.callbacks["resumed"](self.entry.id, self.get_timing())
            logger.debug("Resumed play")

            return

        # the transition screen starts to play
        if self.is_playing_this("transition"):
            self.callbacks["started_transition"](self.entry.id)
            update_metadata(media, {"started": True})
            logger.info("Playing transition for '%s'", self.entry.title)

            return

        # the song starts to play
        if self.is_playing_this("song"):
            self.callbacks["started_song"](self.entry.id)

            # set instrumental track if necessary
            if track_id_audio := get_metadata(media).get("track_id_audio"):
                logger.debug("Requesting to play audio track #%i", track_id_audio)
                self.player.audio_set_track(track_id_audio)

            update_metadata(media, {"started": True})
            logger.info(
                "Now playing '%s' ('%s')",
                self.entry.title,
                mrl_to_path(self.player.get_media().get_mrl()),
            )

            return

        # the idle screen starts to play
        if self.is_playing_this("idle"):
            logger.debug("Playing idle screen")

            return

        raise InvalidStateError("Playing on an undeterminated state")

    @safe
    def handle_paused(self, event):
        """Callback called when pause is set.

        Args:
            event (vlc.EventType): VLC event object.
        """
        logger.debug("Paused callback called")

        # call paused callback
        self.callbacks["paused"](self.entry.id, self.get_timing())

        logger.debug("Paused")

    def set_window(self, id):
        """Associate an existing window to VLC

        Args:
            id (int): ID of the window.

        Raises:
            NotImplementedError: If the current platform is not supported.
        """
        if id is None:
            logger.debug("Using VLC default window")
            return

        system = platform.system()

        if system == "Linux":
            logger.debug("Associating X window to VLC")
            self.player.set_xwindow(id)
            return

        if system == "Windows":
            logger.debug("Associating Win API window to VLC")
            self.player.set_hwnd(id)
            return

        raise NotImplementedError(
            "This operating system ({}) is not currently supported".format(system)
        )


def set_metadata(media: vlc.Media, metadata: dict) -> int:
    """Set metadata to media.

    Take the first free metadata slot to store value, or the first metadata
    slot to contain the metadata marker.

    The metadata is stored in the media and can be recovered from anywhere.

    Args:
        media (vlc.Media): Media to set metadata in.
        metadata (any): JSON representable data.

    Returns:
        int: Key where metadata are written.

    Raises:
        ValueError: If the media has no free metadata to use.
    """
    for key in range(METADATA_KEYS_COUNT):
        value = media.get_meta(key)
        if (
            value is None
            or f'"{METADATA_MARKER_KEY}": "{METADATA_MARKER_VALUE}"' in value
        ):
            media.set_meta(
                key,
                json.dumps({**metadata, METADATA_MARKER_KEY: METADATA_MARKER_VALUE}),
            )
            return key

    raise ValueError("This media has no spare metadata to use")


def get_metadata(media: vlc.Media) -> dict:
    """Get metadata from media.

    Take the first non free metadata slot that contains a valid JSON value with
    the metadata marker

    Args:
        media (vlc.Media): Media to get metadata from.

    Returns:
        any: JSON representable data.

    Raises:
        ValueError: If the media has no valid metadata.
    """
    for key in range(METADATA_KEYS_COUNT):
        try:
            value = json.loads(media.get_meta(key))
            value.pop(METADATA_MARKER_KEY)
            return value

        except (json.JSONDecodeError, TypeError, KeyError):
            continue

    raise ValueError("This media has no set metadata")


def update_metadata(media: vlc.Media, metadata: dict) -> int:
    """Update existing metadata in media.

    Will find the first metadata slot already written by a previous
    `set_metadata`, and will update the metadata with the provided ones.

    Args:
        media (vlc.Media): Media to update metadata in.
        metadata (any): JSON representable data.

    Returns:
        int: Key where metadata are written.
    """
    return set_metadata(media, {**get_metadata(media), **metadata})


def get_instance(instance_parameters=None):
    """Get a VLC instance with parameters.

    Args:
        instance_parameters (list of str): List of parameters. Must be in the
            form "--option=value".

    Returns:
        vlc.Instance: New instance.

    Raises:
        UnavailableInstanceError: If an instance cannot be obtained without
            parameters.
        UnexpectedInstanceParameterError: If unexpected parameters are
            passed.
    """
    # if no parameters are passed, the instance should never be None
    if not instance_parameters:
        instance = vlc.Instance()
        if instance is None:
            raise UnavailableInstanceError("Unable to get a VLC instance")

        return instance

    # if parameters are passed, an unexpected parameter makes the instance None
    instance = vlc.Instance(instance_parameters)
    if instance is None:
        raise UnexpectedInstanceParameterError("Unexpected VLC instance parameter")

    return instance


def get_transition_media(
    transition: MediaPlayerItemTransition, media_parameters: list[str]
) -> vlc.Media:
    """Create a transition media for VLC.

    Args:
        transition (MediaPlayerItemTransition): Transition item that contains
            all data.
        media_parameters (list of str): Media parameters to pass to VLC. Must
            be in the form `option=value` (without the leading `--`).

    Returns:
        vlc.Media: VLC media for the transition.
    """
    media = vlc.Media(
        transition.path.as_uri(),
        *media_parameters,
        f"image-duration={transition.duration}",
        f"sub-file={transition.subtitle_path}",
        "no-sub-autodetect-file",
    )
    set_metadata(media, {"type": "transition", "started": False})

    return media


def get_song_media(song: MediaPlayerItemSong, media_parameters: list[str]) -> vlc.Media:
    """Create a song media for VLC.

    Args:
        song (MediaPlayerItemSong): Song item that contains all data.
        media_parameters (list of str): Media parameters to pass to VLC. Must
            be in the form `option=value` (without the leading `--`).

    Returns:
        vlc.Media: VLC media for the song.
    """
    media = vlc.Media(
        song.path.as_uri(),
        *media_parameters,
    )
    metadata = {"type": "song", "started": False, "track_id_audio": None}

    # manage instrumental
    if song.instrumental_path is not None:
        metadata["track_id_audio"] = set_instrumental_file(song, media)

    elif song.instrumental_track is not None:
        metadata["track_id_audio"] = set_instrumental_track(song, media)

    set_metadata(media, metadata)
    return media


def set_instrumental_file(song: MediaPlayerItemSong, media: vlc.Media) -> int | None:
    """Add the instrumental file as a slave to the media.

    Note some older versions of VLC (cannot find the version, the documentation
    states it has been valid since VLC 3.0.0) do not support to add slaves.

    Args:
        song (MediaPlayerItemSong): Song item that contains all data.
        vlc.Media: VLC media for the song.

    Returns:
        int: Number of the instrumental track (note that the track number is
        not limited to audio tracks).
    """
    assert song.instrumental_path is not None

    # get number of tracks of the media
    media.parse()
    number_tracks = len(list(media.tracks_get()))

    try:
        # try to add the instrumental file
        media.slaves_add(
            vlc.MediaSlaveType.audio,
            4,  # highest priority
            song.instrumental_path.as_uri(),
        )

    except NameError:
        # otherwise fallback to default
        logger.error(
            "This version of VLC does not support slaves, cannot add "
            "instrumental file"
        )
        return None

    return number_tracks


def set_instrumental_track(song: MediaPlayerItemSong, media: vlc.Media) -> int | None:
    """Get the insrumental track number.

    Note that despite the name of the function, nothing is actually set.

    Args:
        song (MediaPlayerItemSong): Song item that contains all data.
        vlc.Media: VLC media for the song.

    Returns:
        int: Number of the instrumental track (note that the track number is
        not limited to audio tracks).
    """
    assert song.instrumental_track is not None

    # get audio track IDs
    media.parse()
    track_id_audio_list = [
        item.id for item in media.tracks_get() if item.type == vlc.TrackType.audio
    ]

    audio_id = song.instrumental_track

    if len(track_id_audio_list) <= audio_id:
        logger.error("Unable to find requested instrumental track %i", audio_id)
        return None

    track_id = track_id_audio_list[audio_id]
    logger.debug("Instrumental track is #%i for VLC", track_id)

    return track_id


def get_idle_media(idle: MediaPlayerItemIdle, media_parameters: list[str]) -> vlc.Media:
    """Create an idle screen media for VLC.

    Args:
        idle (MediaPlayerItemIdle): Idle item that contains all data.
        media_parameters (list of str): Media parameters to pass to VLC. Must
            be in the form `option=value` (without the leading `--`).

    Returns:
        vlc.Media: VLC media for the idle screen.
    """
    media = vlc.Media(
        idle.path.as_uri(),
        *media_parameters,
        f"image-duration={IDLE_DURATION}",
        f"sub-file={idle.subtitle_path}",
        "no-sub-autodetect-file",
    )
    set_metadata(media, {"type": "idle"})

    return media


class VlcTooOldError(DakaraError):
    """Error raised if VLC is too old."""


class UnexpectedInstanceParameterError(DakaraError):
    """Error raised when passing incorrect parameters to  the VLC instance."""


class UnavailableInstanceError(DakaraError):
    """Error raised when a VLC instance cannot be obtained."""
