from unittest import TestCase

from dakara_player.filters import filter_duration_hhmm, filter_duration_ss


class FilterDurationHhMmTestCase(TestCase):
    def test_filter_duration(self):
        """Test to filter durations."""
        self.assertEqual(filter_duration_hhmm(42), "0")
        self.assertEqual(filter_duration_hhmm(425), "7")
        self.assertEqual(filter_duration_hhmm(738), "12")
        self.assertEqual(filter_duration_hhmm(3618), "1:00")

    def test_filter_duration_undefined(self):
        """Test to filter undefined durations."""
        self.assertEqual(filter_duration_hhmm(None), "")
        self.assertEqual(filter_duration_hhmm("undefined"), "undefined")


class FilterDurationSsTestCase(TestCase):
    def test_filter_duration(self):
        """Test to filter durations."""
        self.assertEqual(filter_duration_ss(42), ":42")
        self.assertEqual(filter_duration_ss(425), ":05")
        self.assertEqual(filter_duration_ss(738), ":18")
        self.assertEqual(filter_duration_ss(3618), ":18")

    def test_filter_duration_undefined(self):
        """Test to filter undefined durations."""
        self.assertEqual(filter_duration_ss(None), "")
        self.assertEqual(filter_duration_ss("undefined"), "undefined")
