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
            player (dakara_player.media_player.MediaPlayer): Player.
            what (str): Action to wait for. If not provided, wait for the
                player to be actually playing.
            wait_extra (float): Time to wait at the end of the function.
        """
        if what:
            cls.wait(lambda: player.is_playing() and player.is_playing(what))

        else:
            cls.wait(lambda: player.is_playing())

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
