import logging
import os
import re

from packaging.version import parse

try:
    import python_mpv_jsonipc as mpv

except ImportError:
    mpv = None

from dakara_player_vlc.media_player import (
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


class MediaPlayerMpv(MediaPlayer):
    """Class to manipulate mpv.

    The class can be used as a context manager that closes mpv
    automatically on exit.

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
        text_generator (dakara_player_vlc.text_generator.TextGenerator): Text
            generator instance.
        background_loader
        (dakara_player_vlc.background_loader.BackgroundLoader): Background
            loader instance.
        player (mpv.MPV): Instance of mpv.
        playlist_entry_data (dict): Extra data of the playlist entry.
        player_data (dict): Extra data of the player.
    """

    player_name = "mpv"

    # TODO remove that monstruosity
    if os.name == "nt":
        os.environ["PATH"] = (
            f"{os.environ['PATH']};{os.getcwd()}"
            + ";C:\\ProgramData\\chocolatey\\lib\\mpv.install\\tools"
        )

    @staticmethod
    def is_available():
        """Indicate if mpv is available.

        Must be overriden.

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

        Can be overriden.

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
        self.player.osc = False
        self.player.osd_level = 0

    def get_timing(self):
        """Get mpv timing.

        Returns:
            int: Current song timing in seconds if a song is playing, or 0 when
                idle or during transition screen.
        """
        if self.is_playing("idle") or self.is_playing("transition"):
            return 0

        timing = self.player.time_pos or 0

        return int(timing)

    def get_version(self):
        """Get media player version.

        mpv version is in the form "mpv x.y.z+git.w" where "w" is a timestamp,
        or "mpv x.y.z" in text.

        Returns:
            packaging.version.Version: Parsed version of mpv.
        """
        match = re.search(r"mpv (\d+\.\d+\.\d+)", self.player.mpv_version)
        if match:
            return parse(match.group(1))

        raise VersionNotFoundError("Unable to get mpv version")

    def set_mpv_default_callbacks(self):
        """Set mpv default callbacks.
        """
        self.player.bind_event("end-file", self.handle_end_file)
        self.player.bind_event("start-file", self.handle_start_file)
        self.player.bind_event("pause", self.handle_pause)
        self.player.bind_event("unpause", self.handle_unpause)

    def is_playing(self, what=None):
        """Query if mpv is playing something.

        It is pretty difficult to get what mpv is playing, as it does not have
        a media object, but only a path to the media file, and as this path is
        destroyed when the media ends. We can only rely on the path, and this
        is pretty weak. I don't have any better solution for now.

        Args:
            what (str): If provided, tell if mpv current track is
                of the requested type, but not if it is actually playing it (it
                can be in paused). If not provided, tell if mpv is
                actually playing anything.

        Returns:
            bool: True if mpv is playing something.
        """
        playlist = self.player.playlist

        if len(playlist) == 0:
            return False

        assert len(playlist) == 1, "Too many entries in mpv internal playlist"

        media = playlist[0]
        path = media.get("filename")

        if what:
            if what == "idle":
                return path == self.background_loader.backgrounds["idle"]

            return path == self.playlist_entry_data[what].path

        # query if the player is currently playing
        if self.is_paused():
            return False

        return media.get("playing", False)

    def is_paused(self):
        """Query if mpv is paused.

        Returns:
            bool: True if mpv is paused.
        """
        return self.player.pause

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
        self.player.pause = False

        if what == "idle":
            path_media = self.background_loader.backgrounds["idle"]
            path_subtitle = self.text_paths["idle"]

            self.player.image_display_duration = "inf"

            self.generate_text("idle")

        elif what == "transition":
            path_media = self.playlist_entry_data["transition"].path
            path_subtitle = self.text_paths["transition"]

            self.player.image_display_duration = int(self.durations["transition"])

        elif what == "song":
            path_media = self.playlist_entry_data["song"].path
            path_subtitle = self.playlist_entry_data["song"].path_subtitle

        else:
            raise ValueError("Unexpected action to play: {}".format(what))

        self.player.sub_files = [str(path_subtitle)]
        self.player.play(str(path_media))

    def pause(self, pause):
        """Request mpv to pause or unpause.

        Can only work on transition screens or songs. Pausing should have no
        effect if mpv is already paused, unpausing should have no
        effect if mpv is already unpaused.

        Args:
            paused (bool): If True, pause mpv.
        """
        if self.is_playing("idle"):
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
        if self.is_playing("transition") or self.is_playing("song"):
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
        transition screen and the song. Such data are stored on a dedicated
        object, like `playlist_entry_data`.

        Args:
            playlist_entry (dict): Playlist entry object.
            file_path (path.Path): Absolute path to the song file.
            autoplay (bool): If True, start to play transition screen as soon
                as possible (i.e. as soon as the transition screen media is
                ready). The song media is prepared when the transition screen
                is playing.
        """
        # if the player is playing the idle screen, mark to skip it
        if self.is_playing("idle"):
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

    def clear_playlist_entry_player(self):
        """Clean playlist entry data after being played.
        """
        self.playlist_entry_data = {
            "transition": Media(),
            "song": MediaSong(),
        }

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
        # end-file for EOF only
        if self.player_data["skip"]:
            self.player_data["skip"] = False
            logger.debug("File has been skipped")
            return

        # the transition screen has finished, request to play the song itself
        if self.is_playing("transition"):
            logger.debug("Will play '{}'".format(self.playlist_entry_data["song"].path))
            self.play("song")

            return

        # the media has finished, so call the according callback and clean memory
        if self.is_playing("song"):
            self.callbacks["finished"](self.playlist_entry["id"])
            self.clear_playlist_entry()

            return

        # if no state can be determined, raise an error
        raise InvalidStateError("End file on an undeterminated state")

    def handle_log_messages(self, loglevel, component, message):
        """Callback called when a log message occurs.

        Direct the message to the logger for Dakara Player. If the level is
        "error" or higher, call the callback `callbacks["error"]` and skip the
        media.

        Args:
            loglevel (str): Level of the log message.
            component (str): Component of mpv that generated the message.
            message (str): Actual log message.
        """
        logger.debug("Log message callback called")
        intlevel = get_python_loglever(loglevel)

        # use a proper logger for mpv logs
        mpv_logger.log(intlevel, "%s: %s", component, message)

        # handle all errors here
        if intlevel >= logging.ERROR:
            if self.is_playing("song"):
                logger.error("Unable to play '%s'", self.player.path)
                self.callbacks["error"](
                    self.playlist_entry["id"],
                    "Unable to play current song: {}".format(message),
                )
                self.skip()

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
        if self.is_playing("transition"):
            self.callbacks["started_transition"](self.playlist_entry["id"])
            logger.info(
                "Playing transition for '%s'", self.playlist_entry["song"]["title"]
            )

            return

        # the song starts to play
        if self.is_playing("song"):
            self.callbacks["started_song"](self.playlist_entry["id"])
            logger.info(
                "Now playing '%s' ('%s')",
                self.playlist_entry["song"]["title"],
                self.player.path,
            )

            return

        # the idle screen starts to play
        if self.is_playing("idle"):
            logger.debug("Playing idle screen")

            return

        raise InvalidStateError("Start file on an undeterminated state")

    def handle_pause(self, event):
        """Callback called when paused.

        Args:
            event (dict): mpv event.
        """
        logger.debug("Pause callback called")

        # call paused callback
        self.callbacks["paused"](self.playlist_entry["id"], self.get_timing())

        logger.debug("Paused")

    def handle_unpause(self, event):
        """Callback called when unpaused.

        Args:
            event (dict): mpv event.
        """
        logger.debug("Unpause callback called")

        self.callbacks["resumed"](self.playlist_entry["id"], self.get_timing())

        logger.debug("Resumed play")


def get_python_loglever(loglevel):
    """Convert mpv loglevel name to Python loglevel name.

    Args:
        loglevel (str): Loglevel string used by mpv.

    Returns:
        str: Loglevel integer used by Python logging module.
    """
    if loglevel == "fatal":
        return logging.CRITICAL

    if loglevel == "error":
        return logging.ERROR

    if loglevel == "warn":
        return logging.WARNING

    if loglevel == "info":
        return logging.INFO

    if loglevel == "debug":
        return logging.DEBUG

    return logging.NOTSET


class Media:
    """Media class.
    """

    def __init__(self, path=None):
        self.path = path


class MediaSong(Media):
    """Song class.
    """

    def __init__(self, *args, path_subtitle=None, **kwargs):
        super().__init__(*args, **kwargs)
        path_subtitle = path_subtitle
