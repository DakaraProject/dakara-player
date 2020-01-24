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


class MediaPlayer(Worker):
    """Common operations for media players.

    This class should be subclassed by actual player implementations.

    A media player manages the display of idle/transition screens when playing,
    logging of the messages of the actual player, and provides some accessors and
    mutators to get/set the status of the player.

    After being instanciated, the object must be loaded with `load`.

    Attributes:
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

    def init_worker(self, config, tempdir):
        """Init the worker
        """
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

    def init_player(self, config, tempdir):
        """Init the actual player
        """
        raise NotImplementedError

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

    def load_player(self):
        """Prepare the player instance

        Perform actions with side effects.
        """
        raise NotImplementedError

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
        raise NotImplementedError

    def play_idle_screen(self):
        """Play idle screen
        """
        raise NotImplementedError

    def is_idle(self):
        """Get player idling status

        Returns:
            bool: False when playing a song or a transition screen, True when
                playing idle screen.
        """
        return self.playing_id is None

    def get_playing_id(self):
        """Playlist entry ID getter

        Returns:
            int: current playing ID or None when no song is playing.
        """
        return self.playing_id

    def get_timing(self):
        """Player timing getter

        Returns:
            int: current song timing in seconds if a song is playing or 0 when
                idle or during transition screen.
        """
        raise NotImplementedError

    def is_paused(self):
        """Player pause status getter

        Returns:
            bool: True when playing song is paused.
        """
        raise NotImplementedError

    def set_pause(self, pause):
        """Pause or unpause the player

        Pause playing song when True unpause when False.

        Args:
            pause (bool): flag for pause state requested.
        """
        raise NotImplementedError

    def stop_player(self):
        """Stop playing music
        """
        raise NotImplementedError

    def exit_worker(self, exception_type, exception_value, traceback):
        """Exit the worker
        """
        self.stop_player()


class KaraFolderNotFound(DakaraError):
    """Error raised when the kara folder cannot be found
    """
