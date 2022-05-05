import os
from subprocess import DEVNULL, CalledProcessError, CompletedProcess
from unittest import TestCase, skipUnless
from unittest.mock import patch

from path import Path

from dakara_player.mac import (
    check_brew,
    get_brew_prefix,
    get_tcl_tk_lib_path,
    load_get_ns_view,
)

POSIX = os.name == "posix"


@patch("dakara_player.mac.run")
class CheckBrewTestCase(TestCase):
    def test_check(self, mocked_run):
        """Test a positive call."""
        self.assertTrue(check_brew())

        mocked_run.assert_called_with(["brew"], stdout=DEVNULL, stderr=DEVNULL)

    def test_check_not_found(self, mocked_run):
        """Test a call with Brew not installed."""
        mocked_run.side_effect = FileNotFoundError()
        self.assertFalse(check_brew())


@skipUnless(POSIX, "Tested on POSIX system only")
@patch("dakara_player.mac.run")
class GetBrewPrefixTestCase(TestCase):
    def test_get(self, mocked_run):
        """Test to get a prefix."""
        mocked_run.return_value = CompletedProcess(
            args="brew", returncode=0, stdout="/path/to/formula\n"
        )
        self.assertEqual(
            get_brew_prefix("formula"), Path("/") / "path" / "to" / "formula"
        )

        mocked_run.assert_called_with(
            ["brew", "--prefix", "formula"], capture_output=True, check=True, text=True
        )

    def test_get_fail(self, mocked_run):
        """Test to get the prefix of a formula that does not exist."""
        mocked_run.side_effect = CalledProcessError(
            returncode=255, cmd="brew --prefix formula"
        )
        self.assertIsNone(get_brew_prefix("formula"))

    def test_get_not_found(self, mocked_run):
        """Test to get the prefix of a formula when Brew is not installed."""
        mocked_run.side_effect = FileNotFoundError()
        self.assertIsNone(get_brew_prefix("formula"))


@skipUnless(POSIX, "Tested on POSIX system only")
@patch("dakara_player.mac.get_brew_prefix")
@patch("dakara_player.mac.check_brew")
class GetTclTkLibPathTestCase(TestCase):
    def test_get_environ(self, mocked_check_brew, mocked_get_brew_prefix):
        """Test to get lib from environment variable."""
        with patch.dict(
            "dakara_player.mac.os.environ",
            {"TK_LIBRARY_PATH": "/path/to/formula/lib"},
            clear=True,
        ):
            self.assertEqual(
                get_tcl_tk_lib_path(), Path("/") / "path" / "to" / "formula" / "lib"
            )

        mocked_check_brew.assert_not_called()
        mocked_get_brew_prefix.assert_not_called()

    def test_get_brew(self, mocked_check_brew, mocked_get_brew_prefix):
        """Test to get lib from Brew."""
        mocked_check_brew.return_value = True
        mocked_get_brew_prefix.return_value = Path("/") / "path" / "to" / "formula"

        with patch.dict(
            "dakara_player.mac.os.environ",
            {},
            clear=True,
        ):
            self.assertEqual(
                get_tcl_tk_lib_path(), Path("/") / "path" / "to" / "formula" / "lib"
            )

    def test_get_no_brew(self, mocked_check_brew, mocked_get_brew_prefix):
        """Test when Brew is not available."""
        mocked_check_brew.return_value = False

        with patch.dict(
            "dakara_player.mac.os.environ",
            {},
            clear=True,
        ):
            self.assertIsNone(get_tcl_tk_lib_path())

        mocked_get_brew_prefix.assert_not_called()

    def test_get_brew_no_prefix(self, mocked_check_brew, mocked_get_brew_prefix):
        """Test when Brew formula does not exist."""
        mocked_check_brew.return_value = True
        mocked_get_brew_prefix.return_value = None

        with patch.dict(
            "dakara_player.mac.os.environ",
            {},
            clear=True,
        ):
            self.assertIsNone(get_tcl_tk_lib_path())


@skipUnless(POSIX, "Tested on POSIX system only")
@patch("dakara_player.mac.sys.base_prefix", "/usr")
@patch("dakara_player.mac.tkinter.TkVersion", "0.0")
@patch("dakara_player.mac.cdll")
@patch("dakara_player.mac.get_tcl_tk_lib_path")
class LoadGetNsViewTestCase(TestCase):
    def test_load_standard(self, mocked_get_tcl_tk_lib_path, mocked_cdll):
        """Test load from standard location."""
        mocked_get_tcl_tk_lib_path.return_value = None
        function, found = load_get_ns_view()
        self.assertIsNotNone(function)
        self.assertTrue(found)
        mocked_cdll.LoadLibrary.assert_called_with("/usr/lib/libtk0.0.dylib")

    def test_load_custom(self, mocked_get_tcl_tk_lib_path, mocked_cdll):
        """Test load from custom location."""
        mocked_get_tcl_tk_lib_path.return_value = Path("/") / "path" / "to" / "lib"
        function, found = load_get_ns_view()
        self.assertIsNotNone(function)
        self.assertTrue(found)
        mocked_cdll.LoadLibrary.assert_called_with("/path/to/lib/libtk0.0.dylib")

    def test_load_fail(self, mocked_get_tcl_tk_lib_path, mocked_cdll):
        """Test load from custom location."""
        mocked_get_tcl_tk_lib_path.return_value = None
        mocked_cdll.LoadLibrary.side_effect = OSError()
        function, found = load_get_ns_view()
        self.assertIsNotNone(function)
        self.assertIsNone(function(None))
        self.assertFalse(found)
