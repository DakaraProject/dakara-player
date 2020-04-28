import logging
import os
from pkg_resources import parse_version

from python_mpv_jsonipc import MPV, MPVError

from dakara_player_vlc.media_player import MediaPlayer, MediaPlayerNotAvailableError
from dakara_player_vlc.version import __version__


logger = logging.getLogger(__name__)

SUBTITLE_EXTENSIONS = [
    ".ass",
    ".ssa",
]


class MpvNotAvailableError(MediaPlayerNotAvailableError):
    """Error raised when trying to use the `MpvMediaPlayer` class if mpv cannot be found
    """


class MpvMediaPlayer(MediaPlayer):
    """Interface for the Python mpv wrapper

    This class allows the usage of mpv as a player for Dakara.

    The playlist is virtually handled using song-end callbacks.

    Attributes:
        player (python_mpv_jsonipc.MPV): instance of mpv, attached to the actual player.
        media_pending (str): path of a song which will be played after the transition
            screen.
    """

    player_name = "mpv"
    player_not_available_error_class = MpvNotAvailableError

    if os.name == 'nt':
        os.environ["PATH"] = f"{os.environ['PATH']};{os.getcwd()}"\
            + ";C:\\ProgramData\\chocolatey\\lib\\mpv.install\\tools"

    @staticmethod
    def is_available():
        """Check if mpv can be used
        """
        try:
            mpv = MPV()
            mpv.terminate()
            return True
        except(FileNotFoundError):
            return False

    def init_player(self, config, tempdir):
        # set mpv player options and logging
        loglevel = config.get("loglevel", "info")
        self.player = MPV(log_handler=self.handle_log_messages, loglevel=loglevel)
        config_mpv = config.get("mpv") or {}
        for key, value in config_mpv.items():
            try:
                self.player.__setattr__(key, value)
            except(MPVError):
                logger.error(f"Unable to set mpv option '{key}' to value '{value}'")

        # set mpv callbacks
        self.set_mpv_default_callbacks()

        # media containing a song which will be played after the transition
        # screen
        self.media_pending = None

    def load_player(self):
        # check mpv version
        self.get_version()

        # set mpv fullscreen
        self.player.fullscreen = self.fullscreen

        # set mpv as a single non-interactive window
        self.player.force_window = 'immediate'
        self.player.osc = False
        self.player.osd_level = 0

    def get_version(self):
        """Print the mpv version

        mpv version is in the form "mpv x.y.z+git.w" where "w" is a timestamp.
        """
        # and log version
        # only keep semver values
        version = parse_version(self.player.mpv_version.split()[1])
        self.version = version.base_version
        logger.info("mpv %s", self.version)

    def set_mpv_default_callbacks(self):
        """Set mpv player default callbacks
        """
        # mpv will switch to idle mode when there is nothing to play
        self.player.bind_event("idle", self.handle_end_reached)

    def handle_end_reached(self, event):
        """Callback called when a media ends

        This happens when:
            - A transition screen ends, leading to playing the actual song;
            - A song ends, leading to calling the callback
                `callbacks["finished"]`;
            - An idle screen ends, leading to reloop it.
        A new thread is created in any case.

        Args:
            event (dict): mpv event.
        """

        logger.debug("Song end callback called")

        if self.in_transition:
            # if the transition screen has finished,
            # request to play the song itself
            self.in_transition = False

            # manually set the subtitles as a workaround for the matching of mpv being
            # too permissive
            filepath_without_ext = (
                self.media_pending.dirname() / self.media_pending.stem
            )
            for subtitle_extension in SUBTITLE_EXTENSIONS:
                sub_filepath = filepath_without_ext + subtitle_extension
                if sub_filepath.exists():
                    break

            else:
                sub_filepath = None

            thread = self.create_thread(
                target=self.play_media, args=(self.media_pending, sub_filepath)
            )

            thread.start()

            # get file path
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
        logger.log(intlevel, "mpv: {}: {}".format(component, message))

        # handle all errors here
        if intlevel >= logging.ERROR:
            generic_message = "Unable to play current media"
            logger.error(generic_message)
            self.callbacks["finished"](self.playing_id)
            self.callbacks["error"](
                self.playing_id, "{}: {}".format(generic_message, message)
            )

            # reset current state
            self.playing_id = None
            self.in_transition = False

    def play_media(self, media, sub_file=None):
        """Play the given media

        Args:
            media (str): path to media
        """
        self.player.sub_files = [sub_file] if sub_file else []
        self.player.loadfile(str(media))
        self.player.pause = False

    def play_playlist_entry(self, playlist_entry):
        # file location
        file_path = self.kara_folder_path / playlist_entry["song"]["file_path"]

        # Check file exists
        if not file_path.exists():
            self.handle_file_not_found(file_path, playlist_entry["id"])
            return

        # create the media
        self.playing_id = playlist_entry["id"]
        self.media_pending = file_path

        # create the transition screen
        with self.transition_text_path.open("w", encoding="utf8") as file:
            file.write(
                self.text_generator.create_transition_text(
                    playlist_entry, fade_in=False
                )
            )

        media_transition = self.background_loader.backgrounds["transition"]

        self.in_transition = True

        self.player.image_display_duration = int(self.durations["transition"])
        self.play_media(media_transition, self.transition_text_path)
        logger.info("Playing transition for '%s'", file_path)
        self.callbacks["started_transition"](playlist_entry["id"])

    def play_idle_screen(self):
        # set idle state
        self.playing_id = None
        self.in_transition = False

        # create idle screen media
        media = self.background_loader.backgrounds["idle"]

        # create the idle screen
        with self.idle_text_path.open("w", encoding="utf8") as file:
            file.write(
                self.text_generator.create_idle_text(
                    {
                        "notes": [
                            "mpv {}".format(self.version),
                            "Dakara player {}".format(__version__),
                        ]
                    }
                )
            )

        self.player.image_display_duration = "inf"
        self.play_media(media, self.idle_text_path)
        logger.debug("Playing idle screen")

    def get_timing(self):
        if self.is_idle() or self.in_transition:
            return 0

        timing = self.player.time_pos

        if timing is None:
            return 0

        return int(timing)

    def is_paused(self):
        return self.player.pause

    def set_pause(self, pause):
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
        logger.info("Stopping player")
        self.player.terminate()
        logger.debug("Stopped player")


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
