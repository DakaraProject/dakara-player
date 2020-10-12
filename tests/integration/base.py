from time import sleep
from unittest import TestCase


class TestCasePoller(TestCase):
    DELAY = 0.1

    @classmethod
    def wait_is_playing(cls, player, what=None):
        """Wait for the player to be playing or to play something specifically

        Use a polling loop. Note that after the condition is fulfilled, the
        function waits a little bit more.

        Args:
            player (dakara_player_vlc.media_player.MediaPlayer): Player.
            what (str): Action to wait for. If not provided, wait for the
                player to be actually playing.
        """
        if what:
            while not (player.is_playing() and player.is_playing(what)):
                sleep(cls.DELAY)

            sleep(cls.DELAY)

            return

        while not player.is_playing():
            sleep(cls.DELAY)

        sleep(cls.DELAY)

    @classmethod
    def wait_is_paused(cls, player):
        """Wait for the player to be paused

        Use a polling loop. Note that after the condition is fulfilled, the
        function waits a little bit more.

        Args:
            player (dakara_player_mpv.media_player.MediaPlayer): Player.
        """
        while not player.is_paused():
            sleep(cls.DELAY)

        sleep(cls.DELAY)
