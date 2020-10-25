from time import sleep
from unittest import TestCase


class TestCasePoller(TestCase):
    DELAY = 0.1

    @classmethod
    def wait_is_playing(cls, player, what=None, wait_extra=DELAY):
        """Wait for the player to be playing or to play something specifically

        Use a polling loop. Note that after the condition is fulfilled, the
        function waits a little bit more.

        Args:
            player (dakara_player_vlc.media_player.MediaPlayer): Player.
            what (str): Action to wait for. If not provided, wait for the
                player to be actually playing.
            wait_extra (float): Time to wait at the end of the function.
        """
        if what:
            while not (player.is_playing() and player.is_playing(what)):
                sleep(cls.DELAY)

        else:
            while not player.is_playing():
                sleep(cls.DELAY)

        sleep(wait_extra)

    @classmethod
    def wait_is_paused(cls, player, wait_extra=DELAY):
        """Wait for the player to be paused

        Use a polling loop. Note that after the condition is fulfilled, the
        function waits a little bit more.

        Args:
            player (dakara_player_mpv.media_player.MediaPlayer): Player.
            wait_extra (float): Time to wait at the end of the function.
        """
        while not player.is_paused():
            sleep(cls.DELAY)

        sleep(wait_extra)
