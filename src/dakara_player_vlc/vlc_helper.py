import os

# Required as of Python 3.8
if hasattr(os, "add_dll_directory"):
    os.add_dll_directory("C:\\Program Files\\VideoLAN\\VLC")
