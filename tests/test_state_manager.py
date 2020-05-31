from unittest import TestCase

from dakara_player_vlc.state_manager import State


class StateTestCase(TestCase):
    def test(self):
        state = State()

        self.assertFalse(state.has_started())
        self.assertFalse(state.has_finished())
        self.assertFalse(state.is_active())

        state.start()

        self.assertTrue(state.has_started())
        self.assertFalse(state.has_finished())
        self.assertTrue(state.is_active())

        state.finish()

        self.assertTrue(state.has_started())
        self.assertTrue(state.has_finished())
        self.assertFalse(state.is_active())

        state.reset()

        self.assertFalse(state.has_started())
        self.assertFalse(state.has_finished())
        self.assertFalse(state.is_active())
