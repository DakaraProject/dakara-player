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

SUBTITLE_EXTENSIONS = [
    ".ass",
    ".ssa",
]


class MediaPlayerMpv(MediaPlayer):
    """Interface for the Python mpv wrapper

    This class allows the usage of mpv as a player for Dakara.

    The playlist is virtually handled using callbacks.

    Attributes:
        player (mpv.MPV): instance of mpv, attached to the actual player.
        media_pending (str): path of a song which will be played after the transition
            screen.
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
        """Check if mpv can be used
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
        if self.is_playing("idle") or self.is_playing("transition"):
            return 0

        timing = self.player.time_pos or 0

        return int(timing)

    def get_version(self):
        """Get the mpv version

        mpv version is in the form "mpv x.y.z+git.w" where "w" is a timestamp,
        or "mpv x.y.z" in text.
        """
        match = re.search(r"mpv (\d+\.\d+\.\d+)", self.player.mpv_version)
        if match:
            return parse(match.group(1))

        raise VersionNotFoundError("Unable to get mpv version")

    def set_mpv_default_callbacks(self):
        """Set mpv player default callbacks
        """
        self.player.bind_event("end-file", self.handle_end_file)
        self.player.bind_event("start-file", self.handle_start_file)
        self.player.bind_event("pause", self.handle_pause)
        self.player.bind_event("unpause", self.handle_unpause)

    def is_playing(self, what=None):
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
        return self.player.pause

    def play(self, what):
        """Play the given media
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
        if self.is_playing("transition") or self.is_playing("song"):
            logger.info("Skipping '%s'", self.playlist_entry["song"]["title"])
            self.clear_playlist_entry()
            self.player_data["skip"] = True
            self.callbacks["finished"](self.playlist_entry["id"])

    def stop_player(self):
        logger.info("Stopping player")
        self.player.terminate()
        logger.debug("Stopped player")

    def set_playlist_entry_player(self, playlist_entry, file_path, autoplay):
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
        path_without_ext = file_path.dirname() / file_path.stem
        for subtitle_extension in SUBTITLE_EXTENSIONS:
            path_subtitle = path_without_ext + subtitle_extension
            if path_subtitle.exists():
                break

        else:
            path_subtitle = None

        self.playlist_entry_data["song"].path_subtitle = path_subtitle

    def clear_playlist_entry_player(self):
        self.playlist_entry_data = {
            "transition": Media(),
            "song": MediaSong(),
        }

    def handle_end_file(self, event):
        """Callback called when a media ends

        This happens when:
            - A transition screen ends, leading to playing the actual song;
            - A song ends, leading to calling the callback
                `callbacks["finished"]`;
            - An idle screen ends, leading to reloop it.

        Args:
            event (dict): mpv event.
        """
        logger.debug("File end callback called")

        # only handle when a file naturally ends (i.e. is not skipped)
        # i know this strategy is risky, but it is not possible to not capture
        # end-file for EOF only
        if self.player_data["skip"]:
            self.player_data["skip"] = False
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
        """Callback called when a log message occurs

        Direct the message to the logger for Dakara Player. If the level is
        "error" or higher, call the callbacks `callbackss["finished"]` and
        `callbacks["error"]`.

        Args:
            loglevel (str): Level of the log message.
            component (str): Component of mpv that generated the message.
            message (str): Actual log message.
        """
        logger.debug("Log message callback called")
        intlevel = get_python_loglever(loglevel)
        logger.log(intlevel, "mpv: %s: %s", component, message)

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
        logger.debug("Pause callback called")

        # call paused callback
        self.callbacks["paused"](self.playlist_entry["id"], self.get_timing())

        logger.debug("Paused")

    def handle_unpause(self, event):
        logger.debug("Unpause callback called")

        self.callbacks["resumed"](self.playlist_entry["id"], self.get_timing())

        logger.debug("Resumed play")


def get_python_loglever(loglevel):
    """Convert mpv loglevel name to Python loglevel name

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
    def __init__(self, path=None):
        self.path = path


class MediaSong(Media):
    def __init__(self, *args, path_subtitle=None, **kwargs):
        super().__init__(*args, **kwargs)
        path_subtitle = path_subtitle
