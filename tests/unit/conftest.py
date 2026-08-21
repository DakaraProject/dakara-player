from pathlib import Path
from unittest.mock import patch

import pytest

from dakara_player.media_player.base import MediaPlayerEntry
from tests.utils import get_temp_dir


@pytest.fixture
def playlist_entry():
    return {
        "id": 42,
        "song": {
            "title": "Song title",
            "file_path": "file.mkv",
            "instrumental_file": None,
            "instrumental_track": None,
        },
        "owner": "me",
        "use_instrumental": False,
    }


@pytest.fixture
def backgrounds():
    return {"transition": Path("/transition.png")}


@pytest.fixture
def durations():
    return {"transition": 10}


@pytest.fixture
def text_screens():
    return {"transition": Path("/transition.ass")}


@pytest.fixture
def media_player_entry(playlist_entry, backgrounds, durations, text_screens):
    entry = MediaPlayerEntry(get_temp_dir(), playlist_entry)

    entry.load(backgrounds, durations, text_screens)
    return entry


@pytest.fixture
def media_player_entry_instrumental_file(
    playlist_entry, backgrounds, durations, text_screens
):
    playlist_entry["use_instrumental"] = True
    playlist_entry["song"]["instrumental_file"] = "file.mka"

    with patch.object(Path, "exists", return_value=True, autospec=True):
        entry = MediaPlayerEntry(get_temp_dir(), playlist_entry)
        entry.load(backgrounds, durations, text_screens)

    return entry


@pytest.fixture
def media_player_entry_instrumental_track(
    playlist_entry, backgrounds, durations, text_screens
):
    playlist_entry["use_instrumental"] = True
    playlist_entry["song"]["instrumental_track"] = 1

    entry = MediaPlayerEntry(get_temp_dir(), playlist_entry)

    entry.load(backgrounds, durations, text_screens)
    return entry
