# Path of the karaoke folder
KARA_FOLDER_PATH = "/path/to/your/kara/directory"

# Server URL
SERVER_URL = "http://127.0.0.1:8000/"

# Credentials for server authentication
CREDENTIALS = ('user', 'password')

# Enable or disable fullscreen mode
FULLSCREEN_MODE = False

# Pass extra arguments to VLC, must be a string
# Several parameters can be concatenated in the string
# If you need to disable hardware acceleration:
#   VLC_PARAMETERS_MEDIA = "avcodec-hw=none"
# If you want subtitle rendering to use screen resolution instead of video's:
#   VLC_PARAMETERS_INSTANCE = "--vout x11"
# This may slow down the rendering if hardware decoding cannot be properly
# called
# Consult VLC expanded help for a complete list of parameters:
#   vlc --longhelp --advanced
# Not all parameters are allowed thought
# Some parameters only work on the instance, others only on the media 
#VLC_PARAMETERS_INSTANCE = ""
#VLC_PARAMETERS_MEDIA= ""

# Minimal level of messages to log
#LOGGING_LEVEL = "INFO"

# Disable requests module log entries of level lower than WARNING
#REQUESTS_LOGGING_DISABLED = True
