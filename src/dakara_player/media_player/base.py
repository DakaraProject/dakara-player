"""Base objects for media players."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from threading import Timer

from dakara_base.directory import directories
from dakara_base.exceptions import DakaraError
from dakara_base.safe_workers import Worker

from dakara_player.background import BackgroundLoader
from dakara_player.text import TextGenerator
from dakara_player.version import __version__

TRANSITION_BG_NAME = "transition.png"
TRANSITION_TEXT_NAME = "transition.ass"
TRANSITION_DURATION = 2

IDLE_BG_NAME = "idle.png"
IDLE_TEXT_NAME = "idle.ass"
IDLE_DURATION = 300

PLAYER_CLOSING_DURATION = 3

REWIND_FAST_FORWARD_DURATION = 10


logger = logging.getLogger(__name__)


class MediaPlayer(Worker, ABC):
    """Abstract class to manipulate a media player.

    The class can be used as a context manager that closes the media player
    automatically on exit.

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
        player_name (str): Name of the media player.
        fullscreen (bool): If `True`, the media player will be fullscreen.
        kara_folder_path (pathlib.Path): Path to the karaoke folder.
        entry (MediaPlayerEntry): Entry object.
        callbacks (dict): High level callbacks associated with the media
            player.
        warn_long_exit (bool): If `True`, display a warning message if the media
            player takes too long to stop.
        durations (dict of int): Duration of the different screens in seconds.
        text_paths (dict of pathlib.Path): Path of the different text screens.
        text_generator (dakara_player.text.TextGenerator): Text
            generator instance.
        background_loader
        (dakara_player.background.BackgroundLoader): Background
            loader instance.
    """

    player_name = None

    @staticmethod
    @abstractmethod
    def is_available():
        """Indicate if the implementation is available.

        Must be overriden.

        Returns:
            bool: `True` if the media player is useable.
        """

    def init_worker(self, config, tempdir, warn_long_exit=True):
        """Initialize the base objects of the media player.

        Actions performed in this method should not have any side effects
        (query file system, etc.).

        Args:
            config (dict): Dictionary of configuration.
            tempdir (pathlib.Path): Path of the temporary directory.
            warn_long_exit (bool): If `True`, the class will display a warning
                message if the media player takes too long to stop.
        """
        self.check_is_available()

        # karaoke parameters
        self.fullscreen = config.get("fullscreen", False)
        self.kara_folder_path = Path(config.get("kara_folder", ""))

        # inner objects
        self.entry = None
        self.callbacks = {}
        self.warn_long_exit = warn_long_exit

        # set durations
        config_durations = config.get("durations") or {}
        self.durations = {
            "idle": IDLE_DURATION,
            "transition": config_durations.get(
                "transition_duration", TRANSITION_DURATION
            ),
            "rewind_fast_forward": config_durations.get(
                "rewind_fast_forward_duration", REWIND_FAST_FORWARD_DURATION
            ),
        }

        # set text paths
        self.text_paths = {
            "idle": tempdir / IDLE_TEXT_NAME,
            "transition": tempdir / TRANSITION_TEXT_NAME,
        }

        # set text generator
        config_texts = config.get("templates") or {}
        self.text_generator = TextGenerator(
            package="dakara_player.resources.templates",
            directory=directories.user_data_path / "player" / "templates",
            filenames={
                "transition": config_texts.get(
                    "transition_template_name", TRANSITION_TEXT_NAME
                ),
                "idle": config_texts.get("idle_template_name", IDLE_TEXT_NAME),
            },
        )

        # set background loader
        config_backgrounds = config.get("backgrounds") or {}
        self.background_loader = BackgroundLoader(
            destination=tempdir,
            package="dakara_player.resources.backgrounds",
            directory=directories.user_data_path / "player" / "backgrounds",
            filenames={
                "transition": config_backgrounds.get(
                    "transition_background_name", TRANSITION_BG_NAME
                ),
                "idle": config_backgrounds.get("idle_background_name", IDLE_BG_NAME),
            },
        )

        # set default callbacks
        self.set_default_callbacks()

        # call specialized constructor
        self.init_player(config, tempdir)

    def init_player(self, config, tempdir):
        """Initialize the objects of the specific media player.

        Actions performed in this method should not have any side effects
        (query file system, etc.).

        Can be overriden.

        Args:
            config (dict): Dictionary of configuration.
            tempdir (pathlib.Path): Path of the temporary directory.
        """

    def load(self):
        """Perform base actions with side effects for media player initialization."""
        # check kara folder
        self.check_kara_folder_path()

        # load text generator
        self.text_generator.load()

        # load backgrounds
        self.background_loader.load()

        self.load_player()

    def load_player(self):
        """Perform actions with side effects for specialized media player
        initialization.

        Can be overriden.
        """

    @abstractmethod
    def get_timing(self):
        """Get media player timing.

        Must be overriden.

        Returns:
            int: Current song timing in seconds if a song is playing, or 0 when
                idle or during transition screen.
        """

    @staticmethod
    @abstractmethod
    def get_version():
        """Get media player version.

        Must be overriden.

        Returns:
            packaging.version.Version: Parsed version of the media player.
        """

    @classmethod
    def get_version_str(cls):
        """Get media player formatted version.

        Returns:
            str: Formatted version of the media player. If the version
            cannot be obtained, display `unknown version`.
        """
        try:
            return str(cls.get_version())

        except VersionNotFoundError:
            return "unknown version"

    @abstractmethod
    def is_playing(self):
        """Query if the media player is playing something.

        Must be overriden.

        Returns:
            bool: `True` if the media player is playing something.
        """

    @abstractmethod
    def is_paused(self):
        """Query if the media player is paused.

        Must be overriden.

        Returns:
            bool: `True` if the media player is paused.
        """

    @abstractmethod
    def is_playing_this(self, what):
        """Query if the media player is playing the requested media type.

        Must be overriden.

        Args:
            what (str): Tell if the media player current track is of the
                requested type, but not if it is actually playing it (it can be
                in pause).

        Returns:
            bool: `True` if the media player is playing the requested type.
        """

    @abstractmethod
    def play(self, what):
        """Request the media player to play something.

        No preparation should be done by this function, i.e. the media track
        should have been prepared already by `set_playlist_entry`.

        Must be overriden.

        Args:
            what (str): What media to play.
        """

    @abstractmethod
    def pause(self):
        """Request the media player to pause.

        Can only work on transition screens or songs. Pausing should have no
        effect if the media player is already paused.

        Must be overriden.
        """

    @abstractmethod
    def resume(self):
        """Request the media player to resume playing.

        Can only work on transition screens or songs. Resuming should have no
        effect if the media player is already playing.

        Must be overriden.
        """

    @abstractmethod
    def restart(self):
        """Request to restart the current media.

        Can only work on songs.

        Must be overriden.
        """

    @abstractmethod
    def skip(self, no_callback=False):
        """Request to skip the current media.

        Can only work on transition screens or songs. The media player should
        continue playing, but media has to be considered already finished.

        Args:
            no_callback (bool): If `True`, no callback to signal the song has
                finished will be executed.

        Must be overriden.
        """

    @abstractmethod
    def rewind(self):
        """Request to rewind a few seconds the media.

        Can only work on songs. It cannot rewind before the beginning of the media.

        Must be overriden.
        """

    def fast_forward(self):
        """Request to fast forward a few seconds the media.

        Can only work on songs. It cannot advance passed the end of the media.

        Must be overriden.
        """

    @abstractmethod
    def stop_player(self):
        """Request to stop the media player.

        Must be overriden.
        """

    def set_playlist_entry(self, playlist_entry, autoplay=True):
        """Prepare playlist entry base data to be played.

        Check if the song file exists, otherwise consider the song cannot be
        played.

        Args:
            playlist_entry (dict): Playlist entry object.
            autoplay (bool): If `True`, start to play transition screen as soon
                as possible.
        """
        entry = MediaPlayerEntry(self.kara_folder_path, playlist_entry)
        entry.load(self.background_loader.backgrounds, self.durations, self.text_paths)

        # XXX should be done later
        if not entry.items["song"].path.is_file():
            logger.error("File not found '%s'", entry.items["song"].path)
            self.callbacks["error"](entry.id, "File not found")
            self.callbacks["could_not_play"](entry.id)
            return

        self.entry = entry

        self.set_playlist_entry_player(autoplay)

    @abstractmethod
    def set_playlist_entry_player(self, autoplay):
        """Prepare playlist entry data to be played.

        Prepare all media objects, subtitles, etc. for being played, for the
        transition screen and the song. Such data should be stored on a
        dedicated object, like `playlist_entry_data`.

        Must be overriden.

        Args:
            autoplay (bool): If `True`, start to play transition screen as soon
                as possible (i.e. as soon as the transition screen media is
                ready). The song media is prepared when the transition screen
                is playing.
        """

    def clear_playlist_entry(self):
        """Clean playlist entry base data."""
        logger.debug("Clearing internal memory")
        self.entry = None

    def set_callback(self, name, callback):
        """Set callback to the media player.

        Args:
            name (str): Name of the callback.
            callback (function): Callback.
        """
        self.callbacks[name] = callback

    def check_kara_folder_path(self):
        """Check if the karaoke folder exists."""
        if not self.kara_folder_path.exists():
            raise KaraFolderNotFound(
                'Karaoke folder "{}" does not exist'.format(self.kara_folder_path)
            )

    def check_is_available(self):
        """Check if the media player is installed and useable."""
        # check the target player is available
        if not self.is_available():
            raise MediaPlayerNotAvailableError(
                "{} is not available".format(self.player_name)
            )

    def set_default_callbacks(self):
        """Set dummy callbacks that have to be defined externally."""
        self.set_callback("started_transition", lambda playlist_entry_id: None)
        self.set_callback("started_song", lambda playlist_entry_id: None)
        self.set_callback("could_not_play", lambda playlist_entry_id: None)
        self.set_callback("finished", lambda playlist_entry_id: None)
        self.set_callback("paused", lambda playlist_entry_id, timing: None)
        self.set_callback("resumed", lambda playlist_entry_id, timing: None)
        self.set_callback("error", lambda playlist_entry_id, message: None)
        self.set_callback("updated_timing", lambda playlist_entry_id, timing: None)

    def exit_worker(self, *args, **kwargs):
        """Exit the worker.

        If `warn_long_exit` was `True` during initialization, send a warning
        after `PLAYER_CLOSING_DURATION` seconds if the worker is not closed
        yet.
        """
        if self.warn_long_exit:
            # send a warning within if the player has not stopped already
            timer_stop_player_too_long = Timer(
                PLAYER_CLOSING_DURATION, self.warn_stop_player_too_long
            )
            timer_stop_player_too_long.start()

        # stop player
        self.stop_player()

        if self.warn_long_exit:
            # clear the warning
            timer_stop_player_too_long.cancel()

    @classmethod
    def warn_stop_player_too_long(cls):
        """Notify the user that the player takes too long to stop."""
        logger.warning("{} takes too long to stop".format(cls.player_name))

    def generate_text(self, what, **kwargs):
        """Generate text screens for the requested action.

        Args:
            what (str): What text screen to generate.
            kwargs (dict): Extra arguments passed to the different text
                screens. For transition screen, accepts the `fade_in` boolean,
                which is `True` by default. If `False`, the transition screen will
                have no fade in effect.

        Returns:
            pathlib.Path: Path of the text screen.

        Raises:
            ValueError: If the type of screen to generate is unknown.
        """
        if what == "idle":
            text = self.text_generator.get_text(
                "idle",
                {
                    "notes": [
                        "{} {}".format(self.player_name, self.get_version_str()),
                        "Dakara player {}".format(__version__),
                    ]
                },
            )

        elif what == "transition":
            text = self.text_generator.get_text(
                "transition",
                {
                    "playlist_entry": self.entry.playlist_entry,
                    "fade_in": kwargs.get("fade_in", True),
                },
            )

        else:
            raise ValueError("Unexpected action to generate text for: {}".format(what))

        self.text_paths[what].write_text(text, encoding="utf-8")

        return self.text_paths[what]


def on_playing_this(what_list, default_return=None):
    """Decorator for methods that necessitate the player to be playing
    something specifically.

    Args:
        what_list (list): List of possible states.
        default_return (any): Value to return if the state is different.
            Default to `None`.
    """

    def decorator(function):
        @wraps(function)
        def wrap(self, *args, **kwargs):
            for what in what_list:
                if self.is_playing_this(what):
                    break

            else:
                return default_return

            return function(self, *args, **kwargs)

        return wrap

    return decorator


@dataclass
class MediaPlayerItem:
    """Media item. Anything the player is supposed to play.

    Attributes:
        path (pathlib.Path): Absolute path of the file to play.
    """

    path: Path


@dataclass
class MediaPlayerItemTransition(MediaPlayerItem):
    """Media item for transitions.

    Attributes:
        subtitle_path (pathlib.Path): Absolute path of the screen text file.
        duration (int): Duration of the transition.
    """

    subtitle_path: Path
    duration: int


@dataclass
class MediaPlayerItemSong(MediaPlayerItem):
    """Media item for songs.

    Attributes:
        instrumental_track (int): If provided, number of the audio track to use
            for instrumental version.
        instrumental_path (pathlib.Path): If provided, absolute path to the
            audio file to use for instrumental version.
    """

    instrumental_track: int | None = None
    instrumental_path: Path | None = None


@dataclass
class MediaPlayerEntry:
    """Player-agnostic representation of items to play associated with a playlist entry.

    This class leverages all the logic of manipulating media files, so as to
    let media player implementations only focus on their own logic.

    Attributes:
        kara_folder_path (pathlib.Path): Absolute path to the karaoke directory.
        playlist_entry (dict): Playlist entry as received from the server.
        items (dict): Items associated with the playlist entry.
    """

    kara_folder_path: Path
    playlist_entry: dict
    items: dict[str, MediaPlayerItem] = field(init=False, default_factory=dict)

    def load(
        self,
        backgrounds: dict[str, Path],
        durations: dict[str, int],
        text_paths: dict[str, Path],
    ) -> None:
        """Populate items, which may cause side-effects.

        Args:
            backgrounds (dict): Background file absolute paths.
            durations (dict): Durations.
            text_paths (dict): Text screen file absolute paths.
        """
        self.items = {
            "transition": self.get_transition(backgrounds, durations, text_paths),
            "song": self.get_song(),
        }

    @property
    def id(self) -> int:
        """int: Shorthand to playlist entry ID."""
        return self.playlist_entry["id"]

    @property
    def title(self) -> str:
        """str: Shorthand to playlist entry song title."""
        return self.playlist_entry["song"]["title"]

    def is_loaded(self) -> bool:
        """Indicate if the `load` method was called."""
        return len(self.items.keys()) != 0

    def get_transition(
        self,
        backgrounds: dict[str, Path],
        durations: dict[str, int],
        text_paths: dict[str, Path],
    ) -> MediaPlayerItemTransition:
        """Create a transition item.

        Args:
            backgrounds (dict): Background file absolute paths.
            durations (dict): Durations.
            text_paths (dict): Text screen file absolute paths.

        Returns:
            MediaPlayerItemTransition: Transition item.
        """
        return MediaPlayerItemTransition(
            path=backgrounds["transition"],
            subtitle_path=text_paths["transition"],
            duration=durations["transition"],
        )

    def get_song(self) -> MediaPlayerItemSong:
        """Create a song item.

        Take care of instrumental version.

        Returns:
            MediaPlayerItemSong: Song item.
        """
        song = MediaPlayerItemSong(
            path=self.kara_folder_path / self.playlist_entry["song"]["file_path"]
        )
        self.set_instrumental(song)

        return song

    def set_instrumental(self, song: MediaPlayerItemSong) -> None:
        """Set instrumental track or file in media.

        If the playlist entry requires the instrumental version, first look for
        the instrumental file, then for the instrumental track.

        Args:
            song (MediaPlayerItemSong): Song tiem to modify.
        """
        if self.playlist_entry["use_instrumental"]:
            logger.info("Requesting instrumental version of file '%s'", song.path)

            # use instrumental file
            if instrumental_file_path := self.get_instrumental_file_path(song):
                song.instrumental_path = instrumental_file_path
                return

            # use instrumental track
            if instrumental_track_id := self.get_instrumental_track_id():
                song.instrumental_track = instrumental_track_id
                return

            # display a warning if nothing worked out
            logger.warning("No instrumental version available of file '%s'", song.path)

    def get_instrumental_file_path(self, song: MediaPlayerItemSong) -> Path | None:
        """Retreive the instrumental file of a song.

        Args:
            song (MediaPlayerItemSong): Song item.

        Returs:
            pathlib.Path: Absolute path to the audio file, provided that the
            song has an insrumental file and that this file exists.
        """
        # attempt to add instrumental file
        if audio_file := self.playlist_entry["song"]["instrumental_file"]:
            # get absolute path from song file path
            audio_path = song.path.parent / audio_file

            logger.info(
                "Requesting to play instrumental file '%s'",
                audio_path,
            )

            if not audio_path.exists():
                logger.error(
                    "Unable to find requested instrumental file '%s'", audio_path
                )
                return None

            return audio_path

        return None

    def get_instrumental_track_id(self) -> int | None:
        """Retreive the instrumental track of a song.

        Returs:
            int: Audio track number of the instrumental track, provided that
            the song has one.
        """
        # attempt to add instrumental track
        if audio_id := self.playlist_entry["song"]["instrumental_track"]:
            logger.info("Requesting to play instrumental track %i", audio_id)

            return audio_id

        return None


class KaraFolderNotFound(DakaraError):
    """Error raised when the kara folder cannot be found."""


class MediaPlayerNotAvailableError(DakaraError):
    """Error raised when trying to use a target player that cannot be found."""


class InvalidStateError(RuntimeError):
    """Error raised when the state of the player is invalid."""


class VersionNotFoundError(Exception):
    """Error raised when the version of the player cannot be found."""
