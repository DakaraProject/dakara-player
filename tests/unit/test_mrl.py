import sys
from pathlib import Path
from unittest import TestCase, skipIf

from dakara_player.mrl import mrl_to_path, path_to_mrl


class MrlFunctionsTestCase(TestCase):
    """Test the MRL conversion functions."""

    is_windows = sys.platform.startswith("win")

    @skipIf(is_windows, "Tested on POSIX")
    def test_mrl_to_path_posix(self):
        """Test to convert MRL to path for POSIX."""
        path = mrl_to_path("file:///home/username/directory/file%20name.ext")
        self.assertEqual(
            path, Path("/home").resolve() / "username" / "directory" / "file name.ext"
        )

    @skipIf(not is_windows, "Tested on Windows")
    def test_mrl_to_path_windows(self):
        """Test to convert MRL to path for Windows."""
        path = mrl_to_path("file:///C:/Users/username/directory/file%20name.ext")
        self.assertEqual(
            path,
            Path("C:/Users").resolve() / "username" / "directory" / "file name.ext",
        )

    @skipIf(is_windows, "Tested on POSIX")
    def test_path_to_mrl_posix(self):
        """Test to convert path to MRL for POSIX."""
        mrl = path_to_mrl(
            Path("/home").resolve() / "username" / "directory" / "file name.ext"
        )
        self.assertEqual(mrl, "file:///home/username/directory/file%20name.ext")

    @skipIf(not is_windows, "Tested on Windows")
    def test_path_to_mrl_windows(self):
        """Test to convert path to MRL for Windows."""
        mrl = path_to_mrl(
            Path("C:/Users").resolve() / "username" / "directory" / "file name.ext"
        )
        self.assertEqual(mrl, "file:///C:/Users/username/directory/file%20name.ext")
