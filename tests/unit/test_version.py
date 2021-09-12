from unittest import TestCase
from unittest.mock import patch

from dakara_player.version import check_version


class CheckVersionTestCase(TestCase):
    """Test the version checker."""

    def test_check_version_release(self):
        """Test to display the version for a release."""
        with self.assertLogs("dakara_player.version", "DEBUG") as logger:
            with patch.multiple(
                "dakara_player.version", __version__="0.0.0", __date__="1970-01-01"
            ):
                check_version()

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            ["INFO:dakara_player.version:" "Dakara player 0.0.0 (1970-01-01)"],
        )

    def test_check_version_non_release(self):
        """Test to display the version for a non release."""
        with self.assertLogs("dakara_player.version", "DEBUG") as logger:
            with patch.multiple(
                "dakara_player.version", __version__="0.1.0-dev", __date__="1970-01-01",
            ):
                check_version()

        # assert effect on logs
        self.assertListEqual(
            logger.output,
            [
                "INFO:dakara_player.version:" "Dakara player 0.1.0-dev (1970-01-01)",
                "WARNING:dakara_player.version:"
                "You are running a dev version, use it at your own risks!",
            ],
        )
