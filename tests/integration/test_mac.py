import platform
from unittest import TestCase, skipUnless

from dakara_player.mac import get_brew_prefix, load_get_ns_view


@skipUnless(platform.system() == "Darwin", "Tested on Mac only")
class LoadGetNsViewIntegrationTestCase(TestCase):
    def test_load(self):
        """Test to load Tk and retrieve the function to get NSView."""
        # skip if the library is not installed
        if get_brew_prefix() is None:
            self.skipTest("Tested only if Tcl-Tk is installed with Brew")
            return

        function, found = load_get_ns_view()
        self.assertIsNotNone(function)
        self.assertTrue(found)
