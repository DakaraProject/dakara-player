import os
import sys
import tkinter
from ctypes import c_void_p, cdll
from subprocess import DEVNULL, CalledProcessError, check_call, run

from path import Path

TK_LIBRARY_PATH = "TK_LIBRARY_PATH"
BREW = "brew"
BREW_PREFIX = "--prefix"
LIB = "lib"


def check_brew():
    """Check Brew exists.

    Returns:
        bool: `True` if Brew is available, `False` otherwise.
    """
    try:
        check_call([BREW], stdout=DEVNULL, stderr=DEVNULL)
        return True

    except (CalledProcessError, FileNotFoundError):
        return False


def get_brew_prefix(formula):
    """Get the prefix of a Brew formula.

    Args:
        formula (str): Brew formula.

    Returns:
        path.Path: Path of the formula prefix. `None` if the prefix cannot be
        obtained.
    """
    try:
        outcome = run(
            [BREW, BREW_PREFIX, str(formula)],
            capture_output=True,
            check=True,
            text=True,
        )

    except (CalledProcessError, FileNotFoundError):
        return None

    return Path(outcome.stdout.strip())


def get_tcl_tk_lib_path():
    """Retrieve the location of Tcl Tk library.

    The location can be obtained either from the environment variable
    `TK_LIBRARY_PATH`, or from Brew.

    Returns:
        path.Path: Path of Tck Tk library. `None` if it can't be found.
    """
    # if the TK_LIBRARY_PATH environment variable exists, use it
    if TK_LIBRARY_PATH in os.environ:
        return Path(os.environ[TK_LIBRARY_PATH])

    # if Brew is not installed, don't do anything
    if not check_brew():
        return None

    # try to obtain the location of tk
    prefix = get_brew_prefix("tcl-tk")
    if prefix is None:
        return None

    return prefix / LIB


def load_get_ns_view():
    """Load the function to get NSView.

    Load Tk library for Mac.

    See:
        https://github.com/oaubert/python-vlc/blob/38a90baf1d6c1e9a6131433ec3819766f308612c/examples/tkvlc.py#L52

    Returns:
        tuple: Contains:

        - function: Function to get NSView object.
        - bool: `True` if the function was found, `False` otherwise.
    """

    # libtk = cdll.LoadLibrary(ctypes.util.find_library('tk'))
    # returns the tk library /usr/lib/libtk.dylib from macOS,
    # but we need the tkX.Y library bundled with Python 3+,
    # to match the version number of tkinter, _tkinter, etc.
    try:
        libtk = "libtk{}.dylib".format(tkinter.TkVersion)

        # if Python was installed with Brew, it doesn't have Tk, so Tcl-Tk must be
        # installed separately and we have to retrieve its library path
        lib_path = get_tcl_tk_lib_path()

        if lib_path is None:
            # use default locations
            prefix = Path(getattr(sys, "base_prefix", sys.prefix))
            lib_path = prefix / LIB

        dylib = cdll.LoadLibrary(str(lib_path / libtk))

        # getNSView = dylib.TkMacOSXDrawableView is the
        # proper function to call, but that is non-public
        # (in Tk source file macosx/TkMacOSXSubwindows.c)
        # and dylib.TkMacOSXGetRootControl happens to call
        # dylib.TkMacOSXDrawableView and return the NSView
        _GetNSView = dylib.TkMacOSXGetRootControl
        # C signature: void *_GetNSView(void *drawable) to get
        # the Cocoa/Obj-C NSWindow.contentView attribute, the
        # drawable NSView object of the (drawable) NSWindow
        _GetNSView.restype = c_void_p
        _GetNSView.argtypes = (c_void_p,)

        found = True

    except (NameError, OSError):  # image or symbol not found

        def _GetNSView(unused):
            return None

        found = False

    return _GetNSView, found
