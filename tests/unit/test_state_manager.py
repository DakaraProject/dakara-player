from unittest import TestCase

from dakara_player_vlc.state_manager import State


class StateTestCase(TestCase):
    """Test the State class
    """

    def test_use(self):
        """Test to use a state
        """
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

    def test_repr(self):
        """Test to stringify a state
        """
        state = State()

        self.assertEqual(
            repr(state), "<State started: False, finished: False, active: False>"
        )

        state.start()

        self.assertEqual(
            repr(state), "<State started: True, finished: False, active: True>"
        )

        state.finish()

        self.assertEqual(
            repr(state), "<State started: True, finished: True, active: False>"
        )

        state.reset()

        self.assertEqual(
            repr(state), "<State started: False, finished: False, active: False>"
        )

    def test_finished_too_early(self):
        """Test to finish a state before starting it
        """
        state = State()
        with self.assertRaisesRegex(AssertionError, "The state must have started"):
            state.finish()
