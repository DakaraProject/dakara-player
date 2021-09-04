import re
from contextlib import ExitStack, contextmanager
from queue import Queue
from tempfile import gettempdir
from threading import Event
from time import sleep
from unittest import TestCase, skipIf
from unittest.mock import MagicMock, call, patch

try:
    import vlc

except (ImportError, OSError):
    vlc = None

from packaging.version import parse
from path import Path

from dakara_player.media_player.base import (
    InvalidStateError,
    KaraFolderNotFound,
    VersionNotFoundError,
)
from dakara_player.media_player.vlc import (
    MediaPlayerVlc,
    VlcTooOldError,
    get_metadata,
    set_metadata,
)
from dakara_player.mrl import path_to_mrl
from dakara_player.text_generator import TextGenerator
from dakara_player.window import DummyWindowManager, WindowManager


@patch("dakara_player.media_player.base.TRANSITION_DURATION", 10)
@patch("dakara_player.media_player.base.IDLE_DURATION", 20)
class MediaPlayerVlcTestCase(TestCase):
    """Test the VLC player class unitary
    """

    def setUp(self):
        # create playlist entry ID
        self.id = 42

        # create playlist entry file path
        self.song_file_path = Path("file")

        # create playlist entry
        self.playlist_entry = {
            "id": self.id,
            "song": {"title": "Song title", "file_path": self.song_file_path},
            "owner": "me",
            "use_instrumental": False,
        }

    @contextmanager
    def get_instance(
        self, config=None, tempdir=None,
    ):
        """Get a heavily mocked instance of MediaPlayerVlc

        Args:
            config (dict): Configuration passed to the constructor.
            tempdir (path.Path): Path to temporary directory.

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
        config = config or {"kara_folder": gettempdir()}

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

    def set_playlist_entry(self, vlc_player, started=True):
        """Set a playlist entry and make the player play it

        Args:
            vlc_player (MediaPlayerVlc): Instance of the VLC player.
            started (bool): If True, make the player play the song.
        """
        vlc_player.playlist_entry = self.playlist_entry

        # create mocked transition
        vlc_player.playlist_entry_data["transition"].media = MagicMock()

        # create mocked song
        media_song = MagicMock()
        media_song.get_mrl.return_value = path_to_mrl(
            vlc_player.kara_folder_path / self.playlist_entry["song"]["file_path"]
        )
        vlc_player.playlist_entry_data["song"].media = media_song

        # set media has started
        if started:
            player = vlc_player.instance.media_player_new.return_value
            player.get_media.return_value = vlc_player.playlist_entry_data["song"].media
            vlc_player.playlist_entry_data["transition"].started = True
            vlc_player.playlist_entry_data["song"].started = True

    def test_init_window(self):
        """Test to use default or custom window
        """
        # default window
        with self.get_instance(
            {"kara_folder": gettempdir(), "vlc": {"use_default_window": True}}
        ) as (vlc_player, _, _):
            self.assertIsInstance(vlc_player.window, DummyWindowManager)

        # custom window
        with self.get_instance() as (vlc_player, _, _):
            self.assertIsInstance(vlc_player.window, WindowManager)

    def test_set_callback(self):
        """Test the assignation of a callback
        """
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
        """Test the assignation of a callback to a VLC event

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

    @patch("dakara_player.media_player.vlc.libvlc_get_version")
    def test_get_version_long_4_digits(self, mocked_libvlc_get_version):
        """Test to get the VLC version when it is long and contains 4 digits
        """
        # mock the version of VLC
        mocked_libvlc_get_version.return_value = b"3.0.11.1 Vetinari"

        # call the method
        version = MediaPlayerVlc.get_version()

        # assert the result
        self.assertEqual(version, parse("3.0.11.1"))

    @patch("dakara_player.media_player.vlc.libvlc_get_version")
    def test_get_version_long(self, mocked_libvlc_get_version):
        """Test to get the VLC version when it is long
        """
        # mock the version of VLC
        mocked_libvlc_get_version.return_value = b"3.0.11 Vetinari"

        # call the method
        version = MediaPlayerVlc.get_version()

        # assert the result
        self.assertEqual(version, parse("3.0.11"))

    @patch("dakara_player.media_player.vlc.libvlc_get_version")
    def test_get_version_not_found(self, mocked_libvlc_get_version):
        """Test to get the VLC version when it is not available
        """
        # mock the version of VLC
        mocked_libvlc_get_version.return_value = b"none"

        # call the method
        with self.assertRaisesRegex(VersionNotFoundError, "Unable to get VLC version"):
            MediaPlayerVlc.get_version()

    @patch.object(MediaPlayerVlc, "get_version")
    def test_check_version(self, mocked_get_version):
        """Test to check recent enough version VLC
        """
        with self.get_instance() as (vlc_player, _, _):
            # mock the version of VLC
            mocked_get_version.return_value = parse("3.0.0")

            # call the method
            vlc_player.check_version()

    @patch.object(MediaPlayerVlc, "get_version")
    def test_check_version_old(self, mocked_get_version):
        """Test to check old version of VLC
        """
        with self.get_instance() as (vlc_player, _, _):
            # mock the version of VLC
            mocked_get_version.return_value = parse("2.0.0")

            # call the method
            with self.assertRaisesRegex(VlcTooOldError, "VLC is too old"):
                vlc_player.check_version()

    @patch.object(MediaPlayerVlc, "get_version")
    def test_check_version_3013(self, mocked_get_version):
        """Test to check VLC version 3.0.13
        """
        with self.get_instance() as (vlc_player, _, _):
            # mock the version of VLC
            mocked_get_version.return_value = parse("3.0.13")

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "WARNING") as logger:
                vlc_player.check_version()

            self.assertListEqual(
                logger.output,
                [
                    "WARNING:dakara_player.media_player.vlc:This version of VLC "
                    "is known to not work with Dakara player"
                ],
            )

    @patch.object(MediaPlayerVlc, "get_version")
    def test_check_version_3014(self, mocked_get_version):
        """Test to check VLC version 3.0.14
        """
        with self.get_instance() as (vlc_player, _, _):
            # mock the version of VLC
            mocked_get_version.return_value = parse("3.0.14")

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "WARNING") as logger:
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
        """Test to check if the kara folder exists
        """
        with self.get_instance() as (vlc_player, _, _):
            # pretend the directory exists
            mocked_exists.return_value = True

            # call the method
            vlc_player.check_kara_folder_path()

            # assert the call
            mocked_exists.assert_called_with()

    @patch.object(Path, "exists")
    def test_check_kara_folder_path_does_not_exist(self, mocked_exists):
        """Test to check if the kara folder does not exist
        """
        with self.get_instance() as (vlc_player, _, _):
            # pretend the directory does not exist
            mocked_exists.return_value = False

            # call the method
            with self.assertRaisesRegex(
                KaraFolderNotFound,
                'Karaoke folder "{}" does not exist'.format(re.escape(gettempdir())),
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
        """Test to load the instance
        """
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

    @patch.object(Path, "exists")
    def test_set_playlist_entry_error_file(self, mocked_exists):
        """Test to set a playlist entry that does not exist
        """
        with self.get_instance() as (vlc_player, _, _):
            # mock the system call
            mocked_exists.return_value = False

            # mock the callbacks
            vlc_player.set_callback("could_not_play", MagicMock())
            vlc_player.set_callback("error", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)

            # call the method
            with self.assertLogs("dakara_player.media_player.base", "DEBUG") as logger:
                vlc_player.set_playlist_entry(self.playlist_entry)

            # call assertions
            mocked_exists.assert_called_once_with()

            # post assertions
            self.assertIsNone(vlc_player.playlist_entry)

            # assert the callbacks
            vlc_player.callbacks["could_not_play"].assert_called_with(self.id)
            vlc_player.callbacks["error"].assert_called_with(self.id, "File not found")

            # assert the effects on logs
            self.assertListEqual(
                logger.output,
                [
                    "ERROR:dakara_player.media_player.base:File not found '{}'".format(
                        Path(gettempdir()) / self.song_file_path
                    )
                ],
            )

    @patch("dakara_player.media_player.vlc.set_metadata")
    @patch("dakara_player.media_player.vlc.get_metadata")
    @patch.object(MediaPlayerVlc, "manage_instrumental")
    @patch.object(MediaPlayerVlc, "play")
    @patch.object(MediaPlayerVlc, "generate_text")
    @patch.object(Path, "exists")
    def test_set_playlist_entry(
        self,
        mocked_exists,
        mocked_generate_text,
        mocked_play,
        mocked_manage_instrumental,
        mocked_get_metadata,
        mocked_set_metadata,
    ):
        """Test to set a playlist entry
        """
        with self.get_instance() as (vlc_player, (_, mocked_background_loader, _), _):
            # setup mocks
            mocked_exists.return_value = True
            mocked_background_loader.backgrounds = {
                "transition": Path(gettempdir()) / "transition.png"
            }

            # mock the callbacks
            vlc_player.set_callback("could_not_play", MagicMock())
            vlc_player.set_callback("error", MagicMock())

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry)

            # call the method
            vlc_player.set_playlist_entry(self.playlist_entry)
            self.assertFalse(self.playlist_entry["use_instrumental"])

            # post assertions
            self.assertDictEqual(vlc_player.playlist_entry, self.playlist_entry)

            # assert the callbacks
            vlc_player.callbacks["could_not_play"].assert_not_called()
            vlc_player.callbacks["error"].assert_not_called()

            # assert mocks
            mocked_exists.assert_called_with()
            mocked_generate_text.assert_called_with("transition")
            mocked_play.assert_called_with("transition")
            mocked_manage_instrumental.assert_not_called()

    @patch.object(MediaPlayerVlc, "get_audio_tracks_id")
    @patch.object(MediaPlayerVlc, "get_number_tracks")
    @patch.object(MediaPlayerVlc, "get_instrumental_file")
    def test_manage_instrumental_file(
        self,
        mocked_get_instrumental_file,
        mocked_get_number_tracks,
        mocked_get_audio_tracks_id,
    ):
        """Test to add instrumental file
        """
        with self.get_instance() as (vlc_player, (mocked_instance, _, _), _):
            video_path = Path(gettempdir()) / "video"
            audio_path = Path(gettempdir()) / "audio"

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry_data["song"].audio_track_id)
            self.assertIsNotNone(vlc_player.kara_folder_path)

            # set playlist entry to request instrumental
            self.playlist_entry["use_instrumental"] = True

            # mocks
            mocked_get_instrumental_file.return_value = audio_path
            mocked_get_number_tracks.return_value = 2
            mocked_media_song = mocked_instance.media_new_path.return_value
            vlc_player.playlist_entry_data["song"].media = mocked_media_song

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.manage_instrumental(self.playlist_entry, video_path)

            # post assertions
            self.assertEqual(vlc_player.playlist_entry_data["song"].audio_track_id, 2)

            # assert the effects on logs
            self.assertListEqual(
                logger.output,
                [
                    "INFO:dakara_player.media_player.vlc:Requesting to play "
                    "instrumental file '{}' for '{}'".format(audio_path, video_path),
                ],
            )

            # assert the call
            mocked_get_audio_tracks_id.assert_not_called()

    @patch.object(MediaPlayerVlc, "get_number_tracks")
    @patch.object(MediaPlayerVlc, "get_instrumental_file")
    def test_manage_instrumental_file_error_slaves_add(
        self, mocked_get_instrumental_file, mocked_get_number_tracks,
    ):
        """Test to be unable to add instrumental file
        """
        with self.get_instance() as (vlc_player, (mocked_instance, _, _), _):
            video_path = Path(gettempdir()) / "video"
            audio_path = Path(gettempdir()) / "audio"

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry_data["song"].audio_track_id)
            self.assertIsNotNone(vlc_player.kara_folder_path)

            # set playlist entry to request instrumental
            self.playlist_entry["use_instrumental"] = True

            # mocks
            mocked_get_instrumental_file.return_value = audio_path
            mocked_get_number_tracks.return_value = 2

            # make slaves_add method unavailable
            mocked_media_song = mocked_instance.return_value.media_new_path.return_value
            mocked_media_song.slaves_add.side_effect = NameError("no slaves_add")
            vlc_player.playlist_entry_data["song"].media = mocked_media_song

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.manage_instrumental(self.playlist_entry, video_path)

            # post assertions
            self.assertIsNone(vlc_player.playlist_entry_data["song"].audio_track_id)

            # assert the effects on logs
            self.assertListEqual(
                logger.output,
                [
                    "INFO:dakara_player.media_player.vlc:Requesting to play "
                    "instrumental file '{}' for '{}'".format(audio_path, video_path),
                    "ERROR:dakara_player.media_player.vlc:This version of VLC does "
                    "not support slaves, cannot add instrumental file",
                ],
            )

    @patch.object(MediaPlayerVlc, "get_audio_tracks_id")
    @patch.object(MediaPlayerVlc, "get_number_tracks")
    @patch.object(MediaPlayerVlc, "get_instrumental_file")
    def test_manage_instrumental_track(
        self,
        mocked_get_instrumental_file,
        mocked_get_number_tracks,
        mocked_get_audio_tracks_id,
    ):
        """Test add instrumental track
        """
        with self.get_instance() as (vlc_player, (mocked_instance, _, _,), _):
            video_path = Path(gettempdir()) / "video"

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry_data["song"].audio_track_id)
            self.assertIsNotNone(vlc_player.kara_folder_path)

            # set playlist entry to request instrumental
            self.playlist_entry["use_instrumental"] = True

            # mocks
            mocked_get_instrumental_file.return_value = None
            mocked_get_audio_tracks_id.return_value = [0, 99, 42]
            mocked_media_song = mocked_instance.media_new_path.return_value
            vlc_player.playlist_entry_data["song"].media = mocked_media_song

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.manage_instrumental(self.playlist_entry, video_path)

            # post assertions
            self.assertEqual(vlc_player.playlist_entry_data["song"].audio_track_id, 99)

            # assert the effects on logs
            self.assertListEqual(
                logger.output,
                [
                    "INFO:dakara_player.media_player.vlc:Requesting to play "
                    "instrumental track of '{}'".format(video_path),
                ],
            )

            # assert the call
            mocked_get_number_tracks.assert_not_called()

    @patch.object(MediaPlayerVlc, "get_audio_tracks_id")
    @patch.object(MediaPlayerVlc, "get_instrumental_file")
    def test_manage_instrumental_no_instrumental_found(
        self, mocked_get_instrumental_file, mocked_get_audio_tracks_id
    ):
        """Test to cannot find instrumental
        """
        with self.get_instance() as (vlc_player, (mocked_instance, _, _), _):
            video_path = Path(gettempdir()) / "video"

            # pre assertions
            self.assertIsNone(vlc_player.playlist_entry_data["song"].audio_track_id)

            # set playlist entry to request instrumental
            self.playlist_entry["use_instrumental"] = True

            # mocks
            mocked_get_instrumental_file.return_value = None
            mocked_get_audio_tracks_id.return_value = [99]

            # make slaves_add method unavailable
            mocked_media_song = mocked_instance.return_value.media_new_path.return_value
            vlc_player.playlist_entry_data["song"].media = mocked_media_song

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.manage_instrumental(self.playlist_entry, video_path)

            # post assertions
            self.assertIsNone(vlc_player.playlist_entry_data["song"].audio_track_id)

            # assert the effects on logs
            self.assertListEqual(
                logger.output,
                [
                    "WARNING:dakara_player.media_player.vlc:Cannot find instrumental "
                    "file or track for file '{}'".format(video_path)
                ],
            )

    @patch.object(MediaPlayerVlc, "is_playing_this")
    def test_set_pause_idle(self, mocked_is_playing_this):
        """Test to set pause when the player is idle
        """
        with self.get_instance() as (vlc_player, (mocked_instance, _, _), _):
            player = mocked_instance.media_player_new.return_value

            # mock
            mocked_is_playing_this.return_value = True

            # call method
            vlc_player.pause(True)

            # assert call
            player.pause.assert_not_called()
            mocked_is_playing_this.assert_called_with("idle")

    @patch.object(MediaPlayerVlc, "create_thread")
    @patch.object(MediaPlayerVlc, "is_playing_this")
    def test_handle_end_reached_transition(
        self, mocked_is_playing_this, mocked_create_thread
    ):
        """Test song end callback after a transition screen
        """
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)
            vlc_player.playlist_entry_data["song"].started = False

            # mock the call
            mocked_is_playing_this.return_value = True
            vlc_player.set_callback("finished", MagicMock())

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_end_reached("event")

            # assert effect on logs
            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:End reached callback called",
                    "DEBUG:dakara_player.media_player.vlc:Will play '{}'".format(
                        Path(gettempdir()) / self.song_file_path
                    ),
                ],
            )

            # assert the call
            vlc_player.callbacks["finished"].assert_not_called()
            mocked_create_thread.assert_called_with(
                target=vlc_player.play, args=("song",)
            )
            mocked_is_playing_this.assert_called_with("transition")

    @patch.object(MediaPlayerVlc, "create_thread")
    @patch.object(MediaPlayerVlc, "is_playing_this")
    def test_handle_end_reached_song(
        self, mocked_is_playing_this, mocked_create_thread
    ):
        """Test song end callback after a song
        """
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)

            # mock the call
            vlc_player.set_callback("finished", MagicMock())
            mocked_is_playing_this.side_effect = [False, True]

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG"):
                vlc_player.handle_end_reached("event")

            # post assert
            self.assertIsNone(vlc_player.playlist_entry_data["song"].media)

            # assert the call
            vlc_player.callbacks["finished"].assert_called_with(42)
            mocked_create_thread.assert_not_called()
            mocked_is_playing_this.assert_has_calls([call("transition"), call("song")])

    @patch.object(MediaPlayerVlc, "create_thread")
    @patch.object(MediaPlayerVlc, "is_playing_this")
    def test_handle_end_reached_idle(
        self, mocked_is_playing_this, mocked_create_thread
    ):
        """Test song end callback after an idle screen
        """
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)

            # mock the call
            vlc_player.set_callback("finished", MagicMock())
            mocked_is_playing_this.side_effect = [False, False, True]

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG"):
                vlc_player.handle_end_reached("event")

            # assert the call
            vlc_player.callbacks["finished"].assert_not_called()
            mocked_create_thread.assert_called_with(
                target=vlc_player.play, args=("idle",)
            )
            mocked_is_playing_this.assert_has_calls(
                [call("transition"), call("song"), call("idle")]
            )

    @patch.object(MediaPlayerVlc, "create_thread")
    @patch.object(MediaPlayerVlc, "is_playing_this")
    def test_handle_end_reached_invalid(
        self, mocked_is_playing_this, mocked_create_thread
    ):
        """Test song end callback on invalid state
        """
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)

            # mock the call
            vlc_player.set_callback("finished", MagicMock())
            mocked_is_playing_this.return_value = False

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
    @patch.object(MediaPlayerVlc, "is_playing_this")
    def test_handle_encountered_error(self, mocked_is_playing_this, mocked_skip):
        """Test error callback
        """
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)

            # mock the call
            vlc_player.set_callback("error", MagicMock())

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_encountered_error("event")

            # assert effect on logs
            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:Error callback called",
                    "ERROR:dakara_player.media_player.vlc:Unable to play '{}'".format(
                        Path(gettempdir()) / self.song_file_path
                    ),
                ],
            )

            # assert the call
            vlc_player.callbacks["error"].assert_called_with(
                42, "Unable to play current song"
            )
            mocked_skip.assert_called_with()

    @patch.object(MediaPlayerVlc, "get_timing")
    @patch.object(MediaPlayerVlc, "is_playing_this")
    def test_handle_playing_unpause(self, mocked_is_playing_this, mocked_get_timing):
        """Test playing callback when unpausing
        """
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)

            # mock the call
            vlc_player.set_callback("resumed", MagicMock())
            mocked_is_playing_this.return_value = True
            mocked_get_timing.return_value = 25

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_playing("event")

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
            mocked_is_playing_this.assert_called_with("transition")

    @patch.object(MediaPlayerVlc, "is_playing_this")
    def test_handle_playing_transition_starts(self, mocked_is_playing_this):
        """Test playing callback when transition starts
        """
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player, started=False)

            # mock the call
            vlc_player.set_callback("started_transition", MagicMock())
            mocked_is_playing_this.side_effect = [False, False, True]

            # pre assert
            self.assertFalse(vlc_player.playlist_entry_data["transition"].started)
            self.assertFalse(vlc_player.playlist_entry_data["song"].started)

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_playing("event")

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
            self.assertTrue(vlc_player.playlist_entry_data["transition"].started)
            self.assertFalse(vlc_player.playlist_entry_data["song"].started)

            # assert the call
            vlc_player.callbacks["started_transition"].assert_called_with(42)
            mocked_is_playing_this.assert_has_calls(
                [call("transition"), call("song"), call("transition")]
            )

    @patch.object(MediaPlayerVlc, "is_playing_this")
    def test_handle_playing_song(self, mocked_is_playing_this):
        """Test playing callback when song starts
        """
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)
            vlc_player.playlist_entry_data["song"].started = False

            # mock the call
            vlc_player.set_callback("started_song", MagicMock())
            mocked_is_playing_this.side_effect = [False, False, False, True]

            # pre assert
            self.assertFalse(vlc_player.playlist_entry_data["song"].started)

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_playing("event")

            # assert effect on logs
            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:Playing callback called",
                    "INFO:dakara_player.media_player.vlc:Now playing 'Song title' "
                    "('{}')".format(Path(gettempdir()) / self.song_file_path),
                ],
            )

            # post assert
            self.assertTrue(vlc_player.playlist_entry_data["song"].started)

            # assert the call
            vlc_player.callbacks["started_song"].assert_called_with(42)
            mocked_is_playing_this.assert_has_calls(
                [call("transition"), call("song"), call("transition"), call("song")]
            )

    @patch.object(MediaPlayerVlc, "is_playing_this")
    def test_handle_playing_media_starts_track_id(self, mocked_is_playing_this):
        """Test playing callback when media starts with requested track ID
        """
        with self.get_instance() as (vlc_player, (mocked_instance, _, _), _):
            mocked_player = mocked_instance.media_player_new.return_value
            self.set_playlist_entry(vlc_player)
            vlc_player.playlist_entry_data["song"].audio_track_id = 99

            # mock the call
            vlc_player.set_callback("started_song", MagicMock())
            mocked_is_playing_this.side_effect = [False, False, False, True]

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_playing("event")

            # assert effect on logs
            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:Playing callback called",
                    "DEBUG:dakara_player.media_player.vlc:Requesting to play audio "
                    "track 99",
                    "INFO:dakara_player.media_player.vlc:Now playing 'Song title' "
                    "('{}')".format(Path(gettempdir()) / self.song_file_path),
                ],
            )

            # assert the call
            vlc_player.callbacks["started_song"].assert_called_with(42)
            mocked_player.audio_set_track.assert_called_with(99)
            mocked_is_playing_this.assert_has_calls(
                [call("transition"), call("song"), call("transition"), call("song")]
            )

    @patch.object(MediaPlayerVlc, "is_playing_this")
    def test_handle_playing_idle_starts(self, mocked_is_playing_this):
        """Test playing callback when idle screen starts
        """
        with self.get_instance() as (vlc_player, _, _):
            # mock the call
            mocked_is_playing_this.side_effect = [False, False, False, False, True]

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_playing("event")

            # assert effect on logs
            self.assertListEqual(
                logger.output,
                [
                    "DEBUG:dakara_player.media_player.vlc:Playing callback called",
                    "DEBUG:dakara_player.media_player.vlc:Playing idle screen",
                ],
            )

            # assert the call
            mocked_is_playing_this.assert_has_calls(
                [
                    call("transition"),
                    call("song"),
                    call("transition"),
                    call("song"),
                    call("idle"),
                ]
            )

    @patch.object(MediaPlayerVlc, "is_playing_this")
    def test_handle_playing_invalid(self, mocked_is_playing_this):
        """Test playing callback on invalid state
        """
        with self.get_instance() as (vlc_player, _, _):
            # setup mock
            mocked_is_playing_this.return_value = False

            self.assertFalse(vlc_player.stop.is_set())

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG"):
                vlc_player.handle_playing("event")

            self.assertTrue(vlc_player.stop.is_set())
            exception_class, _, _ = vlc_player.errors.get()
            self.assertIs(InvalidStateError, exception_class)

    @patch.object(MediaPlayerVlc, "get_timing")
    def test_handle_paused(self, mocked_get_timing):
        """Test paused callback
        """
        with self.get_instance() as (vlc_player, _, _):
            self.set_playlist_entry(vlc_player)

            # mock the call
            vlc_player.set_callback("paused", MagicMock())
            mocked_get_timing.return_value = 25

            # call the method
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.handle_paused("event")

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

    @patch("dakara_player.media_player.base.get_user_directory")
    def test_custom_backgrounds(self, mocked_get_user_directory):
        """Test to instanciate with custom backgrounds
        """
        mocked_get_user_directory.return_value = Path("custom")

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
                directory=Path("custom") / "backgrounds",
                filenames={
                    "transition": "custom_transition.png",
                    "idle": "custom_idle.png",
                },
            )

    def test_default_durations(self):
        """Test to instanciate with default durations
        """
        with self.get_instance() as (vlc_player, _, _):
            # assert the instance
            self.assertDictEqual(vlc_player.durations, {"transition": 10, "idle": 20})

    def test_custom_durations(self):
        """Test to instanciate with custom durations
        """
        with self.get_instance({"durations": {"transition_duration": 5}}) as (
            vlc_player,
            _,
            _,
        ):
            # assert the instance
            self.assertDictEqual(vlc_player.durations, {"transition": 5, "idle": 20})

    @patch("dakara_player.media_player.base.PLAYER_CLOSING_DURATION", 0)
    @patch.object(MediaPlayerVlc, "stop_player")
    def test_slow_close(self, mocked_stop_player):
        """Test to close VLC when it takes a lot of time
        """
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
        """Test to generate invalid text screen
        """
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
        """Test to play invalid action
        """
        with self.get_instance() as (vlc_player, _, _):
            with self.assertRaisesRegex(ValueError, "Unexpected action to play: none"):
                vlc_player.play("none")

            vlc_player.player.play.assert_not_called()

    def test_set_window_none(self):
        """Test to use default window
        """
        with self.get_instance() as (vlc_player, _, _):
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.set_window(None)

            self.assertListEqual(
                logger.output,
                ["DEBUG:dakara_player.media_player.vlc:Using VLC default window"],
            )

    @patch("dakara_player.media_player.vlc.sys.platform", "linux")
    def test_set_window_linux(self):
        """Test to use X window
        """
        with self.get_instance() as (vlc_player, _, _):
            with self.assertLogs("dakara_player.media_player.vlc", "DEBUG") as logger:
                vlc_player.set_window(99)

            self.assertListEqual(
                logger.output,
                ["DEBUG:dakara_player.media_player.vlc:Associating X window to VLC"],
            )

    @patch("dakara_player.media_player.vlc.sys.platform", "win32")
    def test_set_window_windows(self):
        """Test to use Win API window
        """
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

    @patch("dakara_player.media_player.base.get_user_directory", autospec=True)
    @patch("dakara_player.media_player.vlc.sys.platform", "other")
    def test_set_window_other(self, mocked_get_user_directory):
        """Test to set window on unknown platform
        """
        with self.get_instance() as (vlc_player, _, _):
            with self.assertRaises(NotImplementedError):
                vlc_player.set_window(99)


@patch("dakara_player.media_player.vlc.METADATA_KEYS_COUNT", 10)
class SetMetadataTestCase(TestCase):
    """Test the set_metadata function"""

    def test_set_first(self):
        """Test to set metadata in first field"""
        media = MagicMock()
        media.get_meta.return_value = None

        set_metadata(media, {"data": "value"})

        media.set_meta.assert_called_with(0, '{"data": "value"}')

    def test_set_second(self):
        """Test to set metadata in second field"""
        media = MagicMock()
        media.get_meta.side_effect = ["value", None]

        set_metadata(media, {"data": "value"})

        media.set_meta.assert_called_with(1, '{"data": "value"}')

    def test_set_fail(self):
        """Test error when unable to set metadata in any field"""
        media = MagicMock()
        media.get_meta.return_value = "value"

        with self.assertRaises(ValueError):
            set_metadata(media, {"data": "value"})


@patch("dakara_player.media_player.vlc.METADATA_KEYS_COUNT", 10)
class GetMetadataTestCase(TestCase):
    """Test the get_metadata function"""

    def test_get_first(self):
        """Test to get metadata from first field"""
        media = MagicMock()
        media.get_meta.return_value = '{"data": "value"}'

        self.assertEqual(get_metadata(media), {"data": "value"})

    def test_get_second_none(self):
        """Test to get metadata from second field with first being none"""
        media = MagicMock()
        media.get_meta.side_effect = [None, '{"data": "value"}']

        self.assertEqual(get_metadata(media), {"data": "value"})

    def test_get_second_text(self):
        """Test to get metadata from second field with first being text"""
        media = MagicMock()
        media.get_meta.side_effect = ["value", '{"data": "value"}']

        self.assertEqual(get_metadata(media), {"data": "value"})

    def test_get_fail(self):
        """Test error when unable to get metadata from any field"""
        media = MagicMock()
        media.get_meta.return_value = "value"

        with self.assertRaises(ValueError):
            get_metadata(media)
