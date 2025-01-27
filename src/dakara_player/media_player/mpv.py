"""mpv media player."""

import logging
import re
from abc import ABC
from pathlib import Path

from dakara_base.exceptions import DakaraError
from dakara_base.safe_workers import safe
from packaging.version import Version, parse

try:
    import python_mpv_jsonipc as mpv

except ImportError:
    mpv = None

from dakara_player.media_player.base import (
    InvalidStateError,
    MediaPlayer,
    VersionNotFoundError,
    on_playing_this,
)

logger = logging.getLogger(__name__)
mpv_logger = logging.getLogger("mpv")

SUBTITLE_EXTENSIONS = [
    ".ass",
    ".ssa",
]

MPV_ERROR_LEVELS = {
    "fatal": logging.CRITICAL,
    "error": logging.ERROR,
    "warn": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}

PLAYER_IS_AVAILABLE_ATTEMPTS = 5


# monkey patch mpv to silent socket close failures on windows
if mpv is not None:

    class WindowsSocketSilenced(mpv.WindowsSocket):
        def stop(self, *args, **kwargs):
            try:
                super().stop(*args, **kwargs)

            except OSError:
                pass

    mpv.WindowsSocket = WindowsSocketSilenced


class MediaPlayerMpv(MediaPlayer, ABC):
    """Abstract class to manipulate mpv.

    This class contains the minimum static methods to detect mpv availability
    and installed version. It can be used to instanciate the correct version
    with the static method `from_version`.
    """

    player_name = "mpv"

    @staticmethod
    def is_available():
        """Indicate if mpv is available.

        Try the detection `PLAYER_IS_AVAILABLE_ATTEMPTS` times.

        Returns:
            bool: `True` if mpv is useable.
        """
        if mpv is None:
            return False

        for _ in range(PLAYER_IS_AVAILABLE_ATTEMPTS):
            try:
                player = mpv.MPV()
                player.terminate()
                return True

            except FileNotFoundError:
                pass

        return False

    @staticmethod
    def get_version():
        """Get media player version.

        mpv versions are in the form "vMAJOR.MINOR.PATCH" for releases, older
        versions (<0.37) do not include a 'v' before the version, post releases
        are detected as any valid base version followed by "+BUILD" or "-BUILD"
        where BUILD is whatever build information was included in the string.

        Returns:
            packaging.version.Version: Parsed version of mpv.

        Raises:
            VersionNotFoundError: If unable to parse version.
        """
        player = mpv.MPV()
        match = re.search(
            r"mpv v?(\d+\.\d+\.\d+)([+-]\w+)?",
            player.mpv_version,
        )
        player.terminate()

        if match:
            if match.group(2):
                return parse(match.group(1) + "-post")

            return parse(match.group(1))

        raise VersionNotFoundError("Unable to get mpv version")

    @staticmethod
    def get_class_from_version(version):
        """Get the mpv media player class according to installed version.

        Args:
            version (packaging.version.Version): Arbitrary mpv version to use.

        Returns:
            MediaPlayerMpv: Will return the class adapted to the version of mpv:

                - `MediaPlayerMpvPost0340` if mpv newer than 0.34.0;
                - `MediaPlayerMpvPost0330` if mpv newer than 0.33.0;
                - `MediaPlayerMpvOld` as default.

        Raises:
            MpvTooOldError: if MPV version is lower than 0.28.0
        """
        if version >= Version("0.34.0"):
            logger.debug("Using post 0.34.0 API of mpv")
            return MediaPlayerMpvPost0340

        if version >= Version("0.33.0"):
            logger.debug("Using post 0.33.0 API of mpv")
            return MediaPlayerMpvPost0330

        if version < Version("0.28.0"):
            raise MpvTooOldError(
                f"MPV is too old ({version=}, version 0.28.0 and higher supported)"
            )

        logger.debug("Using old API of mpv")
        return MediaPlayerMpvOld

    @staticmethod
    def from_version(*args, **kwargs):
        """Instanciate the right mpv media player class.

        Returns:
            MediaPlayer: Instance of the mpv media player for the correct
            version of mpv.
        """
        try:
            config = kwargs.get("config") or args[2]
            version = Version(config["mpv"]["force_version"])

        except (KeyError, IndexError):
            version = MediaPlayerMpv.get_version()

        return MediaPlayerMpv.get_class_from_version(version)(*args, **kwargs)


class MediaPlayerMpvOld(MediaPlayerMpv):
    """Class to manipulate old mpv versions (< 0.33.0).

    The class can be used as a context manager that closes mpv
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
        player_name (str): Name of mpv.
        fullscreen (bool): If `True`, mpv will be fullscreen.
        kara_folder_path (pathlib.Path): Path to the karaoke folder.
        playlist_entry (dict): Playlist entyr object.
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
        player (mpv.MPV): Instance of mpv.
        playlist_entry_data (dict): Extra data of the playlist entry.
        player_data (dict): Extra data of the player.
    """

    def init_player(self, config, tempdir):
        """Initialize the objects of mpv.

        Actions performed in this method should not have any side effects
        (query file system, etc.).

        Args:
            config (dict): Dictionary of configuration.
            tempdir (pathlib.Path): Path of the temporary directory.
        """
        # set mpv player options and logging
        loglevel = config.get("loglevel", "info")
        self.player = mpv.MPV(log_handler=self.handle_log_messages, loglevel=loglevel)
        config_mpv = config.get("mpv") or {}

        for key, value in config_mpv.items():
            try:
                self.player.__setattr__(key, value)

            except mpv.MPVError:
                logger.error(f"Unable to set mpv option '{key}' to value '{value}'")

        # playlist entry objects
        self.playlist_entry_data = {}
        self.clear_playlist_entry_player()

        # player objects
        self.player_data = {}
        self.player_data["skip"] = False

    def load_player(self):
        """Perform actions with side effects for mpv initialization."""
        # set mpv callbacks
        self.set_mpv_default_callbacks()

        # set mpv fullscreen
        self.player.fullscreen = self.fullscreen

        # log mpv version
        logger.info("mpv %s", self.get_version_str())

        # set mpv as a single non-interactive window
        self.player.force_window = "immediate"
        self.player.input_default_bindings = False
        self.player.osc = False
        self.player.osd_level = 0

        # set window title
        self.player.title = "Dakara player mpv"

        # handle image transitions as videos
        self.player.demuxer_lavf_o = "loop=1"
        # used for idle/transitions screens
        self.player.image_display_duration = "inf"

    @on_playing_this(["song"], default_return=0)
    def get_timing(self):
        """Get mpv timing.

        Returns:
            int: Current song timing in seconds if a song is playing, or 0 when
                idle or during transition screen.
        """
        timing = self.player.time_pos or 0

        return int(timing)

    def set_mpv_default_callbacks(self):
        """Set mpv default callbacks."""
        self.player.bind_event("end-file", self.handle_end_file)
        self.player.bind_event("start-file", self.handle_start_file)
        self.player.bind_event("pause", self.handle_pause)
        self.player.bind_event("unpause", self.handle_unpause)

    def is_playing(self):
        """Query if mpv is playing something.

        Returns:
            bool: `True` if mpv is playing something.

        Raises:
            AssertError: If too many intries are present in the mpv internal
                playlist.
        """
        # query if the player is currently playing
        if self.is_paused():
            return False

        playlist = self.player.playlist

        if len(playlist) == 0:
            return False

        assert len(playlist) == 1, "Too many entries in mpv internal playlist"

        media = playlist[0]
        return media.get("playing", False)

    def is_paused(self):
        """Query if mpv is paused.

        Returns:
            bool: `True` if mpv is paused.
        """
        return self.player.pause

    def is_playing_this(self, what):
        """Query if mpv is playing the requested media type.

        It is pretty difficult to get what mpv is/was playing, as it does not
        have a media object, but only a path to the current media file (that
        disappears when the said file ends), and a playlist that contains the
        path of the latest media file (that disappears when another file is set
        to play). We can only rely on the playlist path, and this is pretty
        weak. I don't have any better solution for now.

        Args:
            what (str): Tell if mpv current track is of the requested type, but
                not if it is actually playing it (it can be in pause).

        Returns:
            bool: `True` if mpv is playing the requested type.

        Raises:
            AssertError: If too many entries are present in the mpv internal
                playlist.
        """
        playlist = self.player.playlist

        if len(playlist) == 0:
            return False

        assert len(playlist) == 1, "Too many entries in mpv internal playlist"

        media = playlist[0]
        media_path = Path(media.get("filename") or "")

        if what == "idle":
            return media_path == self.background_loader.backgrounds["idle"]

        return (media_path == self.playlist_entry_data[what].path) and (
            media_path != Path("")
        )

    def play(self, what):
        """Request mpv to play something.

        No preparation should be done by this function, i.e. the media track
        should have been prepared already by `set_playlist_entry`.

        Args:
            what (str): What media to play.

        Raises:
            ValueError: If the action to play is unknown.
        """
        # reset player
        self.player.sub_files = []
        self.player.audio_files = []
        self.player.audio = "auto"
        self.player.pause = False
        self.player.end = "none"

        if what == "idle":
            # if already idle, do nothing
            if self.is_playing_this("idle"):
                return

            self.generate_text("idle")
            self.player.play(self.background_loader.backgrounds["idle"])
            self.player.sub_files = str(self.text_paths["idle"])

            return

        if what == "transition":
            self.player.play(str(self.playlist_entry_data["transition"].path))
            self.player.sub_files = str(self.text_paths["transition"])
            self.player.end = str(self.durations["transition"])

            return

        if what == "song":
            # manage instrumental track/file
            path_audio = str(self.playlist_entry_data["song"].path_audio)
            if path_audio:
                if path_audio == "self":
                    # mpv use different index for each track, so we can safely request
                    # the second audio track
                    self.player.audio = 2
                    logger.debug("Requesting to play audio track 2")

                else:
                    self.player.audio_files = [path_audio]
                    logger.debug("Requesting to play audio file %s", path_audio)

            # if the subtitle file cannot be discovered, do not request it
            if self.playlist_entry_data["song"].path_subtitle:
                self.player.sub_files = [
                    str(self.playlist_entry_data["song"].path_subtitle)
                ]

            self.player.play(str(self.playlist_entry_data["song"].path))

            return

        raise ValueError("Unexpected action to play: {}".format(what))

    @on_playing_this(["transition", "song"])
    def pause(self):
        """Request mpv to pause or unpause.

        Can only work on transition screens or songs. Pausing should have no
        effect if mpv is already paused.
        """
        if self.is_paused():
            logger.debug("Player already in pause")
            return

        logger.info("Setting pause")
        self.player.pause = True

    @on_playing_this(["transition", "song"])
    def resume(self):
        """Request mpv to resume playing.

        Can only work on transition screens or songs. Resuming should have no
        effect if mpv is already playing.
        """
        if not self.is_paused():
            logger.debug("Player already playing")
            return

        logger.info("Resuming play")
        self.player.pause = False

    @on_playing_this(["song"])
    def restart(self):
        """Request to restart the current media.

        Can only work on songs.
        """
        logger.info("Restarting media")
        self.player.time_pos = 0
        self.callbacks["updated_timing"](self.playlist_entry["id"], self.get_timing())

    @on_playing_this(["transition", "song"])
    def skip(self, no_callback=False):
        """Request to skip the current media.

        Can only work on transition screens or songs. mpv should
        continue playing, but media has to be considered already finished.

        Args:
            no_callback (bool): If `True`, no callback to signal the song has
                finished will be executed.
        """
        logger.info("Skipping '%s'", self.playlist_entry["song"]["title"])
        self.player_data["skip"] = True
        if not no_callback:
            self.callbacks["finished"](self.playlist_entry["id"])

        self.clear_playlist_entry()

    @on_playing_this(["song"])
    def rewind(self):
        """Request to rewind a few seconds the media.

        Can only work on songs. It cannot rewind before the beginning of the
        media. In that case, restart the song.
        """
        timing = self.player.time_pos - self.durations["rewind_fast_forward"]

        if timing < 0:
            self.restart()
            return

        logger.info("Rewinding media")
        self.player.time_pos = timing
        self.callbacks["updated_timing"](self.playlist_entry["id"], self.get_timing())

    @on_playing_this(["song"])
    def fast_forward(self):
        """Request to fast forward a few seconds the media.

        Can only work on songs. It cannot advance passed the end of the media.
        In that case, skip the song.
        """
        timing = self.player.time_pos + self.durations["rewind_fast_forward"]

        if timing > self.player.duration:
            self.skip()
            return

        logger.info("Fast forwarding media")
        self.player.time_pos = timing
        self.callbacks["updated_timing"](self.playlist_entry["id"], self.get_timing())

    def stop_player(self):
        """Request to stop mpv."""
        logger.info("Stopping player")
        self.player.terminate()
        logger.debug("Stopped player")

    def set_playlist_entry_player(self, playlist_entry, file_path, autoplay):
        """Prepare playlist entry data to be played.

        Prepare all media objects, subtitles, etc. for being played, for the
        transition screen and the song. Such data are stored on the dedicated
        object `playlist_entry_data`.

        Args:
            playlist_entry (dict): Playlist entry object.
            file_path (pathlib.Path): Absolute path to the song file.
            autoplay (bool): If `True`, start to play transition screen as soon
                as possible (i.e. as soon as the transition screen media is
                ready). The song media is prepared when the transition screen
                is playing.
        """
        # if the player is playing the idle screen, mark to skip it
        if self.is_playing_this("idle"):
            self.player_data["skip"] = True

        # set transition
        self.playlist_entry_data[
            "transition"
        ].path = self.background_loader.backgrounds["transition"]
        self.generate_text("transition")

        if autoplay:
            self.play("transition")

        # set song
        self.playlist_entry_data["song"].path = file_path

        # manually set the subtitles as a workaround for the matching of
        # mpv being too permissive
        path_without_ext = file_path.parent / file_path.stem
        for subtitle_extension in SUBTITLE_EXTENSIONS:
            path_subtitle = path_without_ext.with_suffix(subtitle_extension)
            if path_subtitle.exists():
                break

        else:
            path_subtitle = None

        self.playlist_entry_data["song"].path_subtitle = path_subtitle

        # manage instrumental
        if playlist_entry["use_instrumental"]:
            self.manage_instrumental(playlist_entry, file_path)

    def manage_instrumental(self, playlist_entry, file_path):
        """Manage the requested instrumental track.

        Instrumental track is searched first in audio files having the same
        name as the video file, then in extra audio tracks of the video file.

        As mpv cannot fetch information of a media in advance, we have to
        discover and set the instrumental track when the media starts.

        Args:
            playlist_entry (dict): Playlist entry data. Must contain the key
                `use_instrumental`.
            file_path (pathlib.Path): Path of the song file.
        """
        # get instrumental file if possible
        audio_path = self.get_instrumental_file(file_path)

        if audio_path:
            self.playlist_entry_data["song"].path_audio = audio_path
            logger.info(
                "Requesting to play instrumental file '%s' for '%s'",
                audio_path,
                file_path,
            )

            return

        # otherwise mark to look for instrumental track in internal tracks when
        # starting to read the media
        self.playlist_entry_data["song"].path_audio = "self"
        logger.info("Requesting to play instrumental track of '%s'", file_path)

    def clear_playlist_entry_player(self):
        """Clean playlist entry data after being played."""
        self.playlist_entry_data = {
            "transition": Media(),
            "song": MediaSong(),
        }

    @safe
    def handle_end_file(self, event):
        """Callback called when a media ends.

        This happens when:
            - A transition screen ends, leading to playing the actual song;
            - A song ends normally, leading to calling the callback
                `callbacks["finished"]`;
            - A song ends because it has been skipped, this case is ignored.

        Args:
            event (dict): Mpv event.

        Raises:
            InvalidStateError: If the context of call of this callback is
                unexpected.
        """
        logger.debug("File end callback called")

        # only handle when a file naturally ends (i.e. is not skipped)
        # i know this strategy is risky but it is the only way for this version
        # of mpv
        if self.player_data["skip"]:
            self.player_data["skip"] = False
            logger.debug("File has been skipped")

            return

        # the transition screen has finished, request to play the song itself
        if self.is_playing_this("transition"):
            logger.debug("Will play '{}'".format(self.playlist_entry_data["song"].path))
            self.play("song")

            return

        # the media has finished, so clean memory and call the according callback
        if self.is_playing_this("song"):
            playlist_entry_id = self.playlist_entry["id"]
            self.clear_playlist_entry()
            self.callbacks["finished"](playlist_entry_id)

            return

        # if no state can be determined, raise an error
        raise InvalidStateError("End file on an undeterminated state")

    @safe
    def handle_log_messages(self, loglevel, component, message):
        """Callback called when a log message occurs.

        Direct the message to the logger for Dakara Player. If the level is
        "fatal" or higher, call the callback `callbacks["error"]` and skip the
        media.

        Args:
            loglevel (str): Level of the log message.
            component (str): Component of mpv that generated the message.
            message (str): Actual log message.
        """
        logger.debug("Log message callback called")
        intlevel = MPV_ERROR_LEVELS.get(loglevel, logging.NOTSET)

        # use a proper logger for mpv logs
        mpv_logger.log(intlevel, "%s: %s", component, message)

        # handle all errors here
        if intlevel == logging.CRITICAL:
            if self.is_playing_this("song"):
                logger.error("Unable to play '%s'", self.player.path)
                self.callbacks["error"](
                    self.playlist_entry["id"],
                    "Unable to play current song: {}".format(message),
                )
                self.skip()

    @safe
    def handle_start_file(self, event):
        """Callback called when a media starts.

        This happens when:
            - A transition screen starts;
            - A song starts;
            - A idle screen starts.

        Args:
            event (dict): Mpv event.

        Raises:
            InvalidStateError: If the context of call of this callback is
                unexpected.
        """
        logger.debug("Start file callback called")

        # the transition screen starts to play
        if self.is_playing_this("transition"):
            self.callbacks["started_transition"](self.playlist_entry["id"])
            logger.info(
                "Playing transition for '%s'", self.playlist_entry["song"]["title"]
            )

            return

        # the song starts to play
        if self.is_playing_this("song"):
            self.callbacks["started_song"](self.playlist_entry["id"])
            logger.info(
                "Now playing '%s' ('%s')",
                self.playlist_entry["song"]["title"],
                self.player.path,
            )

            return

        # the idle screen starts to play
        if self.is_playing_this("idle"):
            logger.debug("Playing idle screen")

            return

        raise InvalidStateError("Start file on an undeterminated state")

    def get_audio_tracks_id(self):
        """Get ID of audio tracks for the current media.

        Returns:
            list of int: ID of audio tracks in the media.
        """
        audio = [
            item["id"] for item in self.player.track_list if item["type"] == "audio"
        ]

        return audio

    @safe
    def handle_pause(self, event):
        """Callback called when paused.

        Args:
            event (dict): Mpv event.
        """
        logger.debug("Pause callback called")

        # call paused callback
        self.callbacks["paused"](self.playlist_entry["id"], self.get_timing())

        logger.debug("Paused")

    @safe
    def handle_unpause(self, event):
        """Callback called when unpaused.

        If the player is skipping a song, do not handle this event.

        Args:
            event (dict): Mpv event.
        """
        logger.debug("Unpause callback called")

        if self.player_data["skip"]:
            return

        self.callbacks["resumed"](self.playlist_entry["id"], self.get_timing())

        logger.debug("Resumed play")


class MediaPlayerMpvPost0330(MediaPlayerMpvOld):
    """Class to manipulate newer mpv versions (>= 0.33.0).

    The class can be used as a context manager that closes mpv
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
        player_name (str): Name of mpv.
        fullscreen (bool): If `True`, mpv will be fullscreen.
        kara_folder_path (pathlib.Path): Path to the karaoke folder.
        playlist_entry (dict): Playlist entyr object.
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
        player (mpv.MPV): Instance of mpv.
        playlist_entry_data (dict): Extra data of the playlist entry.
        player_data (dict): Extra data of the player. This attribute is not
            used by the post 0.33.0 methods.
    """

    def is_playing(self):
        """Query if mpv is playing something.

        Returns:
            bool: `True` if mpv is playing something.
        """
        # query if the player is currently playing
        if self.is_paused():
            return False

        current_entries = [e for e in self.player.playlist if e.get("playing")]
        return bool(len(current_entries))

    def was_playing_this(self, what, id):
        """Query if mpv was playing the requested internal playlist ID.

        Args:
            what (str): Type of the track.
            id (int): ID of the track in mpv internal playlist.

        Returns:
            bool: `True` if mpv was playing the requested track.

        Raises:
            AssertError: If zero or more than one entries correspond to the
                provided ID.
        """
        # extract entry from playlist
        entries = [e for e in self.player.playlist if e["id"] == id]

        assert len(entries) < 2, "There are more than one media that was playing"
        assert len(entries) > 0, "No media was playing"

        return self.is_playing_this(what, entries[0]["filename"])

    def is_playing_this(self, what, media_path=None):
        """Query if mpv is playing the requested media type.

        Args:
            what (str): Tell if mpv current track is of the requested type, but
                not if it is actually playing it (it can be in pause).
            media_path (pathlib.Path): Optional media path.

        Returns:
            bool: `True` if mpv is playing the requested type.
        """
        media_path = Path(media_path or self.player.path or "")

        if what == "idle":
            return media_path == self.background_loader.backgrounds["idle"]

        return (media_path == self.playlist_entry_data[what].path) and (
            media_path != Path("")
        )

    @safe
    def handle_end_file(self, event):
        """Callback called when a media ends.

        This happens when:
            - A transition screen ends, leading to playing the actual song;
            - A song ends normally, leading to calling the callback
                `callbacks["finished"]`;
            - A song ends because it has been skipped, this case is ignored.

        Args:
            event (dict): Mpv event.

        Raises:
            InvalidStateError: If the context of call of this callback is
                unexpected.
        """
        logger.debug("File end callback called")
        id = event["playlist_entry_id"]

        # only handle when a file naturally ends
        # we additionnaly check the skip flag as sometimes the reason is not correct
        if event["reason"] != "eof" or self.player_data["skip"]:
            self.player_data["skip"] = False
            logger.debug("File has been skipped")

            return

        # the transition screen has finished, request to play the song itself
        if self.was_playing_this("transition", id):
            logger.debug("Will play '{}'".format(self.playlist_entry_data["song"].path))
            self.play("song")

            return

        # the media has finished, so clean memory and call the according callback
        if self.was_playing_this("song", id):
            playlist_entry_id = self.playlist_entry["id"]
            self.clear_playlist_entry()
            self.callbacks["finished"](playlist_entry_id)

            return

        # if no state can be determined, raise an error
        raise InvalidStateError("End file on an undeterminated state")


class MediaPlayerMpvPost0340(MediaPlayerMpvPost0330):
    """Class to manipulate newer mpv versions (>= 0.34.0).

    The class can be used as a context manager that closes mpv
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
        player_name (str): Name of mpv.
        fullscreen (bool): If `True`, mpv will be fullscreen.
        kara_folder_path (pathlib.Path): Path to the karaoke folder.
        playlist_entry (dict): Playlist entyr object.
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
        player (mpv.MPV): Instance of mpv.
        playlist_entry_data (dict): Extra data of the playlist entry.
        player_data (dict): Extra data of the player. Used to store if the
            player is initializing.
    """

    def set_mpv_default_callbacks(self):
        """Set mpv default callbacks.

        Some callbacks are binded to a property change, but mpv will call them
        immediately. To prevent inappropriate callbacks to be called, we have
        to register an initializing state in memory, that will be unregistered
        as soon as possible (just after calling `load`).
        """
        # binding properties
        self.player_data["initializing"] = True
        self.player.bind_property_observer("pause", self.handle_pause)

        # binding events
        self.player.bind_event("end-file", self.handle_end_file)
        self.player.bind_event("start-file", self.handle_start_file)

    def is_initializing(self):
        """Tell if mpv is initializing.

        This function is used to prevent execution of property observer
        callbacks just after their binding.

        Returns:
            bool: `True` if initializing.
        """
        return self.player_data.get("initializing", False)

    def load_player(self):
        super().load_player()

        # ensure initialization is done
        self.player_data["initializing"] = False

    @safe
    def handle_pause(self, name, paused):
        """Callback called when paused or unpaused.

        Args:
            name (str): Name of the property that changed. Should be `"pause"`.
            paused (bool): `True` if paused, `False` otherwise.
        """
        assert name == "pause"

        logger.debug("Pause callback called")

        # invalidate call if initializing
        if self.is_initializing():
            logger.debug("Pause callback aborted")

            return

        if paused:
            # call paused callback
            self.callbacks["paused"](self.playlist_entry["id"], self.get_timing())

            logger.debug("Paused")

            return

        if self.player_data["skip"]:
            return

        self.callbacks["resumed"](self.playlist_entry["id"], self.get_timing())

        logger.debug("Resumed play")


class Media:
    """Media class."""

    def __init__(self, path=None):
        self.path = path


class MediaSong(Media):
    """Song class."""

    def __init__(self, *args, path_subtitle=None, path_audio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.path_subtitle = path_subtitle
        self.path_audio = path_audio


class MpvTooOldError(DakaraError):
    """Error raised if MPV is too old."""
