from time import sleep
from unittest import TestCase

try:
    from importlib.resources import path

except ImportError:
    from importlib_resources import path

from path import Path, TempDir


class TestCasePoller(TestCase):
    """Test class that can poll the state of tested player
    """

    DELAY = 0.1

    @classmethod
    def wait_is_playing(cls, player, what=None, wait_extra=DELAY):
        """Wait for the player to be playing or to play something specifically

        Use a polling loop. Note that after the condition is fulfilled, the
        function waits a little bit more.

        Args:
            player (dakara_player.media_player.base.MediaPlayer): Player.
            what (str): Action to wait for. If not provided, wait for the
                player to be actually playing.
            wait_extra (float): Time to wait at the end of the function.
        """
        if what:
            cls.wait(lambda: player.is_playing() and player.is_playing_this(what))

        else:
            cls.wait(lambda: player.is_playing())

        sleep(wait_extra)

    @classmethod
    def wait_is_paused(cls, player, wait_extra=DELAY):
        """Wait for the player to be paused

        Use a polling loop. Note that after the condition is fulfilled, the
        function waits a little bit more.

        Args:
            player (dakara_player.media_player.base.MediaPlayer): Player.
            wait_extra (float): Time to wait at the end of the function.
        """
        cls.wait(lambda: player.is_paused())

        sleep(wait_extra)

    @classmethod
    def wait(cls, condition_method):
        """Wait for a condition to be true safely

        Args:
            condition_method (function): Function to call in loop in a try/except
                structure, so as to not break the loop in cause of error.
        """
        while True:
            try:
                if condition_method():
                    return

            except OSError:
                pass

            sleep(cls.DELAY)


class TestCaseKara(TestCase):
    """Test class that creates a working kara folder
    """

    def setUp(self):
        # create kara folder
        self.kara_folder = TempDir()

        # create subtitle
        with path("tests.resources", "song1.ass") as file:
            self.subtitle1_path = Path(file).copy(self.kara_folder)

        with path("tests.resources", "song2.ass") as file:
            self.subtitle2_path = Path(file).copy(self.kara_folder)

        # create song
        with path("tests.resources", "song1.mkv") as file:
            self.song1_path = Path(file).copy(self.kara_folder)

        with path("tests.resources", "song2.mkv") as file:
            self.song2_path = Path(file).copy(self.kara_folder)

        with path("tests.resources", "song3.avi") as file:
            self.song3_path = Path(file).copy(self.kara_folder)

        # create audio
        with path("tests.resources", "song2.mp3") as file:
            self.audio2_path = Path(file).copy(self.kara_folder)

        # create playlist entry
        self.playlist_entry1 = {
            "id": 42,
            "song": {"title": "Song 1", "file_path": self.song1_path},
            "owner": "me",
            "use_instrumental": False,
        }

        self.playlist_entry2 = {
            "id": 43,
            "song": {"title": "Song 2", "file_path": self.song2_path},
            "owner": "me",
            "use_instrumental": False,
        }

        self.playlist_entry3 = {
            "id": 44,
            "song": {"title": "Song 3", "file_path": self.song3_path},
            "owner": "me",
            "use_instrumental": False,
        }

    def tearDown(self):
        self.kara_folder.rmtree(ignore_errors=True)


class TestCasePollerKara(TestCasePoller, TestCaseKara):
    """Test class that polls player and create kara folder
    """
