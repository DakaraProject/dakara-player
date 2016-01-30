KARA_FOLDER_PATH = ""
SERVER_URL = "http://127.0.0.1:8000/"
CREDENTIALS = ()
LOGGING_LEVEL = "INFO"
DELAY_BETWEEN_REQUESTS = 1
REQUESTS_LOGGING_DISABLED = True
try:
    import local_settings

    if hasattr(local_settings, 'KARA_FOLDER_PATH'):
        KARA_FOLDER_PATH = local_settings.KARA_FOLDER_PATH
    if hasattr(local_settings, 'SERVER_URL'):
        SERVER_URL = local_settings.SERVER_URL
    if hasattr(local_settings, 'CREDENTIALS'):
        CREDENTIALS = local_settings.CREDENTIALS
    if hasattr(local_settings, 'LOGGING_LEVEL'):
        LOGGING_LEVEL = local_settings.LOGGING_LEVEL
except ImportError:
    pass
