import logging
from pathlib import Path

from dakara_player.media_player.base import MediaPlayerEntry


class TestMediaPlayerEntry:
    def test_create(self, playlist_entry):
        """Test to create an instance."""
        entry = MediaPlayerEntry(Path("/kara/folder"), playlist_entry)

        assert entry is not None
        assert not entry.is_loaded()
        assert entry.id == playlist_entry["id"]
        assert entry.title == playlist_entry["song"]["title"]

    def test_load(self, playlist_entry, backgrounds, durations, text_screens):
        """Test to load a created instance."""
        entry = MediaPlayerEntry(Path("/kara/folder"), playlist_entry)

        assert not entry.is_loaded()

        entry.load(backgrounds, durations, text_screens)

        assert entry is not None
        assert entry.is_loaded()
        assert len(entry.items.keys()) == 2
        assert "transition" in entry.items
        assert "song" in entry.items

    def test_get_transition(self, playlist_entry, backgrounds, durations, text_screens):
        """Test to get a transition."""

        entry = MediaPlayerEntry(Path("/kara/folder"), playlist_entry)
        transition = entry.get_transition(backgrounds, durations, text_screens)

        assert transition is not None
        assert transition.path == Path("/transition.png")
        assert transition.subtitle_path == Path("/transition.ass")
        assert transition.duration == 10

    def test_get_song(self, playlist_entry):
        """Test to get a song."""
        entry = MediaPlayerEntry(Path("/kara/folder"), playlist_entry)
        song = entry.get_song()

        assert song is not None
        assert song.path == Path("/kara/folder/file.mkv")
        assert song.instrumental_track is None
        assert song.instrumental_path is None

    def test_get_song_instrumental_file(self, playlist_entry, mocker, caplog):
        """Test to get a song with instrumental file."""
        playlist_entry["use_instrumental"] = True
        playlist_entry["song"]["instrumental_file"] = "file.mka"

        mocker.patch.object(Path, "exists", return_value=True, autospec=True)

        caplog.set_level(logging.INFO)

        entry = MediaPlayerEntry(Path("/kara/folder"), playlist_entry)
        song = entry.get_song()

        assert song.instrumental_path == Path("/kara/folder/file.mka")
        assert caplog.record_tuples == [
            (
                "dakara_player.media_player.base",
                logging.INFO,
                "Requesting instrumental version of file '/kara/folder/file.mkv'",
            ),
            (
                "dakara_player.media_player.base",
                logging.INFO,
                "Requesting to play instrumental file '/kara/folder/file.mka'",
            ),
        ]

    def test_get_song_instrumental_file_no_file(self, playlist_entry, mocker, caplog):
        """Test to get a song with instrumental file when the file does not
        exist."""
        playlist_entry["use_instrumental"] = True
        playlist_entry["song"]["instrumental_file"] = "file.mka"

        caplog.set_level(logging.INFO)

        mocker.patch.object(Path, "exists", return_value=False, autospec=True)

        entry = MediaPlayerEntry(Path("/kara/folder"), playlist_entry)
        song = entry.get_song()

        assert song.instrumental_path is None
        assert caplog.record_tuples == [
            (
                "dakara_player.media_player.base",
                logging.INFO,
                "Requesting instrumental version of file '/kara/folder/file.mkv'",
            ),
            (
                "dakara_player.media_player.base",
                logging.INFO,
                "Requesting to play instrumental file '/kara/folder/file.mka'",
            ),
            (
                "dakara_player.media_player.base",
                logging.ERROR,
                "Unable to find requested instrumental file '/kara/folder/file.mka'",
            ),
            (
                "dakara_player.media_player.base",
                logging.WARNING,
                "No instrumental version available of file '/kara/folder/file.mkv'",
            ),
        ]

    def test_get_song_instrumental_track(self, playlist_entry, caplog):
        """Test to get a song with instrumental track."""
        playlist_entry["use_instrumental"] = True
        playlist_entry["song"]["instrumental_track"] = 1

        caplog.set_level(logging.DEBUG)

        entry = MediaPlayerEntry(Path("/kara/folder"), playlist_entry)
        song = entry.get_song()

        assert song.instrumental_track == 1
        assert caplog.record_tuples == [
            (
                "dakara_player.media_player.base",
                logging.INFO,
                "Requesting instrumental version of file '/kara/folder/file.mkv'",
            ),
            (
                "dakara_player.media_player.base",
                logging.INFO,
                "Requesting to play instrumental track 1",
            ),
        ]

    def test_get_song_instrumental_no_fields(self, playlist_entry, caplog):
        """Test to get a song with instrumental file or track when the field is
        missing."""
        playlist_entry["use_instrumental"] = True

        caplog.set_level(logging.INFO)

        entry = MediaPlayerEntry(Path("/kara/folder"), playlist_entry)
        song = entry.get_song()

        assert song.instrumental_path is None
        assert song.instrumental_track is None
        assert caplog.record_tuples == [
            (
                "dakara_player.media_player.base",
                logging.INFO,
                "Requesting instrumental version of file '/kara/folder/file.mkv'",
            ),
            (
                "dakara_player.media_player.base",
                logging.WARNING,
                "No instrumental version available of file '/kara/folder/file.mkv'",
            ),
        ]
