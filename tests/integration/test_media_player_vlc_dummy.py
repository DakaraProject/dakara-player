from importlib.resources import as_file, files
from pathlib import Path
from shutil import copy

import pytest

from dakara_player.media_player import vlc_dummy
from dakara_player.media_player.vlc_check import is_vlc_available

if is_vlc_available():
    import vlc

else:
    pytest.skip("VLC not installed", allow_module_level=True)


def test_version():
    assert vlc.libvlc_get_version() is not None
    assert vlc_dummy.libvlc_get_version() is not None


@pytest.fixture
def file(tmpdir) -> str:
    with as_file(files("tests.resources").joinpath("song1.mkv")) as res:
        yield Path(copy(res, tmpdir)).as_uri()


@pytest.fixture
def file_audio(tmpdir) -> str:
    with as_file(files("tests.resources").joinpath("song2.mp3")) as res:
        yield Path(copy(res, tmpdir)).as_uri()


@pytest.fixture
def instance() -> vlc.Instance:
    return vlc.Instance()


@pytest.fixture
def instance_dummy() -> vlc_dummy.Instance:
    return vlc_dummy.Instance()


class TestInstance:
    def test_create_no_parameters(self):
        """Test to create instance without arguments."""
        assert vlc.Instance() is not None
        assert vlc_dummy.Instance() is not None

    def test_create_parameters(self):
        """Test to create instance with arguments."""
        assert (
            vlc.Instance(
                "--vout=vdummy",
                "--aout=adummy",
                "--text-renderer=tdummy",
            )
            is not None
        )
        assert (
            vlc_dummy.Instance(
                "--vout=vdummy",
                "--aout=adummy",
                "--text-renderer=tdummy",
            )
            is not None
        )

    def test_create_player_new(self, instance, instance_dummy):
        """Test to get a player."""
        assert instance.media_player_new() is not None
        assert instance_dummy.media_player_new() is not None


@pytest.fixture
def media(file) -> vlc.Media:
    return vlc.Media(file)


@pytest.fixture
def media_dummy(file) -> vlc_dummy.Media:
    return vlc_dummy.Media(file)


class TestMedia:
    def test_create_no_parameters(self, file):
        """Test to create media without arguments."""
        assert vlc.Media(file) is not None
        assert vlc_dummy.Media(file) is not None

    def test_create_parameters(self, file):
        """Test to create media with arguments."""
        assert (
            vlc.Media(
                file,
                "image-duration=10",
                "sub-file=/subtitle",
                "no-subautodetect-file",
            )
            is not None
        )
        assert (
            vlc_dummy.Media(
                file,
                "image-duration=10",
                "sub-file=/subtitle",
                "no-subautodetect-file",
            )
            is not None
        )

    def test_meta(self, media, media_dummy):
        """Test to set and get metadata."""
        media.set_meta(1, "test")
        media_dummy.set_meta(1, "test")

        assert media.get_meta(1) == "test"
        assert media_dummy.get_meta(1) == "test"

    def test_duration(self, media, media_dummy):
        """Test to get duration."""
        assert media.get_duration() == -1
        assert media_dummy.get_duration() == -1

    def test_mrl(self, file, media, media_dummy):
        """Test to get MRL."""
        assert media.get_mrl() == file
        assert media_dummy.get_mrl() == file

    def test_tracks(self, media, media_dummy):
        """Test to get tracks."""
        media.parse()
        media_dummy.parse()

        assert len(list(media.tracks_get())) == 4
        assert len(list(media_dummy.tracks_get())) == 4

        assert [item.id for item in media.tracks_get()] == [0, 1, 2, 3]
        assert [item.id for item in media_dummy.tracks_get()] == [0, 1, 2, 3]

        assert [item.type for item in media.tracks_get()] == [
            vlc.TrackType.video,
            vlc.TrackType.audio,
            vlc.TrackType.audio,
            vlc.TrackType.ext,
        ]
        assert [item.type for item in media_dummy.tracks_get()] == [
            vlc_dummy.TrackType.video,
            vlc_dummy.TrackType.audio,
            vlc_dummy.TrackType.audio,
            vlc_dummy.TrackType.ext,
        ]

    def test_slaves(self, file_audio, media, media_dummy):
        """Test to add slaves."""
        media.slaves_add(
            vlc.MediaSlaveType.audio,
            4,
            file_audio,
        )
        media_dummy.slaves_add(
            vlc_dummy.MediaSlaveType.audio,
            4,
            file_audio,
        )


def test_meta_length():
    """Test length of meta fields."""
    assert len(vlc.Meta.__dict__["_enum_names_"]) >= 3
    assert len(vlc_dummy.Meta.__dict__["_enum_names_"]) >= 3


@pytest.fixture
def media_player(instance) -> vlc.MediaPlayer:
    return instance.media_player_new()


@pytest.fixture
def media_player_dummy(instance_dummy) -> vlc_dummy.MediaPlayer:
    return instance_dummy.media_player_new()


class TestMediaPlayer:
    def test_event_manager(self, media_player, media_player_dummy):
        """Test to get an event manager."""
        assert media_player.event_manager() is not None
        assert media_player_dummy.event_manager() is not None

    def test_time(self, media_player, media_player_dummy):
        """Test to get and set time."""
        assert media_player.get_time() == -1
        assert media_player_dummy.get_time() == -1

        media_player.set_time(1)
        media_player_dummy.set_time(1)

    def test_state(self, media_player, media_player_dummy):
        """Test to get state."""
        assert media_player.get_state() == vlc.State.NothingSpecial
        assert media_player_dummy.get_state() == vlc_dummy.State.NothingSpecial

    def test_media(self, media_player, media_player_dummy, media, media_dummy):
        """Test to get and set media."""
        assert media_player.get_media() is None
        assert media_player_dummy.get_media() is None

        media_player.set_media(media)
        media_player_dummy.set_media(media_dummy)

        assert media_player.get_media().get_mrl() == media.get_mrl()
        assert media_player_dummy.get_media().get_mrl() == media_dummy.get_mrl()

    def test_play(self, media_player_dummy):
        """Test that playback functions cannot be used, for the dummy interface
        only"""
        with pytest.raises(vlc_dummy.DummyVlcUsedError):
            media_player_dummy.play()

        with pytest.raises(vlc_dummy.DummyVlcUsedError):
            media_player_dummy.pause()

        with pytest.raises(vlc_dummy.DummyVlcUsedError):
            media_player_dummy.stop()

    def test_window(self, media_player_dummy):
        """Test that window functions cannot be used, for the dummy interface
        only"""
        with pytest.raises(vlc_dummy.DummyVlcUsedError):
            media_player_dummy.set_xwindow(0)

        with pytest.raises(vlc_dummy.DummyVlcUsedError):
            media_player_dummy.set_hwnd(0)

    def test_audio_track(self, media_player, media_player_dummy):
        """Test to set the audio track."""
        media_player.audio_set_track(1)
        media_player_dummy.audio_set_track(1)


@pytest.fixture
def event_manager(media_player) -> vlc.EventManager:
    return media_player.event_manager()


@pytest.fixture
def event_manager_dummy(media_player_dummy) -> vlc_dummy.EventManager:
    return media_player_dummy.event_manager()


def dummy_callback(*args, **kwargs) -> None:
    pass


class TestEventManager:
    def test_attach(self, event_manager, event_manager_dummy):
        """Test to attach a callback to an event."""
        event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, dummy_callback)
        event_manager_dummy.event_attach(
            vlc_dummy.EventType.MediaPlayerEndReached, dummy_callback
        )
