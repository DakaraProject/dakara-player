import logging
import re
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from json import dumps, loads
from pathlib import Path
from queue import Queue
from threading import Event
from time import sleep
from unittest import TestCase, skipIf
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from dakara_base.directory import PlatformDirs
from packaging.version import parse

from dakara_player.media_player.base import (
    InvalidStateError,
    KaraFolderNotFound,
    MediaPlayerEntry,
    VersionNotFoundError,
    on_playing_this,
)
from dakara_player.media_player.vlc import (
    MediaPlayerVlc,
    UnavailableInstanceError,
    UnexpectedInstanceParameterError,
    VlcTooOldError,
    get_instance,
    get_metadata,
    get_song_media,
    get_transition_media,
    set_metadata,
    update_metadata,
)
from dakara_player.text import TextGenerator
from dakara_player.window import DummyWindowManager, WindowManager

try:
    import vlc

except (ImportError, OSError):
    from dakara_player.media_player import vlc_dummy as vlc

from tests.utils import assert_no_errors, get_temp_dir


class BaseTestCase(TestCase):
    """Base test case to provid a mocked instance of MediaPlayerVlc."""

    def setUp(self):
        # create playlist entry ID
        self.id = 42

        # create playlist entry file path
        self.song_file_path = get_temp_dir() / "file"

        # create playlist entry
        self.playlist_entry = {
            "id": self.id,
            "song": {
                "title": "Song title",
                "file_path": "file",
                "instrumental_file": None,
                "instrumental_track": None,
            },
            "owner": "me",
            "use_instrumental": False,
        }

        self.entry = MediaPlayerEntry(get_temp_dir(), self.playlist_entry)

        self.media_song = vlc.Media(self.song_file_path.as_uri())
        self.media_transition = vlc.Media((get_temp_dir() / "transition.png").as_uri())
        self.media_idle = vlc.Media((get_temp_dir() / "idle.png").as_uri())

    @contextmanager
    def get_instance(
        self,
        config=None,
        tempdir=None,
    ):
        """Get a heavily mocked instance of MediaPlayerVlc.

        Args:
            config (dict): Configuration passed to the constructor.
            tempdir (pathlib.Path): Path to temporary directory.

        Yields:
            tuple: Contains the following elements:
                MediaPlayerVlc: Instance;
                tuple: Contains the mocked objects:
                    unittest.mock.MagicMock: VLC Instance object.
                    unittest.mock.MagicMock: BackgroundLoader object.
                    unittest.mock.MagicMock: TextGenerator object.
                tuple: Contains the mocked classes:
                    unittest.mock.MagicMock: VLC Instance class.
                    unittest.mock.MagicMock: BackgroundLoader class.
                    unittest.mock.MagicMock: TextGenerator class.
        """
        config = config or {"kara_folder": str(get_temp_dir())}

        with ExitStack() as stack:
            if vlc is None:
                mocked_vlc = stack.enter_context(
                    patch("dakara_player.media_player.vlc.vlc")
                )
                mocked_instance_class = mocked_vlc.Instance
            else:
                mocked_instance_class = stack.enter_context(
                    patch("dakara_player.media_player.vlc.vlc.Instance")
                )

            mocked_background_loader_class = stack.enter_context(
                patch("dakara_player.media_player.base.BackgroundLoader")
            )

            mocked_text_generator_class = stack.enter_context(
                patch("dakara_player.media_player.base.TextGenerator")
            )

            stack.enter_context(patch.object(MediaPlayerVlc, "check_is_available"))

            if tempdir is None:
                tempdir = Path("temp")

            yield (
                MediaPlayerVlc(Event(), Queue(), config, tempdir),
                (
                    mocked_instance_class.return_value,
                    mocked_background_loader_class.return_value,
                    mocked_text_generator_class.return_value,
                ),
                (
                    mocked_instance_class,
                    mocked_background_loader_class,
                    mocked_text_generator_class,
                ),
            )


@patch("dakara_player.media_player.base.TRANSITION_DURATION", 10)
@patch("dakara_player.media_player.base.IDLE_DURATION", 20)
class MediaPlayerVlcTestCase(BaseTestCase):
    """Test the VLC player class unitary."""

    def set_playlist_entry(self, vlc_player):
        """Set a playlist entry and make the player play it.

        Args:
            vlc_player (MediaPlayerVlc): Instance of the VLC player.
            started (bool): If True, make the player play the song.
        """
        vlc_player.entry = self.entry
        vlc_player.entry.load(
            {"transition": get_temp_dir() / "transition.png"},
            {"transition": 2},
            {"transition": get_temp_dir() / "transition.ass"},
        )

    def set_media(
        self, vlc_player: MediaPlayerVlc, what: str | None = None, started: bool = True
    ) -> vlc.Media:
        if what == "idle":
            set_metadata(self.media_idle, {"started": started, "type": "idle"})
            vlc_player.player.get_media.return_value = self.media_idle
            return self.media_idle

        if what == "transition":
            set_metadata(
                self.media_transition, {"started": started, "type": "transition"}
            )
            vlc_player.player.get_media.return_value = self.media_transition
            return self.media_transition

        # default to song
        set_metadata(
            self.media_song, {"started": started, "track_id_audio": 0, "type": "song"}
        )
        vlc_player.player.get_media.return_value = self.media_song
        return self.media_song

    def test_init_window(self):
        """Test to use default or custom window."""
        # default window
        with self.get_instance(
            {"kara_folder": str(get_temp_dir()), "vlc": {"use_default_window": True}}
        ) as (vlc_player, _, _):
            self.assertIsInstance(vlc_player.window, DummyWindowManager)

        # custom window
        with self.get_instance() as (vlc_player, _, _):
            self.assertIsInstance(vlc_player.window, WindowManager)

    def test_set_callback(self):
        """Test the assignation of a callback."""
        with self.get_instance() as (vlc_player, _, _):
            # create a callback function
            callback = MagicMock()

            # pre assert the callback is not set yet
            self.assertIsNot(vlc_player.callbacks.get("test"), callback)

            # call the method
            vlc_player.set_callback("test", callback)

            # post assert the callback is now set
            self.assertIs(vlc_player.callbacks.get("test"), callback)

    @skipIf(vlc is None, "VLC not installed")
    def test_set_vlc_callback(self):
        """Test the assignation of a callback to a VLC event.

        We have also to mock the event manager method because there is no way
        with the VLC library to know which callback is associated to a given
        event.
        """
        with self.get_instance() as (vlc_player, _, _):
            # patch the event creator
            vlc_player.event_manager.event_attach = MagicMock()

            # create a callback function
            callback = MagicMock()

            # pre assert the callback is not set yet
            self.assertIsNot(
                vlc_player.vlc_callbacks.get(vlc.EventType.MediaPlayerEndReached),
                callback,
            )

            # call the method
            vlc_player.set_vlc_callback(vlc.EventType.MediaPlayerEndReached, callback)

            # assert the callback is now set
            self.assertIs(
                vlc_player.vlc_callbacks.get(vlc.EventType.MediaPlayerEndReached),
                callback,
            )

            # assert the event manager got the right arguments
            vlc_player.event_manager.event_attach.assert_called_with(
                vlc.EventType.MediaPlayerEndReached, callback
            )

    @skipIf(vlc is None, "VLC not installed")
    def test_vlc_unavailable(self):
        """Test that is_available returns False when vlc.Instance raises a NameError."""
        with patch.object(vlc, "Instance", side_effect=NameError()):
            self.assertFalse(MediaPlayerVlc.is_available())

    @patch("dakara_player.media_player.vlc.vlc.libvlc_get_version")
    def test_get_version_long_4_digits(self, mocked_libvlc_get_version):
        """Test to get the VLC version when it is long and contains 4 digits."""
        # mock the version of VLC
        mocked_libvlc_get_version.return_value = b"3.0.11.1 Vetinari"

        # call the method
        version = MediaPlayerVlc.get_version()

        # assert the result
        self.assertEqual(version, parse("3.0.11.1"))

    @patch("dakara_player.media_player.vlc.vlc.libvlc_get_version")
    def test_get_version_long(self, mocked_libvlc_get_version):
        """Test to get the VLC version when it is long."""
        # mock the version of VLC
        mocked_libvlc_get_version.return_value = b"3.0.11 Vetinari"

        # call the method
        version = MediaPlayerVlc.get_version()

        # assert the result
        self.assertEqual(version, parse("3.0.11"))

    @patch("dakara_player.media_player.vlc.vlc.libvlc_get_version")
    def test_get_version_not_found(self, mocked_libvlc_get_version):
        """Test to get the VLC version when it is not available."""
        # mock the version of VLC
        mocked_libvlc_get_version.return_value = b"none"

        # call the method
        with self.assertRaisesRegex(VersionNotFoundError, "Unable to get VLC version"):
            MediaPlayerVlc.get_version()

    @patch.object(MediaPlayerVlc, "get_version")
    def test_get_version_str(self, mocked_get_version):
        """Test to get the VLC version as a string."""
        # mock the version of VLC
        mocked_get_version.return_value = parse("3.0.11")

        # call the method
        version_str = MediaPlayerVlc.get_version_str()

        # assert the result
        self.assertEqual(version_str, "3.0.11")

    @patch.object(MediaPlayerVlc, "get_version")
    def test_get_version_str_not_found(self, mocked_get_version):
        """Test to get the VLC version as a string when it is not
        available."""
        # mock the version of VLC
        mocked_get_version.side_effect = VersionNotFoundError(
            "Unable to get VLC version"
        )

        # call the method
        self.assertEqual(MediaPlayerVlc.get_version_str(), "unknown version")

    @patch.object(MediaPlayerVlc, "get_version")
    def test_check_version(self, mocked_get_version):
        """Test to check recent enough version VLC."""
        with self.get_instance() as (vlc_player, _, _):
            # mock the version of VLC
            mocked_get_version.return_value = parse("3.0.0")

            # call the method
            vlc_player.check_version()

    @patch.object(MediaPlayerVlc, "get_version")
    def test_check_version_old(self, mocked_get_version):
        """Test to check old version of VLC."""
        with self.get_instance() as (vlc_player, _, _):
            # mock the version of VLC
            mocked_get_version.return_value = parse("2.0.0")

            # call the method
            with self.assertRaisesRegex(VlcTooOldError, "VLC is too old"):
                vlc_player.check_version()

    @patch.object(MediaPlayerVlc, "get_version")
    def test_check_version_problem(self, mocked_get_version):
        """Test to check known problematic version of VLC."""
        with self.get_instance() as (vlc_player, _, _):
            versions = ["3.0.13", "3.0.14", "3.0.15", "3.0.16"]

            for version in versions:
                # mock the version of VLC
                mocked_get_version.return_value = parse(version)

                # call the method
                with self.assertLogs(
                    "dakara_player.media_player.vlc", "WARNING"
                ) as logger:
                    vlc_player.check_version()

                self.assertListEqual(
                    logger.output,
                    [
                        "WARNING:dakara_player.media_player.vlc:This version of VLC "
                        "is known to not work with Dakara player"
                    ],
                )

    @patch.object(Path, "exists")
    def test_check_kara_folder_path(self, mocked_exists):
        """Test to check if the kara folder exists."""
        with self.get_instance() as (vlc_player, _, _):
            # pretend the directory exists
            mocked_exists.return_value = True

            # call the method
            vlc_player.check_kara_folder_path()

            # assert the call
            mocked_exists.assert_called_with()

    @patch.object(Path, "exists")
    def test_check_kara_folder_path_does_not_exist(self, mocked_exists):
        """Test to check if the kara folder does not exist."""
        with self.get_instance() as (vlc_player, _, _):
            # pretend the directory does not exist
            mocked_exists.return_value = False

            # call the method
            with self.assertRaisesRegex(
                KaraFolderNotFound,
                'Karaoke folder "{}" does not exist'.format(
                    re.escape(str(get_temp_dir()))
                ),
            ):
                vlc_player.check_kara_folder_path()

    @patch.object(WindowManager, "get_id")
    @patch.object(WindowManager, "open")
    @patch.object(MediaPlayerVlc, "check_kara_folder_path")
    @patch.object(MediaPlayerVlc, "check_version")
    @patch.object(MediaPlayerVlc, "set_vlc_default_callbacks")
    @patch.object(MediaPlayerVlc, "get_version")
    def test_load(
        self,
        mocked_get_version,
        mocked_set_vlc_default_callback,
        mocked_check_version,
        mocked_check_kara_folder_path,
        mocked_open,
        mocked_get_id,
    ):
        """Test to load the instance."""
        with self.get_instance() as (
            vlc_player,
            (_, mocked_background_loader, mocked_text_generator),
            _,
        ):
            # setup mocks
            mocked_get_version.return_value = "3.0.0 NoName"

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "INFO") as logger:
                vlc_player.load()

            # assert the calls
            mocked_check_kara_folder_path.assert_called_with()
            mocked_text_generator.load.assert_called_with()
            mocked_background_loader.load.assert_called_with()
            mocked_check_version.assert_called_with()
            mocked_set_vlc_default_callback.assert_called_with()
            mocked_open.assert_called_with()
            mocked_get_id.assert_called_with()

            # assert logs
            self.assertListEqual(
                logger.output, ["INFO:dakara_player.media_player.vlc:VLC 3.0.0 NoName"]
            )

    @patch.object(Path, "is_file")
    def test_set_playlist_entry_error_file(self, mocked_is_file):
        """Test to set a playlist entry that does not exist."""
        with self.get_instance() as (vlc_player, _, _):
            # mock the system call
            mocked_is_file.return_value = False

            # mock the callbacks
            vlc_player.set_callback("could_not_play", MagicMock())
            vlc_player.set_callback("error", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.entry)

            # call the method
            with self.assertLogs("dakara_player.media_player.base", "DEBUG") as logger:
                vlc_player.set_playlist_entry(self.playlist_entry, autoplay=False)

            # call assertions
            mocked_is_file.assert_called_once_with()

            # post assertions
            self.assertIsNone(vlc_player.entry)

            # assert the callbacks
            vlc_player.callbacks["could_not_play"].assert_called_with(self.id)
            vlc_player.callbacks["error"].assert_called_with(self.id, "File not found")

            # assert the effects on logs
            self.assertListEqual(
                logger.output,
                [
                    "ERROR:dakara_player.media_player.base:File not found '{}'".format(
                        get_temp_dir() / self.song_file_path
                    )
                ],
            )

    @patch("dakara_player.media_player.vlc.set_metadata")
    @patch("dakara_player.media_player.vlc.get_metadata")
    @patch.object(MediaPlayerVlc, "play")
    @patch.object(MediaPlayerVlc, "generate_text")
    @patch.object(Path, "is_file")
    def test_set_playlist_entry(
        self,
        mocked_is_file,
        mocked_generate_text,
        mocked_play,
        mocked_get_metadata,
        mocked_set_metadata,
    ):
        """Test to set a playlist entry."""
        with self.get_instance() as (vlc_player, (_, mocked_background_loader, _), _):
            # setup mocks
            mocked_is_file.return_value = True
            mocked_background_loader.backgrounds = {
                "transition": get_temp_dir() / "transition.png"
            }

            # mock the callbacks
            vlc_player.set_callback("could_not_play", MagicMock())
            vlc_player.set_callback("error", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.entry)

            # call the method
            vlc_player.set_playlist_entry(self.playlist_entry)

            # post assertions
            self.assertEqual(vlc_player.entry.kara_folder_path, get_temp_dir())
            self.assertEqual(vlc_player.entry.playlist_entry, self.entry.playlist_entry)
            self.assertEqual(len(vlc_player.entry.items), 2)
            self.assertIn("transition", vlc_player.entry.items)
            self.assertIn("song", vlc_player.entry.items)

            # assert the callbacks
            vlc_player.callbacks["could_not_play"].assert_not_called()
            vlc_player.callbacks["error"].assert_not_called()

            # assert mocks
            mocked_is_file.assert_called_with()
            mocked_generate_text.assert_called_with("transition")
            mocked_play.assert_called_with("transition")

    def test_set_pause_idle(self):
        """Test to set pause when the player is idle."""
        with self.get_instance() as (vlc_player, (mocked_instance, _, _), _):
            player = mocked_instance.media_player_new.return_value
            self.set_media(vlc_player, "idle")

            # call method
            vlc_player.pause()

            # assert call
            player.pause.assert_not_called()

    def test_restart_transition(self):
        """Test to restart on transition screen."""
        with self.get_instance() as (vlc_player, (mocked_instance, _, _), _):
            player = mocked_instance.media_player_new.return_value
            self.set_media(vlc_player, "idle")

            # call method
            vlc_player.restart()

            # assert call
            player.set_time.assert_not_called()

    @patch.object(MediaPlayerVlc, "clear_playlist_entry")
    def test_skip_idle(self, mocked_clear_playlist_entry):
        """Test to skip on idle screen."""
        with self.get_instance() as (vlc_player, (mocked_instance, _, _), _):
            self.set_media(vlc_player, "idle")

            # call method
            vlc_player.skip(True)

            # assert call
            vlc_player.clear_playlist_entry.assert_not_called()

    def test_rewind_transition(self):
        """Test to rewind on transition screen."""
        with self.get_instance() as (vlc_player, (mocked_instance, _, _), _):
            player = mocked_instance.media_player_new.return_value
            self.set_media(vlc_player, "transition")

            # call method
            vlc_player.rewind()

            # assert call
            player.set_time.assert_not_called()

    def test_fast_forward_transition(self):
        """Test to advance on transition screen."""
        with self.get_instance() as (vlc_player, (mocked_instance, _, _), _):
            player = mocked_instance.media_player_new.return_value
            self.set_media(vlc_player, "transition")

            # call method
            vlc_player.fast_forward()

            # assert call
            player.set_time.assert_not_called()

    @patch.object(Path, "is_file", autospec=True, return_value=True)
    @patch.object(MediaPlayerVlc, "create_thread")
    def test_handle_end_reached_transition(self, mocked_create_thread, mocked_is_file):
        """Test song end callback after a transition screen."""
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)
            self.set_media(vlc_player, "transition")

            # mock the call
            vlc_player.set_callback("finished", MagicMock())

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_end_reached("event")

            assert_no_errors(vlc_player)

            # assert effect on logs
            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:End reached callback called",
                    "DEBUG:dakara_player.media_player.vlc:Finished playing transition "
                    "for 'Song title'",
                ],
            )

            # assert the call
            vlc_player.callbacks["finished"].assert_not_called()
            mocked_create_thread.assert_called_with(
                target=vlc_player.play, args=("song",)
            )

    @patch.object(MediaPlayerVlc, "create_thread")
    def test_handle_end_reached_song(self, mocked_create_thread):
        """Test song end callback after a song."""
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)
            self.set_media(vlc_player, "song")

            # mock the call
            vlc_player.set_callback("finished", MagicMock())

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG"):
                vlc_player.handle_end_reached("event")

            assert_no_errors(vlc_player)

            # assert the call
            vlc_player.callbacks["finished"].assert_called_with(42)
            mocked_create_thread.assert_not_called()

    @patch.object(MediaPlayerVlc, "create_thread")
    def test_handle_end_reached_idle(self, mocked_create_thread):
        """Test song end callback after an idle screen."""
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)
            self.set_media(vlc_player, "idle")

            # mock the call
            vlc_player.set_callback("finished", MagicMock())

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG"):
                vlc_player.handle_end_reached("event")

            assert_no_errors(vlc_player)

            # assert the call
            vlc_player.callbacks["finished"].assert_not_called()
            mocked_create_thread.assert_called_with(
                target=vlc_player.play, args=("idle",)
            )

    @patch.object(MediaPlayerVlc, "create_thread")
    def test_handle_end_reached_invalid(self, mocked_create_thread):
        """Test song end callback on invalid state."""
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)
            media = self.set_media(
                vlc_player,
            )
            set_metadata(media, {"type": "unknown"})

            # mock the call
            vlc_player.set_callback("finished", MagicMock())

            self.assertFalse(vlc_player.stop.is_set())

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG"):
                vlc_player.handle_end_reached("event")

            self.assertTrue(vlc_player.stop.is_set())
            exception_class, _, _ = vlc_player.errors.get()
            self.assertIs(InvalidStateError, exception_class)

            # assert the call
            vlc_player.callbacks["finished"].assert_not_called()
            mocked_create_thread.assert_not_called()

    @patch.object(MediaPlayerVlc, "skip")
    def test_handle_encountered_error(self, mocked_skip):
        """Test error callback."""
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)
            self.set_media(vlc_player, "song")

            # mock the call
            vlc_player.set_callback("error", MagicMock())

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_encountered_error("event")

            assert_no_errors(vlc_player)

            # assert effect on logs
            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:Error callback called",
                    "ERROR:dakara_player.media_player.vlc:Unable to play '{}'".format(
                        get_temp_dir() / self.song_file_path
                    ),
                ],
            )

            # assert the call
            vlc_player.callbacks["error"].assert_called_with(
                42, "Unable to play current song"
            )
            mocked_skip.assert_called_with()

    @patch.object(MediaPlayerVlc, "get_timing")
    def test_handle_playing_resumed(self, mocked_get_timing):
        """Test playing callback when resuming."""
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)
            self.set_media(vlc_player, "song")

            # mock the call
            vlc_player.set_callback("resumed", MagicMock())
            mocked_get_timing.return_value = 25

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_playing("event")

            assert_no_errors(vlc_player)

            # assert effect on logs
            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:Playing callback called",
                    "DEBUG:dakara_player.media_player.vlc:Resumed play",
                ],
            )

            # assert the call
            vlc_player.callbacks["resumed"].assert_called_with(42, 25)

    def test_handle_playing_transition_starts(self):
        """Test playing callback when transition starts."""

        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)
            media = self.set_media(vlc_player, "transition", started=False)

            # mock the call
            vlc_player.set_callback("started_transition", MagicMock())
            vlc_player.player.get_media.return_value = media

            # pre assert
            self.assertFalse(get_metadata(media)["started"])

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_playing("event")

            assert_no_errors(vlc_player)

            # assert effect on logs
            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:Playing callback called",
                    "INFO:dakara_player.media_player.vlc:Playing transition for "
                    "'Song title'",
                ],
            )

            # post assert
            self.assertTrue(get_metadata(media)["started"])

            # assert the call
            vlc_player.callbacks["started_transition"].assert_called_with(42)

    def test_handle_playing_song_starts(self):
        """Test playing callback when song starts."""
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)
            media = self.set_media(vlc_player, "song", started=False)

            # mock the call
            vlc_player.set_callback("started_song", MagicMock())

            # pre assert
            self.assertFalse(get_metadata(media)["started"])

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_playing("event")

            assert_no_errors(vlc_player)

            # assert effect on logs
            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:Playing callback called",
                    "INFO:dakara_player.media_player.vlc:Now playing 'Song title' "
                    "('{}')".format(get_temp_dir() / self.song_file_path),
                ],
            )

            # post assert
            self.assertTrue(get_metadata(media)["started"])

            # assert the call
            vlc_player.callbacks["started_song"].assert_called_with(42)

    def test_handle_playing_song_starts_track_id(self):
        """Test playing callback when media starts with requested track ID."""
        with self.get_instance() as (vlc_player, (mocked_instance, _, _), _):
            mocked_player = mocked_instance.media_player_new.return_value
            self.set_playlist_entry(vlc_player)
            media = self.set_media(vlc_player, "song", started=False)
            update_metadata(media, {"track_id_audio": 99})

            # mock the call
            vlc_player.set_callback("started_song", MagicMock())

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_playing("event")

            assert_no_errors(vlc_player)

            # assert effect on logs
            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:Playing callback called",
                    "DEBUG:dakara_player.media_player.vlc:Requesting to play audio "
                    "track #99",
                    "INFO:dakara_player.media_player.vlc:Now playing 'Song title' "
                    "('{}')".format(get_temp_dir() / self.song_file_path),
                ],
            )

            # assert the call
            vlc_player.callbacks["started_song"].assert_called_with(42)
            mocked_player.audio_set_track.assert_called_with(99)

    def test_handle_playing_idle_starts(self):
        """Test playing callback when idle screen starts."""
        with self.get_instance() as (vlc_player, _, _):
            self.set_media(vlc_player, "idle", started=False)

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_playing("event")

            assert_no_errors(vlc_player)

            # assert effect on logs
            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:Playing callback called",
                    "DEBUG:dakara_player.media_player.vlc:Playing idle screen",
                ],
            )

    def test_handle_playing_invalid(self):
        """Test playing callback on invalid state."""
        with self.get_instance() as (vlc_player, _, _):
            media = self.set_media(vlc_player)
            update_metadata(media, {"type": "unknown"})

            self.assertFalse(vlc_player.stop.is_set())

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG"):
                vlc_player.handle_playing("event")

            self.assertTrue(vlc_player.stop.is_set())
            exception_class, _, _ = vlc_player.errors.get()
            self.assertIs(InvalidStateError, exception_class)

    @patch.object(MediaPlayerVlc, "get_timing")
    def test_handle_paused(self, mocked_get_timing):
        """Test paused callback."""
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)

            # mock the call
            vlc_player.set_callback("paused", MagicMock())
            mocked_get_timing.return_value = 25

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_paused("event")

            assert_no_errors(vlc_player)

            # assert effect on logs
            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:Paused callback called",
                    "DEBUG:dakara_player.media_player.vlc:Paused",
                ],
            )

            # assert the call
            vlc_player.callbacks["paused"].assert_called_with(42, 25)

    @patch.object(PlatformDirs, "user_data_path", new_callable=PropertyMock)
    def test_custom_backgrounds(self, mocked_user_data_path):
        """Test to instanciate with custom backgrounds."""
        mocked_user_data_path.return_value = Path("directory")

        # create object
        tempdir = Path("temp")
        with self.get_instance(
            {
                "backgrounds": {
                    "transition_background_name": "custom_transition.png",
                    "idle_background_name": "custom_idle.png",
                }
            },
            tempdir=tempdir,
        ) as (_, _, (_, mocked_background_loader_class, _)):

            # assert the instanciation of the background loader
            mocked_background_loader_class.assert_called_with(
                destination=tempdir,
                package="dakara_player.resources.backgrounds",
                directory=Path("directory") / "player" / "backgrounds",
                filenames={
                    "transition": "custom_transition.png",
                    "idle": "custom_idle.png",
                },
            )

    def test_default_durations(self):
        """Test to instanciate with default durations."""
        with self.get_instance() as (vlc_player, _, _):
            # assert the instance
            self.assertDictEqual(
                vlc_player.durations,
                {"transition": 10, "idle": 20, "rewind_fast_forward": 10},
            )

    def test_custom_durations(self):
        """Test to instanciate with custom durations."""
        with self.get_instance({"durations": {"transition_duration": 5}}) as (
            vlc_player,
            _,
            _,
        ):
            # assert the instance
            self.assertDictEqual(
                vlc_player.durations,
                {"transition": 5, "idle": 20, "rewind_fast_forward": 10},
            )

    @patch("dakara_player.media_player.base.PLAYER_CLOSING_DURATION", 0)
    @patch.object(MediaPlayerVlc, "stop_player")
    def test_slow_close(self, mocked_stop_player):
        """Test to close VLC when it takes a lot of time."""
        with self.get_instance() as (vlc_player, _, _):
            mocked_stop_player.side_effect = lambda: sleep(1)

            with self.assertLogs("dakara_player.media_player.base", "DEBUG") as logger:
                vlc_player.exit_worker()

            self.assertListEqual(
                logger.output,
                ["WARNING:dakara_player.media_player.base:VLC takes too long to stop"],
            )

    @patch.object(TextGenerator, "get_text")
    def test_generate_text_invalid(self, mocked_get_text):
        """Test to generate invalid text screen."""
        with self.get_instance() as (vlc_player, _, _):
            with self.assertRaisesRegex(
                ValueError, "Unexpected action to generate text for: none"
            ):
                vlc_player.generate_text("none")

        with self.assertRaisesRegex(
            ValueError, "Unexpected action to generate text for: none"
        ):
            vlc_player.generate_text("none")

        mocked_get_text.assert_not_called()

    def test_play_invalid(self):
        """Test to play invalid action."""
        with self.get_instance() as (vlc_player, _, _):
            with self.assertRaisesRegex(ValueError, "Unexpected action to play: none"):
                vlc_player.play("none")

            vlc_player.player.play.assert_not_called()

    def test_set_window_none(self):
        """Test to use default window."""
        with self.get_instance() as (vlc_player, _, _):
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.set_window(None)

            self.assertListEqual(
                logger.output,
                ["DEBUG:dakara_player.media_player.vlc:Using VLC default window"],
            )

    @patch("dakara_player.media_player.vlc.platform.system", return_value="Linux")
    def test_set_window_linux(self, mocked_system):
        """Test to use X window."""
        with self.get_instance() as (vlc_player, _, _):
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.set_window(99)

            self.assertListEqual(
                logger.output,
                ["DEBUG:dakara_player.media_player.vlc:Associating X window to VLC"],
            )

    @patch("dakara_player.media_player.vlc.platform.system", return_value="Windows")
    def test_set_window_windows(self, mocked_system):
        """Test to use Win API window."""
        with self.get_instance() as (vlc_player, _, _):
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.set_window(99)

            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:"
                    "Associating Win API window to VLC"
                ],
            )

    @patch("dakara_player.media_player.vlc.platform.system", return_value="other")
    def test_set_window_other(self, mocked_system):
        """Test to set window on unknown platform."""
        with self.get_instance() as (vlc_player, _, _):
            with self.assertRaises(NotImplementedError):
                vlc_player.set_window(99)


@patch.object(MediaPlayerVlc, "is_playing_this")
class OnPlayingThisTestCase(BaseTestCase):
    """Test the decorator for returning early if the player is playing
    something else."""

    def test_in_list(self, mocked_is_playing_this):
        """Test an action in the list of accepted actions."""
        function = MagicMock()
        mocked_is_playing_this.side_effect = lambda what: what == "song"

        function_decorated = on_playing_this(["transition", "song"])(function)

        with self.get_instance() as (player, _, _):
            function_decorated(player)

            function.assert_called_with(player)

    def test_not_in_list(self, mocked_is_playing_this):
        """Test an action not in the list of accepted actions."""
        function = MagicMock()
        mocked_is_playing_this.side_effect = lambda what: what == "idle"

        function_decorated = on_playing_this(["transition", "song"])(function)

        with self.get_instance() as (player, _, _):
            self.assertIsNone(function_decorated(player))

            function.assert_not_called()

    def test_not_in_list_default_return(self, mocked_is_playing_this):
        """Test an action not in the list of accepted actions."""
        function = MagicMock()
        mocked_is_playing_this.side_effect = lambda what: what == "idle"

        function_decorated = on_playing_this(["transition", "song"], 42)(function)

        with self.get_instance() as (player, _, _):
            self.assertEqual(function_decorated(player), 42)


@patch("dakara_player.media_player.vlc.vlc", autospec=True)
class GetInstanceTestCase(TestCase):

    def test_parameters_unexpected(self, mocked_vlc):
        """Test to pass unexpected parameters."""
        mocked_vlc.Instance.return_value = None
        with self.assertRaises(UnexpectedInstanceParameterError):
            get_instance(["parameter"])

    def test_parameters(self, mocked_vlc):
        """Test to pass parameters."""
        self.assertIs(mocked_vlc.Instance.return_value, get_instance(["parameter"]))
        mocked_vlc.Instance.assert_called_with(["parameter"])

    def test_no_parameters_unavailable(self, mocked_vlc):
        """Test unavailable instance."""
        mocked_vlc.Instance.return_value = None
        with self.assertRaises(UnavailableInstanceError):
            get_instance()

    def test_no_parameters(self, mocked_vlc):
        """Test instance."""
        self.assertIs(mocked_vlc.Instance.return_value, get_instance())
        mocked_vlc.Instance.assert_called_with()


@dataclass
class DummyTrack:
    id: int
    type: vlc.TrackType


class TestMediaPlayerEntryVlc:
    def test_get_transition_media(self, media_player_entry):
        """Test to get a transition."""
        transition = get_transition_media(media_player_entry.items["transition"], [])

        assert transition is not None
        assert transition.get_mrl() == (get_temp_dir() / "transition.png").as_uri()
        assert get_metadata(transition) == {"type": "transition", "started": False}

    def test_get_song_media(self, media_player_entry):
        """Test to get a song."""
        song = get_song_media(media_player_entry.items["song"], [])

        assert song is not None
        assert song.get_mrl() == (get_temp_dir() / "file.mkv").as_uri()
        assert get_metadata(song) == {
            "type": "song",
            "started": False,
            "track_id_audio": None,
        }

    def test_get_song_media_instrumental_file(
        self, media_player_entry_instrumental_file, mocker
    ):
        """Test to get a song with instrumental file."""
        mocker.patch.object(
            vlc.Media,
            "tracks_get",
            return_value=[
                DummyTrack(0, vlc.TrackType.video),
                DummyTrack(1, vlc.TrackType.audio),
            ],
            autospec=True,
        )
        mocker.patch.object(vlc.Media, "parse", autospec=True)

        song = get_song_media(media_player_entry_instrumental_file.items["song"], [])

        assert get_metadata(song) == {
            "type": "song",
            "started": False,
            "track_id_audio": 2,
        }

    def test_get_song_media_instrumental_file_no_slaves_add(
        self, media_player_entry_instrumental_file, mocker, caplog
    ):
        """Test to be unable to add instrumental file."""
        mocker.patch.object(
            vlc.Media,
            "tracks_get",
            return_value=[
                DummyTrack(0, vlc.TrackType.video),
                DummyTrack(1, vlc.TrackType.audio),
            ],
            autospec=True,
        )
        mocker.patch.object(vlc.Media, "parse", autospec=True)
        mocker.patch.object(
            vlc.Media,
            "slaves_add",
            side_effect=NameError("no slaves_add"),
            autospec=True,
        )

        song = get_song_media(media_player_entry_instrumental_file.items["song"], [])

        assert get_metadata(song) == {
            "type": "song",
            "started": False,
            "track_id_audio": None,
        }
        assert caplog.record_tuples == [
            (
                "dakara_player.media_player.vlc",
                logging.ERROR,
                "This version of VLC does not support slaves, cannot add "
                "instrumental file",
            )
        ]

    def test_get_song_media_instrumental_track(
        self, media_player_entry_instrumental_track, mocker, caplog
    ):
        """Test to get a song with instrumental track."""
        mocker.patch.object(
            vlc.Media,
            "tracks_get",
            return_value=[
                DummyTrack(0, vlc.TrackType.video),
                DummyTrack(1, vlc.TrackType.audio),
                DummyTrack(2, vlc.TrackType.audio),
            ],
            autospec=True,
        )
        mocker.patch.object(vlc.Media, "parse", autospec=True)

        caplog.set_level(logging.DEBUG)

        song = get_song_media(media_player_entry_instrumental_track.items["song"], [])

        assert get_metadata(song) == {
            "type": "song",
            "started": False,
            "track_id_audio": 2,
        }
        assert caplog.record_tuples == [
            (
                "dakara_player.media_player.vlc",
                logging.DEBUG,
                "Instrumental track is #2 for VLC",
            ),
        ]

    def test_get_song_media_instrumental_track_no_track(
        self, media_player_entry_instrumental_track, mocker, caplog
    ):
        """Test to get a song with instrumental track when this track is
        missing."""
        mocker.patch.object(
            vlc.Media,
            "tracks_get",
            return_value=[
                DummyTrack(0, vlc.TrackType.video),
                DummyTrack(1, vlc.TrackType.audio),
            ],
            autospec=True,
        )
        mocker.patch.object(vlc.Media, "parse", autospec=True)

        caplog.set_level(logging.INFO)

        song = get_song_media(media_player_entry_instrumental_track.items["song"], [])

        assert get_metadata(song) == {
            "type": "song",
            "started": False,
            "track_id_audio": None,
        }
        assert caplog.record_tuples == [
            (
                "dakara_player.media_player.vlc",
                logging.ERROR,
                "Unable to find requested instrumental track 1",
            ),
        ]


@pytest.fixture
def media() -> vlc.Media:
    return vlc.Media("nowhere")


@pytest.fixture
def media_set(media) -> vlc.Media:
    set_metadata(media, {"key": "value"})
    return media


class TestMetadata:
    def test_set_first(self, media):
        """Test to set metadata for the first time."""
        key = set_metadata(media, {"key": "value"})
        meta = loads(media.get_meta(key))

        # assert content
        assert "key" in meta
        assert meta["key"] == "value"

        # assert marker
        assert "set_by" in meta
        assert meta["set_by"] == "dakara"

    def test_set_second(self, media):
        """Test to set metadata for the second time."""
        key1 = set_metadata(media, {"key": "value1"})
        key2 = set_metadata(media, {"key": "value2"})

        assert key1 == key2

        meta = loads(media.get_meta(key2))

        # assert content
        assert "key" in meta
        assert meta["key"] == "value2"

    def test_set_slot_not_empty(self, media):
        """Test to set metadata in second slot when the first one is not empty."""
        media.set_meta(0, "foo")
        media.set_meta(1, "bar")
        key = set_metadata(media, {"key": "value"})

        assert key == 2

        meta = loads(media.get_meta(key))

        # assert content
        assert "key" in meta
        assert meta["key"] == "value"

    def test_set_fail(self, media, mocker):
        """Test error when unable to set metadata in any field."""
        mocker.patch.object(vlc.Media, "get_meta", return_value="value", autospec=True)

        with pytest.raises(ValueError):
            set_metadata(media, {"key": "value"})

    def test_get_first(self, media_set):
        """Test to get metadata from the first time."""
        meta = get_metadata(media_set)

        assert "key" in meta
        assert meta["key"] == "value"

    def test_get_second(self, media_set):
        """Test to get metadata from the first time."""
        get_metadata(media_set)
        meta = get_metadata(media_set)

        assert "key" in meta
        assert meta["key"] == "value"

    def test_get_slot_not_empty(self, media):
        """Test to get metadata from second slot when the first one is not empty."""
        media.set_meta(0, "foo")
        media.set_meta(1, "bar")
        set_metadata(media, {"key": "value"})

        get_metadata(media)
        meta = get_metadata(media)

        assert "key" in meta
        assert meta["key"] == "value"

    def test_get_fail(self, media):
        """Test error when metadata is not set."""
        with pytest.raises(ValueError):
            get_metadata(media)

    def test_get_fail_slot_not_empty(self, media):
        """Test error when metadata is not set with first slot being not empty."""
        media.set_meta(0, "foo")
        media.set_meta(1, "bar")

        with pytest.raises(ValueError):
            get_metadata(media)

    def test_get_fail_no_marker(self, media):
        """Test error when metadata do not have the marker."""
        media.set_meta(0, dumps({"foo": "bar"}))
        media.set_meta(1, dumps({"foo": "baz"}))

        with pytest.raises(ValueError):
            get_metadata(media)

    def test_update_first(self, media_set):
        """Test update metadata for the first time."""
        update_metadata(media_set, {"foo": "bar"})

        meta = get_metadata(media_set)

        assert "key" in meta
        assert meta["key"] == "value"
        assert "foo" in meta
        assert meta["foo"] == "bar"

    def test_update_second(self, media_set):
        """Test update metadata for the second time."""
        key1 = update_metadata(media_set, {"foo": "bar"})
        key2 = update_metadata(media_set, {"foo": "bar"})

        assert key1 == key2

        meta = get_metadata(media_set)

        assert "key" in meta
        assert meta["key"] == "value"
        assert "foo" in meta
        assert meta["foo"] == "bar"
