KARA_FOLDER_PATH = ""
SERVER_URL = "http://127.0.0.1:8000/"
CREDENTIALS = ()
LOGGING_LEVEL = "INFO"
DELAY_BETWEEN_REQUESTS = 1
REQUESTS_LOGGING_DISABLED = True

try:
    from local_settings import *
except ImportError:
    pass
