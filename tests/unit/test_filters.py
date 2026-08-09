from unittest import TestCase

from dakara_player.filters import filter_duration


class FilterDurationTestCase(TestCase):
    def test_filter_duration(self):
        """Test to filter durations."""
        self.assertEqual(filter_duration(42), "0:42")
        self.assertEqual(filter_duration(425), "7:05")
        self.assertEqual(filter_duration(738), "12:18")
        self.assertEqual(filter_duration(3618), "1:00:18")

    def test_filter_duration_undefined(self):
        """Test to filter undefined durations."""
        self.assertEqual(filter_duration(None), "")
        self.assertEqual(filter_duration("undefined"), "undefined")
