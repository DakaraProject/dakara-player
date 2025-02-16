from importlib.resources import as_file, files
from pathlib import Path
from queue import Empty
from shutil import copy
from tempfile import TemporaryDirectory
from time import sleep
from unittest import TestCase


class TestCasePoller(TestCase):
    """Test class that can poll the state of tested player."""

    DELAY = 0.1

    @classmethod
    def wait_is_playing(cls, player, what=None, wait_extra=DELAY):
        """Wait for the player to be playing or to play something specifically.

        Use a polling loop. Note that after the condition is fulfilled, the
        function waits a little bit more.

        Args:
            player (dakara_player.media_player.base.MediaPlayer): Player.
            what (str): Action to wait for. If not provided, wait for the
                player to be actually playing.
            wait_extra (float): Time to wait at the end of the function.
        """
        if what:
            cls.wait(
                player, lambda: player.is_playing() and player.is_playing_this(what)
            )

        else:
            cls.wait(player, lambda: player.is_playing())

        sleep(wait_extra)

    @classmethod
    def wait_is_paused(cls, player, wait_extra=DELAY):
        """Wait for the player to be paused.

        Use a polling loop. Note that after the condition is fulfilled, the
        function waits a little bit more.

        Args:
            player (dakara_player.media_player.base.MediaPlayer): Player.
            wait_extra (float): Time to wait at the end of the function.
        """
        cls.wait(player, lambda: player.is_paused())

        sleep(wait_extra)

    @classmethod
    def wait(cls, player, condition_method):
        """Wait for a condition to be true safely.

        Args:
            condition_method (function): Function to call in loop in a try/except
                structure, so as to not break the loop in cause of error.
        """
        while True:
            # handle any player error
            if player.stop.is_set():
                try:
                    _, error, traceback = player.errors.get(5)
                    error.with_traceback(traceback)
                    raise error

                except Empty as error_empty:
                    raise RuntimeError("Unexpected error happened") from error_empty

            try:
                if condition_method():
                    return

            except OSError:
                pass

            sleep(cls.DELAY)


class TestCaseKara(TestCase):
    """Test class that creates a working kara folder."""

    def setUp(self):
        # create kara folder
        self.kara_folder = TemporaryDirectory()
        # resolve to prevent DOS short paths on Windows CI
        self.kara_folder_path = Path(self.kara_folder.name).resolve()

        # create subtitle
        with as_file(files("tests.resources").joinpath("song1.ass")) as file:
            self.subtitle1_path = Path(copy(file, self.kara_folder_path))

        with as_file(files("tests.resources").joinpath("song2.ass")) as file:
            self.subtitle2_path = Path(copy(file, self.kara_folder_path))

        # create song
        with as_file(files("tests.resources").joinpath("song1.mkv")) as file:
            self.song1_path = Path(copy(file, self.kara_folder_path))

        with as_file(files("tests.resources").joinpath("song2.mkv")) as file:
            self.song2_path = Path(copy(file, self.kara_folder_path))

        with as_file(files("tests.resources").joinpath("song3.avi")) as file:
            self.song3_path = Path(copy(file, self.kara_folder_path))

        # create audio
        with as_file(files("tests.resources").joinpath("song2.mp3")) as file:
            self.audio2_path = Path(copy(file, self.kara_folder_path))

        # create playlist entry
        self.playlist_entry1 = {
            "id": 42,
            "song": {
                "title": "Song 1",
                "file_path": str(self.song1_path),
                "duration": 60,
            },
            "owner": "me",
            "use_instrumental": False,
        }

        self.playlist_entry2 = {
            "id": 43,
            "song": {
                "title": "Song 2",
                "file_path": str(self.song2_path),
                "duration": 60,
            },
            "owner": "me",
            "use_instrumental": False,
        }

        self.playlist_entry3 = {
            "id": 44,
            "song": {
                "title": "Song 3",
                "file_path": str(self.song3_path),
                "duration": 60,
            },
            "owner": "me",
            "use_instrumental": False,
        }

    def tearDown(self):
        self.kara_folder.cleanup()


class TestCasePollerKara(TestCasePoller, TestCaseKara):
    """Test class that polls player and create kara folder."""
