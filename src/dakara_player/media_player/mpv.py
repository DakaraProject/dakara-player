import logging
import re

from dakara_base.safe_workers import safe
from packaging.version import parse, Version

try:
    import python_mpv_jsonipc as mpv

except ImportError:
    mpv = None

from dakara_player.media_player.base import (
    InvalidStateError,
    MediaPlayer,
    VersionNotFoundError,
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


def get_media_player_mpv_class():
    """Get the mpv media player class according to installed version.

    Returns:
        object: Will return `MediaPlayerMpvPost0330` if mpv version is
        higher than 0.33.0, or `MediaPlayerMpvOld` otherwise.
    """
    version = MediaPlayerMpvOld.get_version()

    if version >= Version("0.33.0"):
        logger.debug("Using post 0.33.0 API of mpv")
        return MediaPlayerMpvPost0330

    logger.debug("Using old API of mpv")
    return MediaPlayerMpvOld


def media_player_mpv_selector(*args, **kwargs):
    """Instanciate the right mpv media player class.

    Returns:
        MediaPlayer: Instance of the mpv media player for the correct version
        of mpv.
    """
    return get_media_player_mpv_class()(*args, **kwargs)


class MediaPlayerMpvOld(MediaPlayer):
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
        tempdir (path.Path): Path of the temporary directory.

    Attributes:
        stop (threading.Event): Stop event that notify to stop the entire
            program when set.
        errors (queue.Queue): Error queue to communicate the exception to the
            main thread.
        player_name (str): Name of mpv.
        fullscreen (bool): If True, mpv will be fullscreen.
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
        player (mpv.MPV): Instance of mpv.
        playlist_entry_data (dict): Extra data of the playlist entry.
        player_data (dict): Extra data of the player.
    """

    player_name = "mpv"

    @staticmethod
    def is_available():
        """Indicate if mpv is available.

        Returns:
            bool: True if mpv is useable.
        """
        if mpv is None:
            return False

        try:
            player = mpv.MPV()
            player.terminate()
            return True

        except FileNotFoundError:
            return False

    def init_player(self, config, tempdir):
        """Initialize the objects of mpv.

        Actions performed in this method should not have any side effects
        (query file system, etc.).

        Args:
            config (dict): Dictionary of configuration.
            tempdir (path.Path): Path of the temporary directory.
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
        self.player_data = {"skip": False}

    def load_player(self):
        """Perform actions with side effects for mpv initialization.
        """
        # set mpv callbacks
        self.set_mpv_default_callbacks()

        # set mpv fullscreen
        self.player.fullscreen = self.fullscreen

        # log mpv version
        logger.info("mpv %s", self.get_version())

        # set mpv as a single non-interactive window
        self.player.force_window = "immediate"
        self.player.input_default_bindings = False
        self.player.osc = False
        self.player.osd_level = 0

        # set window title
        self.player.title = "Dakara player mpv"

    def get_timing(self):
        """Get mpv timing.

        Returns:
            int: Current song timing in seconds if a song is playing, or 0 when
                idle or during transition screen.
        """
        if self.is_playing_this("idle") or self.is_playing_this("transition"):
            return 0

        timing = self.player.time_pos or 0

        return int(timing)

    @staticmethod
    def get_version():
        """Get media player version.

        mpv version is in the form "mpv x.y.z+git.v.w" where "v" is a timestamp
        and "w" a commit hash for post releases, or "mpv x.y.z" for releases.

        In case of post release, as the version given by mpv does not respect
        semantic versionning, the sub-version is the concatenation of the day
        part and the time part of "v".

        Returns:
            packaging.version.Version: Parsed version of mpv.
        """
        player = mpv.MPV()
        match = re.search(
            r"mpv (\d+\.\d+\.\d+)(?:\+git\.(\d{8})T(\d{6})\..*)?", player.mpv_version,
        )
        player.terminate()

        if match:
            if match.group(2) and match.group(3):
                return parse(match.group(1) + "-post" + match.group(2) + match.group(3))

            return parse(match.group(1))

        raise VersionNotFoundError("Unable to get mpv version")

    def set_mpv_default_callbacks(self):
        """Set mpv default callbacks.
        """
        self.player.bind_event("end-file", self.handle_end_file)
        self.player.bind_event("start-file", self.handle_start_file)
        self.player.bind_event("pause", self.handle_pause)
        self.player.bind_event("unpause", self.handle_unpause)

    def is_playing(self):
        """Query if mpv is playing something.

        Returns:
            bool: True if mpv is playing something.
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
            bool: True if mpv is paused.
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
            bool: True if mpv is playing the requested type.
        """
        playlist = self.player.playlist

        if len(playlist) == 0:
            return False

        assert len(playlist) == 1, "Too many entries in mpv internal playlist"

        media = playlist[0]
        path = media.get("filename")

        if what == "idle":
            return path == self.background_loader.backgrounds["idle"]

        return path == self.playlist_entry_data[what].path

    def play(self, what):
        """Request mpv to play something.

        No preparation should be done by this function, i.e. the media track
        should have been prepared already by `set_playlist_entry`.

        Args:
            what (str): What media to play.
        """
        # reset player
        self.player.image_display_duration = 0
        self.player.sub_files = []
        self.player.audio_files = []
        self.player.audio = "auto"
        self.player.pause = False

        if what == "idle":
            # if already idle, do nothing
            if self.is_playing_this("idle"):
                return

            self.player.image_display_duration = "inf"
            self.player.sub_files = [self.text_paths["idle"]]
            self.generate_text("idle")
            self.player.play(self.background_loader.backgrounds["idle"])

            return

        if what == "transition":
            self.player.image_display_duration = int(self.durations["transition"])
            self.player.sub_files = [self.text_paths["transition"]]
            self.player.play(self.playlist_entry_data["transition"].path)

            return

        if what == "song":
            # manage instrumental track/file
            path_audio = self.playlist_entry_data["song"].path_audio
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
                self.player.sub_files = [self.playlist_entry_data["song"].path_subtitle]

            self.player.play(self.playlist_entry_data["song"].path)

            return

        raise ValueError("Unexpected action to play: {}".format(what))

    def pause(self, pause):
        """Request mpv to pause or unpause.

        Can only work on transition screens or songs. Pausing should have no
        effect if mpv is already paused, unpausing should have no
        effect if mpv is already unpaused.

        Args:
            paused (bool): If True, pause mpv.
        """
        if self.is_playing_this("idle"):
            return

        if pause:
            if self.is_paused():
                logger.debug("Player already in pause")
                return

            logger.info("Setting pause")
            self.player.pause = True
            return

        if not self.is_paused():
            logger.debug("Player already playing")
            return

        logger.info("Resuming play")
        self.player.pause = False

    def skip(self):
        """Request to skip the current media.

        Can only work on transition screens or songs. mpv should
        continue playing, but media has to be considered already finished.
        """
        if self.is_playing_this("transition") or self.is_playing_this("song"):
            logger.info("Skipping '%s'", self.playlist_entry["song"]["title"])
            self.player_data["skip"] = True
            self.callbacks["finished"](self.playlist_entry["id"])
            self.clear_playlist_entry()

    def stop_player(self):
        """Request to stop mpv.
        """
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
            file_path (path.Path): Absolute path to the song file.
            autoplay (bool): If True, start to play transition screen as soon
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
        self.generate_text("transition", fade_in=False)

        if autoplay:
            self.play("transition")

        # set song
        self.playlist_entry_data["song"].path = file_path

        # manually set the subtitles as a workaround for the matching of
        # mpv being too permissive
        path_without_ext = file_path.dirname() / file_path.stem
        for subtitle_extension in SUBTITLE_EXTENSIONS:
            path_subtitle = path_without_ext + subtitle_extension
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
            file_path (path.Path): Path of the song file.
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
        """Clean playlist entry data after being played.
        """
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
            event (dict): mpv event.
        """
        logger.debug("File end callback called")

        # only handle when a file naturally ends (i.e. is not skipped)
        # i know this strategy is risky, but it is not possible to not capture
        # end-file for EOF only with the stable version of mpv (0.32.0)
        if self.player_data["skip"]:
            self.player_data["skip"] = False
            logger.debug("File has been skipped")
            return

        # the transition screen has finished, request to play the song itself
        if self.is_playing_this("transition"):
            logger.debug("Will play '{}'".format(self.playlist_entry_data["song"].path))
            self.play("song")

            return

        # the media has finished, so call the according callback and clean memory
        if self.is_playing_this("song"):
            self.callbacks["finished"](self.playlist_entry["id"])
            self.clear_playlist_entry()

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
            event (dict): mpv event.
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
            event (dict): mpv event.
        """
        logger.debug("Pause callback called")

        # call paused callback
        self.callbacks["paused"](self.playlist_entry["id"], self.get_timing())

        logger.debug("Paused")

    @safe
    def handle_unpause(self, event):
        """Callback called when unpaused.

        Args:
            event (dict): mpv event.
        """
        logger.debug("Unpause callback called")

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
        tempdir (path.Path): Path of the temporary directory.

    Attributes:
        stop (threading.Event): Stop event that notify to stop the entire
            program when set.
        errors (queue.Queue): Error queue to communicate the exception to the
            main thread.
        player_name (str): Name of mpv.
        fullscreen (bool): If True, mpv will be fullscreen.
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
        player (mpv.MPV): Instance of mpv.
        playlist_entry_data (dict): Extra data of the playlist entry.
        player_data (dict): Extra data of the player. This attribute is not
            used by the post 0.33.0 methods.
    """

    def is_playing(self):
        """Query if mpv is playing something.

        Returns:
            bool: True if mpv is playing something.
        """
        # query if the player is currently playing
        if self.is_paused():
            return False

        current_entries = [e for e in self.player.playlist if e.get("playing")]
        return bool(len(current_entries))

    def was_playing_this(self, what, id):
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

        Returns:
            bool: True if mpv is playing the requested type.
        """
        media_path = media_path or self.player.path

        if what == "idle":
            return media_path == self.background_loader.backgrounds["idle"]

        return media_path == self.playlist_entry_data[what].path

    @safe
    def handle_end_file(self, event):
        """Callback called when a media ends.

        This happens when:
            - A transition screen ends, leading to playing the actual song;
            - A song ends normally, leading to calling the callback
                `callbacks["finished"]`;
            - A song ends because it has been skipped, this case is ignored.

        Args:
            event (dict): mpv event.
        """
        logger.debug("File end callback called")
        id = event["playlist_entry_id"]

        # only handle when a file naturally ends
        if event["reason"] != "eof":
            logger.debug("File has been skipped")
            return

        # the transition screen has finished, request to play the song itself
        if self.was_playing_this("transition", id):
            logger.debug("Will play '{}'".format(self.playlist_entry_data["song"].path))
            self.play("song")

            return

        # the media has finished, so call the according callback and clean memory
        if self.was_playing_this("song", id):
            self.callbacks["finished"](self.playlist_entry["id"])
            self.clear_playlist_entry()

            return

        # if no state can be determined, raise an error
        raise InvalidStateError("End file on an undeterminated state")


class Media:
    """Media class.
    """

    def __init__(self, path=None):
        self.path = path


class MediaSong(Media):
    """Song class.
    """

    def __init__(self, *args, path_subtitle=None, path_audio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.path_subtitle = path_subtitle
        self.path_audio = path_audio
