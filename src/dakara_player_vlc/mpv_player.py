import logging
import os

try:
    import mpv

except OSError:
    mpv = None

from dakara_player_vlc.media_player import MediaPlayer, MediaPlayerNotAvailableError
from dakara_player_vlc.version import __version__


logger = logging.getLogger(__name__)


class MpvNotAvailableError(MediaPlayerNotAvailableError):
    """Error raised when trying to use the `MpvMediaPlayer` class if MPV cannot be found
    """


class MpvMediaPlayer(MediaPlayer):
    """Interface for the Python MPV wrapper

    This class allows the usage of mpv as a player for Dakara.

    The playlist is virtually handled using song-end callbacks.

    Attributes:
        player (mpv.Mpv): instance of mpv, attached to the actual player.
        media_pending (str): path of a song which will be played after the transition
            screen.
    """

    player_name = "MPV"
    player_not_available_error_class = MpvNotAvailableError

    @staticmethod
    def is_available():
        """Check if MPV can be used
        """
        return mpv is not None

    def init_player(self, config, tempdir):
        # set mpv player options and logging
        config_loglevel = config.get("loglevel") or "info"
        self.player = mpv.MPV(
            log_handler=self.handle_log_messages, loglevel=config_loglevel
        )
        config_mpv = config.get("mpv") or {}
        for mpv_option in config_mpv:
            self.player[mpv_option] = config_mpv[mpv_option]

        # set mpv callbacks
        self.set_mpv_default_callbacks()

        # media containing a song which will be played after the transition
        # screen
        self.media_pending = None

    def load_player(self):
        # check mpv version
        self.check_mpv_version()

        # set mpv fullscreen
        self.player.fullscreen = self.fullscreen

        # force a single window
        self.player.force_window = True

    def check_mpv_version(self):
        """Print the mpv version
        """
        # get and log version
        logger.info(self.player.mpv_version)

    def set_mpv_default_callbacks(self):
        """Set mpv player default callbacks
        """
        # wrapper to use the event_callback decorator for setting handle_end_reached
        @self.player.event_callback("end_file")
        def end_file_callback(event):
            self.handle_end_reached(event)

    def handle_end_reached(self, event):
        """Callback called when a media ends

        This happens when:
            - A transition screen ends, leading to playing the actual song;
            - A song ends, leading to calling the callback
                `callbacks["finished"]`;
            - An idle screen ends, leading to reloop it.
        A new thread is created in any case.

        Args:
            event (mpv.MpvEventEndFile): mpv end fle event object.
        """
        # check that the reason is actually a file ending (could be a force stop)
        if event["event"]["reason"] != mpv.MpvEventEndFile.EOF:
            return

        logger.debug("Song end callback called")

        if self.in_transition:
            # if the transition screen has finished,
            # request to play the song itself
            self.in_transition = False

            # manually set the subtitles as a workaround for the matching of mpv being
            # too permissive
            filename_without_ext = os.path.splitext(self.media_pending)[0]
            sub_file = None
            if os.path.exists("{}.ass".format(filename_without_ext)):
                sub_file = "{}.ass".format(filename_without_ext)
            elif os.path.exists("{}.ssa".format(filename_without_ext)):
                sub_file = "{}.ssa".format(filename_without_ext)

            thread = self.create_thread(
                target=self.play_media, args=(self.media_pending, sub_file)
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

        Direct the message to the logger for Dakara Player.
        If the level is 'error' or higher, call the callbacks
        `callbackss["finished"]` and `callbacks["error"]`

        Args:
            loglevel (str): level of the log message
            component (str): component of mpv that generated the message
            message (str): actual log message
        """
        if loglevel == "fatal":
            intlevel = logging.CRITICAL
        elif loglevel == "error":
            intlevel = logging.ERROR
        elif loglevel == "warn":
            intlevel = logging.WARNING
        elif loglevel == "info":
            intlevel = logging.INFO
        elif loglevel == "debug":
            intlevel = logging.DEBUG
        else:
            intlevel = logging.NOTSET

        logger.log(intlevel, "mpv: {}: {}".format(component, message))

        if intlevel >= logging.ERROR:
            message = "Unable to play current media"
            logger.error(message)

            self.in_transition = False

            self.callbacks["finished"](self.playing_id)
            self.callbacks["error"](self.playing_id, message)

    def play_media(self, media, sub_file=None):
        """Play the given media

        Args:
            media (str): path to media
        """
        self.player["sub-files"] = [sub_file] if sub_file else []
        self.player.loadfile(media)

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
        self.media_pending = str(file_path)

        # create the transition screen
        with self.transition_text_path.open("w", encoding="utf8") as file:
            file.write(
                self.text_generator.create_transition_text(
                    playlist_entry, fade_in=False
                )
            )

        media_transition = str(self.background_loader.backgrounds["transition"])

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
