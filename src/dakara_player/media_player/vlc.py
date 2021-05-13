import logging
import json
import re
import sys

from dakara_base.exceptions import DakaraError
from dakara_base.safe_workers import safe
from dakara_player.window import WindowManager, DummyWindowManager
from packaging.version import parse

try:
    import vlc
    from vlc import libvlc_get_version

except (ImportError, OSError):
    vlc = None
    libvlc_get_version = None

from dakara_player.media_player.base import (
    MediaPlayer,
    InvalidStateError,
    VersionNotFoundError,
)
from dakara_player.mrl import path_to_mrl, mrl_to_path


try:
    METADATA_KEY = vlc.Meta.Setting

except AttributeError:
    METADATA_KEY = None

logger = logging.getLogger(__name__)


class MediaPlayerVlc(MediaPlayer):
    """Abstract class to manipulate VLC.

    The class can be used as a context manager that closes VLC
    automatically on exit.

    Any exception in callbacks make the application to crash.

    Args:
        stop (threading.Event): Stop event that notify to stop the entire
            program when set.
        errors (queue.Queue): Error queue to communicate the exception to the
            main thread.
        config (dict): Dictionary of configuration.
        tempdir (path.Path): Path of the temporary directory.

    Attributes:
        stop (threading.Event): Stop event that notify to stop the entire
            program when set.
        errors (queue.Queue): Error queue to communicate the exception to the
            main thread.
        player_name (str): Name of VLC.
        fullscreen (bool): If True, VLC will be fullscreen.
        kara_folder_path (path.Path): Path to the karaoke folder.
        playlist_entry (dict): Playlist entyr object.
        callbacks (dict): High level callbacks associated with the media
            player.
        warn_long_exit (bool): If True, display a warning message if the media
            player takes too long to stop.
        durations (dict of int): Duration of the different screens in seconds.
        text_paths (dict of path.Path): Path of the different text screens.
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
        playlist_entry_data (dict): Extra data of the playlist entry.
    """

    player_name = "VLC"

    @staticmethod
    def is_available():
        """Indicate if VLC is available.

        Returns:
            bool: True if VLC is useable.
        """
        return vlc is not None and vlc.Instance() is not None

    def init_player(self, config, tempdir):
        """Initialize the objects of VLC.

        Actions performed in this method should not have any side effects
        (query file system, etc.).

        Args:
            config (dict): Dictionary of configuration.
            tempdir (path.Path): Path of the temporary directory.
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
            title="Dakara Player VLC", fullscreen=self.fullscreen,
        )

        # VLC objects
        self.instance = vlc.Instance(config_vlc.get("instance_parameters") or [])
        self.player = self.instance.media_player_new()
        self.event_manager = self.player.event_manager()

        # vlc callbacks
        self.vlc_callbacks = {}

        # playlist entry objects
        self.playlist_entry_data = {}
        self.clear_playlist_entry_player()

    def load_player(self):
        """Perform actions with side effects for VLC initialization.
        """
        # check VLC version
        self.check_version()

        # assign window to VLC
        self.window.open()
        self.set_window(self.window.get_id())

        # set VLC callbacks
        self.set_vlc_default_callbacks()

        # print VLC version
        logger.info("VLC %s", self.get_version())

    def get_timing(self):
        """Get VLC timing.

        Returns:
            int: Current song timing in seconds if a song is playing, or 0 when
                idle or during transition screen.
        """
        if self.is_playing_this("idle") or self.is_playing_this("transition"):
            return 0

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
        """
        match = re.search(r"(\d+\.\d+\.\d+(?:\.\d+)*)", libvlc_get_version().decode())
        if match:
            return parse(match.group(1))

        raise VersionNotFoundError("Unable to get VLC version")

    def check_version(self):
        """Check that VLC is at least version 3.
        """
        version = self.get_version()

        if version.major < 3:
            raise VlcTooOldError("VLC is too old (version 3 and higher supported)")

    def set_vlc_default_callbacks(self):
        """Set VLC default callbacks.
        """
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
            bool: True if VLC is playing something.
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
            bool: True if VLC is playing the requested type.
        """
        return get_metadata(self.player.get_media())["type"] == what

    def play(self, what):
        """Request VLC to play something.

        No preparation should be done by this function, i.e. the media track
        should have been prepared already by `set_playlist_entry_player`.

        Args:
            what (str): What media to play.
        """
        if what == "idle":
            # create idle screen media
            media = self.instance.media_new_path(
                self.background_loader.backgrounds["idle"]
            )

            media.add_options(
                *self.media_parameters,
                "image-duration={}".format(self.durations["idle"]),
                "sub-file={}".format(self.text_paths["idle"]),
                "no-sub-autodetect-file",
            )

            set_metadata(media, {"type": "idle"})

            self.generate_text("idle")

        elif what == "transition":
            media = self.playlist_entry_data["transition"].media

        elif what == "song":
            media = self.playlist_entry_data["song"].media

        else:
            raise ValueError("Unexpected action to play: {}".format(what))

        self.player.set_media(media)
        self.player.play()

    def pause(self, paused):
        """Request VLC to pause or unpause.

        Can only work on transition screens or songs. Pausing should have no
        effect if VLC is already paused, unpausing should have no
        effect if VLC is already unpaused.

        Must be overriden.

        Args:
            paused (bool): If True, pause VLC.
        """
        if self.is_playing_this("idle"):
            return

        if paused:
            if self.is_paused():
                logger.debug("Player already in pause")
                return

            logger.info("Setting pause")
            self.player.pause()
            return

        if not self.is_paused():
            logger.debug("Player already playing")
            return

        logger.info("Resuming play")
        self.player.play()

    def skip(self):
        """Request to skip the current media.

        Can only work on transition screens or songs. VLC should continue
        playing, but media has to be considered already finished.
        """
        if self.is_playing_this("transition") or self.is_playing_this("song"):
            self.callbacks["finished"](self.playlist_entry["id"])
            logger.info("Skipping '%s'", self.playlist_entry["song"]["title"])
            self.clear_playlist_entry()

    def stop_player(self):
        """Request to stop VLC.
        """
        # stopping VLC
        logger.info("Stopping player")
        self.player.stop()
        logger.debug("Stopped player")

        # closing window
        self.window.close()

    def set_playlist_entry_player(self, playlist_entry, file_path, autoplay):
        """Prepare playlist entry data to be played.

        Prepare all media objects, subtitles, etc. for being played, for the
        transition screen and the song. Such data should be stored on a
        dedicated object, like `playlist_entry_data`.

        Args:
            playlist_entry (dict): Playlist entry object.
            file_path (path.Path): Absolute path to the song file.
            autoplay (bool): If True, start to play transition screen as soon
                as possible (i.e. as soon as the transition screen media is
                ready). The song media is prepared when the transition screen
                is playing.
        """
        # create transition screen media
        media_transition = self.instance.media_new_path(
            self.background_loader.backgrounds["transition"]
        )

        media_transition.add_options(
            *self.media_parameters,
            "image-duration={}".format(self.durations["transition"]),
            "sub-file={}".format(self.text_paths["transition"]),
            "no-sub-autodetect-file",
        )

        set_metadata(
            media_transition,
            {"type": "transition", "playlist_entry": self.playlist_entry},
        )

        self.generate_text("transition", fade_in=True)

        self.playlist_entry_data["transition"].media = media_transition

        # start playing transition right away if requested
        if autoplay:
            self.play("transition")

        # create song media
        media_song = self.instance.media_new_path(file_path)
        media_song.add_options(*self.media_parameters)
        set_metadata(
            media_song, {"type": "song", "playlist_entry": self.playlist_entry}
        )

        self.playlist_entry_data["song"].media = media_song

        # manage instrumental
        if playlist_entry["use_instrumental"]:
            self.manage_instrumental(playlist_entry, file_path)

    def manage_instrumental(self, playlist_entry, file_path):
        """Manage the requested instrumental track.

        Instrumental track is searched first in audio files having the same
        name as the video file, then in extra audio tracks of the video file.

        Args:
            playlist_entry (dict): Playlist entry data. Must contain the key
                `use_instrumental`.
            file_path (path.Path): Path of the song file.
        """
        # get instrumental file if possible
        audio_path = self.get_instrumental_file(file_path)

        # if audio file is present, request to add the file to the media
        # as a slave and register to play this extra track (which will be
        # the last audio track of the media)
        if audio_path:
            number_tracks = self.get_number_tracks(
                self.playlist_entry_data["song"].media
            )
            logger.info(
                "Requesting to play instrumental file '%s' for '%s'",
                audio_path,
                file_path,
            )
            try:
                # try to add the instrumental file
                self.playlist_entry_data["song"].media.slaves_add(
                    vlc.MediaSlaveType.audio, 4, path_to_mrl(audio_path).encode()
                )

            except NameError:
                # otherwise fallback to default
                logger.error(
                    "This version of VLC does not support slaves, cannot add "
                    "instrumental file"
                )
                return

            self.playlist_entry_data["song"].audio_track_id = number_tracks
            return

        # get audio tracks
        audio_tracks_id = self.get_audio_tracks_id(
            self.playlist_entry_data["song"].media
        )

        # if more than 1 audio track is present, register to play the 2nd one
        if len(audio_tracks_id) > 1:
            logger.info("Requesting to play instrumental track of '%s'", file_path)
            self.playlist_entry_data["song"].audio_track_id = audio_tracks_id[1]
            return

        # otherwise, fallback to register to play the first track and log it
        logger.warning(
            "Cannot find instrumental file or track for file '%s'", file_path
        )

    def clear_playlist_entry_player(self):
        """Clean playlist entry data after being played.
        """
        self.playlist_entry_data = {
            "transition": Media(),
            "song": MediaSong(),
        }

    @staticmethod
    def get_number_tracks(media):
        """Get number of all tracks of the media.

        Args:
            media (vlc.Media): Media to investigate.

        Returns:
            int: Number of tracks in the media.
        """
        # parse media to extract tracks
        media.parse()

        return len(list(media.tracks_get()))

    @staticmethod
    def get_audio_tracks_id(media):
        """Get ID of audio tracks of the media.

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
        """
        logger.debug("End reached callback called")

        # the transition screen has finished, request to play the song itself
        if self.is_playing_this("transition"):
            logger.debug(
                "Will play '{}'".format(
                    mrl_to_path(self.playlist_entry_data["song"].media.get_mrl())
                )
            )
            thread = self.create_thread(target=self.play, args=("song",))
            thread.start()

            return

        # the media has finished, so call the according callback and clean memory
        if self.is_playing_this("song"):
            self.callbacks["finished"](self.playlist_entry["id"])
            self.clear_playlist_entry()

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
            self.callbacks["error"](
                self.playlist_entry["id"], "Unable to play current song"
            )
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
        """
        logger.debug("Playing callback called")

        # the media or the transition is resuming from pause
        # it is pretty hard to detect this case, as we do not have a previous
        # state in memory
        # we rely on a specific flag stored in `playlist_entry_data` Media
        # objects which is set to True when the corresponding media starts
        if (
            self.is_playing_this("transition")
            and self.playlist_entry_data["transition"].started
            or self.is_playing_this("song")
            and self.playlist_entry_data["song"].started
        ):
            self.callbacks["resumed"](self.playlist_entry["id"], self.get_timing())
            logger.debug("Resumed play")

            return

        # the transition screen starts to play
        if self.is_playing_this("transition"):
            self.callbacks["started_transition"](self.playlist_entry["id"])
            self.playlist_entry_data["transition"].started = True
            logger.info(
                "Playing transition for '%s'", self.playlist_entry["song"]["title"]
            )

            return

        # the song starts to play
        if self.is_playing_this("song"):
            self.callbacks["started_song"](self.playlist_entry["id"])

            # set instrumental track if necessary
            audio_track_id = self.playlist_entry_data["song"].audio_track_id
            if audio_track_id is not None:
                logger.debug("Requesting to play audio track %i", audio_track_id)
                self.player.audio_set_track(audio_track_id)

            self.playlist_entry_data["song"].started = True
            logger.info(
                "Now playing '%s' ('%s')",
                self.playlist_entry["song"]["title"],
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
        self.callbacks["paused"](self.playlist_entry["id"], self.get_timing())

        logger.debug("Paused")

    def set_window(self, id):
        """Associate an existing window to VLC

        Args:
            id (int): ID of the window.
        """
        if id is None:
            logger.debug("Using VLC default window")
            return

        if "linux" in sys.platform:
            logger.debug("Associating X window to VLC")
            self.player.set_xwindow(id)
            return

        if "win" in sys.platform:
            logger.debug("Associating Win API window to VLC")
            self.player.set_hwnd(id)
            return

        raise NotImplementedError(
            "This operating system ({}) is not currently supported".format(sys.platform)
        )


def set_metadata(media, metadata):
    """Set metadata to media.

    Use the `METADATA_KEY` for storage. The metadata can be extracted after.

    Args:
        media (vlc.Media): Media to set metadata in.
        metadata (any): JSON representable data.
    """
    media.set_meta(METADATA_KEY, json.dumps(metadata))


def get_metadata(media):
    """Get metadata from media.

    Use the `METADATA_KEY` for storage.

    Args:
        media (vlc.Media): Media to get metadata from.

    Returns:
        any: JSON representable data.
    """
    return json.loads(media.get_meta(METADATA_KEY))


class Media:
    """Media object.
    """

    def __init__(self, media=None):
        self.media = media
        self.started = False


class MediaSong(Media):
    """Song object.
    """

    def __init__(self, *args, audio_track_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.audio_track_id = audio_track_id


class VlcTooOldError(DakaraError):
    """Error raised if VLC is too old.
    """
