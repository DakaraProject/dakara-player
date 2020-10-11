import logging
from abc import ABC, abstractmethod
from threading import Timer

from dakara_base.exceptions import DakaraError
from dakara_base.safe_workers import Worker
from path import Path

from dakara_player_vlc.background_loader import BackgroundLoader
from dakara_player_vlc.resources_manager import PATH_BACKGROUNDS
from dakara_player_vlc.audio import get_audio_files
from dakara_player_vlc.text_generator import TextGenerator
from dakara_player_vlc.version import __version__


TRANSITION_BG_NAME = "transition.png"
TRANSITION_TEXT_NAME = "transition.ass"
TRANSITION_DURATION = 2

IDLE_BG_NAME = "idle.png"
IDLE_TEXT_NAME = "idle.ass"
IDLE_DURATION = 300

PLAYER_CLOSING_DURATION = 3


logger = logging.getLogger(__name__)


class MediaPlayer(Worker, ABC):
    player_name = None

    @staticmethod
    @abstractmethod
    def is_available():
        """Indicate if the implementation is available """

    def init_worker(self, config, tempdir):
        self.check_is_available()

        # karaoke parameters
        self.fullscreen = config.get("fullscreen", False)
        self.kara_folder_path = Path(config.get("kara_folder", ""))

        # inner objects
        self.playlist_entry = None
        self.callbacks = {}

        # set durations
        config_durations = config.get("durations") or {}
        self.durations = {
            "idle": IDLE_DURATION,
            "transition": config_durations.get(
                "transition_duration", TRANSITION_DURATION
            ),
        }

        # set text paths
        self.text_paths = {
            "idle": tempdir / IDLE_TEXT_NAME,
            "transition": tempdir / TRANSITION_TEXT_NAME,
        }

        # set text generator
        config_texts = config.get("templates") or {}
        self.text_generator = TextGenerator(config_texts)

        # set background loader
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

        # set default callbacks
        self.set_default_callbacks()

        # call specialized constructor
        self.init_player(config, tempdir)

    def init_player(self, config, tempdir):
        pass

    def load(self):
        # check kara folder
        self.check_kara_folder_path()

        # load text generator
        self.text_generator.load()

        # load backgrounds
        self.background_loader.load()

        self.load_player()

    def load_player(self):
        pass

    @abstractmethod
    def get_timing(self):
        pass

    @abstractmethod
    def get_version(self):
        pass

    @abstractmethod
    def is_playing(self, what):
        pass

    @abstractmethod
    def is_paused(self):
        pass

    @abstractmethod
    def play(self, what):
        pass

    @abstractmethod
    def pause(self, paused):
        pass

    @abstractmethod
    def skip(self):
        pass

    @abstractmethod
    def stop():
        pass

    def set_playlist_entry(self, playlist_entry, autoplay=True):
        file_path = self.kara_folder_path / playlist_entry["song"]["file_path"]

        if not file_path.exists():
            logger.error("File not found '%s'", file_path)
            self.callbacks["error"](playlist_entry["id"], "File not found")
            self.callbacks["could_not_play"](playlist_entry["id"])
            return

        self.playlist_entry = playlist_entry

        self.set_playlist_entry_player(playlist_entry, file_path, autoplay)

    def set_playlist_entry_player(self, playlist_entry, file_path, autoplay):
        return

    def clear_playlist_entry(self):
        self.playlist_entry = None

        self.clear_playlist_entry_player()

    def clear_playlist_entry_player(self):
        return

    def set_callback(self, name, callback):
        self.callbacks[name] = callback

    @staticmethod
    def get_instrumental_file(filepath):
        audio_files = get_audio_files(filepath)

        # accept only one audio file
        if len(audio_files) == 1:
            return audio_files[0]

        # otherwise return None
        return None

    def check_kara_folder_path(self):
        if not self.kara_folder_path.exists():
            raise KaraFolderNotFound(
                'Karaoke folder "{}" does not exist'.format(self.kara_folder_path)
            )

    def check_is_available(self):
        # check the target player is available
        if not self.is_available():
            raise MediaPlayerNotAvailableError(
                "{} is not available".format(self.player_name)
            )

    def set_default_callbacks(self):
        # set dummy callbacks that have to be defined externally
        self.set_callback("started_transition", lambda playlist_entry_id: None)
        self.set_callback("started_song", lambda playlist_entry_id: None)
        self.set_callback("could_not_play", lambda playlist_entry_id: None)
        self.set_callback("finished", lambda playlist_entry_id: None)
        self.set_callback("paused", lambda playlist_entry_id, timing: None)
        self.set_callback("resumed", lambda playlist_entry_id, timing: None)
        self.set_callback("error", lambda playlist_entry_id, message: None)

    def exit_worker(self, exception_type, exception_value, traceback):
        """Exit the worker

        Send a warning after `PLAYER_CLOSING_DURATION` seconds if the worker is
        not closed yet.
        """
        # send a warning within if the player has not stopped already
        timer_stop_player_too_long = Timer(
            PLAYER_CLOSING_DURATION, self.warn_stop_player_too_long
        )
        timer_stop_player_too_long.start()

        # stop player
        self.stop()

        # clear the warning
        timer_stop_player_too_long.cancel()

    @classmethod
    def warn_stop_player_too_long(cls):
        """Notify the user that the player takes too long to stop
        """
        logger.warning("{} takes too long to stop".format(cls.player_name))

    def generate_text(self, what, *args, **kwargs):
        if what == "idle":
            text = self.text_generator.create_idle_text(
                {
                    "notes": [
                        "VLC {}".format(self.get_version()),
                        "Dakara player {}".format(__version__),
                    ]
                },
                *args,
                **kwargs
            )

        elif what == "transition":
            text = self.text_generator.create_idle_text(
                self.playlist_entry, *args, **kwargs
            )

        else:
            raise ValueError("Unexpected action to generate text to: {}".format(what))

        self.text_paths[what].write_text(text, "utf-8")

        return self.text_paths[what]


class KaraFolderNotFound(DakaraError):
    """Error raised when the kara folder cannot be found
    """


class MediaPlayerNotAvailableError(DakaraError):
    """Error raised when trying to use a target player that cannot be found
    """
