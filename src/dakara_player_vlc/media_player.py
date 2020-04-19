import logging
from abc import ABC, abstractmethod
from threading import Timer

from dakara_base.exceptions import DakaraError
from dakara_base.safe_workers import Worker
from path import Path

from dakara_player_vlc.background_loader import BackgroundLoader
from dakara_player_vlc.resources_manager import PATH_BACKGROUNDS
from dakara_player_vlc.text_generator import TextGenerator


TRANSITION_BG_NAME = "transition.png"
TRANSITION_TEXT_NAME = "transition.ass"
TRANSITION_DURATION = 2

IDLE_BG_NAME = "idle.png"
IDLE_TEXT_NAME = "idle.ass"
IDLE_DURATION = 300

PLAYER_CLOSING_DURATION = 3

logger = logging.getLogger(__name__)


class MediaPlayerNotAvailableError(DakaraError):
    """Error raised when trying to use a target player that cannot be found
    """


class MediaPlayer(Worker, ABC):
    """Common operations for media players.

    This class should be subclassed by actual player implementations.

    A media player manages the display of idle/transition screens when playing,
    logging of the messages of the actual player, and provides some accessors and
    mutators to get/set the status of the player.

    Before being instanciated, one should check if the target player is
    available with the static method `is_available`. If the return value is
    False, the class cannot be instanciated. After instanciation, the object
    must be loaded with `load` before being used.

    Attributes:
        player_name (str): Name of the target player.
        player_not_available_error_class (type): Exception raised if the target
            player cannot be found.
        text_generator (TextGenerator): generator of on-screen texts.
        callbacks (dict): dictionary of external callbacks that are run by this player
            on certain events. They must be set with `set_callback`.
        durations (dict): dictionary of durations for screens.
        fullscreen (bool): is the player running fullscreen flag.
        kara_folder_path (path.Path): path to the root karaoke folder containing
            songs.
        playing_id (int): playlist entry id of the current song if no songs are
            playing, its value is None.
        in_transition (bool): flag set to True is a transition screen is
            playing.

    Args:
        stop (Event): event to stop the program.
        errors (Queue): queue of errors.
        config (dict): configuration.
        tempdir (path.Path): path to a temporary directory.
    """

    player_name = None
    player_not_available_error_class = MediaPlayerNotAvailableError

    @staticmethod
    @abstractmethod
    def is_available():
        """Check if the target player can be used

        Returns:
            bool: True if the class can be instanciated.
        """

    def init_worker(self, config, tempdir):
        """Init the worker
        """
        # check the target player is available
        if not self.is_available():
            raise self.player_not_available_error_class(
                "{} is not available".format(self.player_name)
            )

        # callbacks
        self.callbacks = {}

        # karaoke parameters
        self.fullscreen = config.get("fullscreen", False)
        self.kara_folder_path = Path(config.get("kara_folder", ""))

        # set durations
        config_durations = config.get("durations") or {}
        self.durations = {
            "transition": config_durations.get(
                "transition_duration", TRANSITION_DURATION
            ),
            "idle": IDLE_DURATION,
        }

        # set text generator
        config_texts = config.get("templates") or {}
        self.text_generator = TextGenerator(config_texts)

        # set background loader
        # we need to make some adaptations here
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

        # set path of ASS files for text screens
        self.idle_text_path = tempdir / IDLE_TEXT_NAME
        self.transition_text_path = tempdir / TRANSITION_TEXT_NAME

        # playlist entry id of the current song
        # if no songs are playing, its value is None
        self.playing_id = None

        # flag set to True is a transition screen is playing
        self.in_transition = False

        # set default callbacks
        self.set_default_callbacks()

        self.init_player(config, tempdir)

    @abstractmethod
    def init_player(self, config, tempdir):
        """Init the actual player
        """

    def load(self):
        """Prepare the instance

        Perform actions with side effects.
        """
        # check kara folder
        self.check_kara_folder_path()

        # load text generator
        self.text_generator.load()

        # load backgrounds
        self.background_loader.load()

        self.load_player()

    @abstractmethod
    def load_player(self):
        """Prepare the player instance

        Perform actions with side effects.
        """

    def check_kara_folder_path(self):
        """Check the kara folder is valid
        """
        if not self.kara_folder_path.exists():
            raise KaraFolderNotFound(
                'Karaoke folder "{}" does not exist'.format(self.kara_folder_path)
            )

    def set_default_callbacks(self):
        """Set all the default callbacks
        """

        # set dummy callbacks that have to be defined externally
        self.set_callback("started_transition", lambda playlist_entry_id: None)
        self.set_callback("started_song", lambda playlist_entry_id: None)
        self.set_callback("could_not_play", lambda playlist_entry_id: None)
        self.set_callback("finished", lambda playlist_entry_id: None)
        self.set_callback("paused", lambda playlist_entry_id, timing: None)
        self.set_callback("resumed", lambda playlist_entry_id, timing: None)
        self.set_callback("error", lambda playlist_entry_id, message: None)

    def set_callback(self, name, callback):
        """Assign an arbitrary callback

        Callback is added to the `callbacks` dictionary.

        Args:
            name (str): name of the callback in the `callbacks` attribute.
            callback (function): function to assign.
        """
        self.callbacks[name] = callback

    @abstractmethod
    def play_playlist_entry(self, playlist_entry):
        """Play the specified playlist entry

        Prepare the media containing the song to play and store it. Add a
        transition screen and play it first. When the transition ends, the song
        will be played.

        Args:
            playlist_entry (dict): dictionnary containing at least `id` and
                `song` attributes. `song` is a dictionary containing at least
                the key `file_path`.
        """

    def handle_file_not_found(self, playlist_entry_file_path, playlist_entry_id):
        """Call all the necessary callbacks when a file does not exist.

        Args:
            playlist_entry_file_path (path.Path): Path of the not found file.
            playlist_entry_id (int): ID of the associated playlist entry.
        """
        logger.error("File not found '%s'", playlist_entry_file_path)
        self.callbacks["could_not_play"](playlist_entry_id)
        self.callbacks["error"](
            playlist_entry_id, "File not found '{}'".format(playlist_entry_file_path)
        )

    @abstractmethod
    def play_idle_screen(self):
        """Play idle screen
        """

    def is_idle(self):
        """Get player idling status

        Returns:
            bool: False when playing a song or a transition screen, True when
                playing idle screen.
        """
        return self.playing_id is None

    @abstractmethod
    def get_timing(self):
        """Player timing getter

        Returns:
            int: current song timing in seconds if a song is playing or 0 when
                idle or during transition screen.
        """

    @abstractmethod
    def is_paused(self):
        """Player pause status getter

        Returns:
            bool: True when playing song is paused.
        """

    @abstractmethod
    def set_pause(self, pause):
        """Pause or unpause the player

        Pause playing song when True unpause when False.

        Args:
            pause (bool): flag for pause state requested.
        """

    @abstractmethod
    def stop_player(self):
        """Stop playing music
        """

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
        self.stop_player()

        # clear the warning
        timer_stop_player_too_long.cancel()

    @classmethod
    def warn_stop_player_too_long(cls):
        """Notify the user that the player takes too long to stop
        """
        logger.warning("{} takes too long to stop".format(cls.player_name))


class KaraFolderNotFound(DakaraError):
    """Error raised when the kara folder cannot be found
    """
