"""Dummy module that replaces VLC for unit tests when VLC is not installed."""

from dataclasses import InitVar, dataclass, field
from enum import IntEnum
from typing import ByteString, Callable
from warnings import warn

from dakara_base.exceptions import DakaraError

VLC_DUMMY_INTERFACE = True


def display_module_warning() -> None:
    warn(
        "Using the dummy interface of VLC, as VLC seems to not be installed on "
        "your system. This is fine for unit testing but will crash for any "
        "other use.",
        stacklevel=2,
    )


def libvlc_get_version() -> ByteString:
    return "0.0.0 Mocked".encode("utf-8")


class EventType(IntEnum):
    MediaPlayerEndReached = 0
    MediaPlayerEncounteredError = 1
    MediaPlayerPlaying = 2
    MediaPlayerPaused = 3


class State(IntEnum):
    Playing = 0
    Paused = 1
    NothingSpecial = 2


class MediaSlaveType(IntEnum):
    video = 0
    audio = 1


class TrackType(IntEnum):
    video = 0
    audio = 1
    ext = 3


@dataclass
class Track:
    id: int
    type: TrackType


@dataclass
class Media:
    mrl: str
    parameter_0: InitVar[str | None] = None
    parameter_1: InitVar[str | None] = None
    parameter_2: InitVar[str | None] = None
    parameter_3: InitVar[str | None] = None
    parameters: list[str] = field(init=False)
    meta: list[str | None] = field(init=False)

    def __post_init__(self, parameter_0, parameter_1, parameter_2, parameter_3):
        self.parameters = [parameter_0, parameter_1, parameter_2, parameter_3]
        self.meta = ["media", None, None]

    def set_meta(self, key: int, value: str) -> None:
        self.meta[key] = value

    def get_meta(self, key: int) -> str | None:
        return self.meta[key]

    def get_duration(self) -> int:
        return -1

    def get_mrl(self) -> str:
        return self.mrl

    def tracks_get(self) -> list[Track]:
        return [
            Track(0, TrackType.video),
            Track(1, TrackType.audio),
            Track(2, TrackType.audio),
            Track(3, TrackType.ext),
        ]

    def parse(self) -> None:
        pass

    def slaves_add(self, media_type: MediaSlaveType, priority: int, uri: str) -> None:
        pass


class Meta:
    _enum_names_ = {0: "", 1: "", 2: ""}


@dataclass
class Instance:
    parameter_0: InitVar[str | None] = None
    parameter_1: InitVar[str | None] = None
    parameter_2: InitVar[str | None] = None
    parameter_3: InitVar[str | None] = None
    parameters: list[str] = field(init=False)

    def __post_init__(self, parameter_0, parameter_1, parameter_2, parameter_3):
        self.parameters = [parameter_0, parameter_1, parameter_2, parameter_3]

    def media_player_new(self) -> "MediaPlayer":
        return MediaPlayer()


class MediaPlayer:
    media: Media | None = None

    def event_manager(self) -> "EventManager":
        return EventManager()

    def get_time(self) -> int:
        return -1

    def set_time(self, time: int) -> None:
        pass

    def get_state(self) -> State:
        return State.NothingSpecial

    def get_media(self) -> Media | None:
        return self.media

    def set_media(self, media: Media) -> None:
        self.media = media

    def play(self) -> None:
        raise DummyVlcUsedError("The dummy VLC interface cannot be used!")

    def pause(self) -> None:
        raise DummyVlcUsedError("The dummy VLC interface cannot be used!")

    def stop(self) -> None:
        raise DummyVlcUsedError("The dummy VLC interface cannot be used!")

    def audio_set_track(self, track: int) -> None:
        pass

    def set_xwindow(self, id: int) -> None:
        pass

    def set_hwnd(self, id: int) -> None:
        pass


@dataclass
class EventManager:
    events: dict[EventType, Callable] = field(init=False, default_factory=dict)

    def event_attach(self, event: EventType, callback: Callable):
        self.events[event] = callback


class DummyVlcUsedError(DakaraError):
    """Error raised when trying to use the dummy VLC interface."""
