KARA_FOLDER_PATH = ""
SERVER_URL = "http://127.0.0.1:8000/"
CREDENTIALS = ()

try:
    import local_settings

    if hasattr(local_settings, 'KARA_FOLDER_PATH'):
        KARA_FOLDER_PATH = local_settings.KARA_FOLDER_PATH
    if hasattr(local_settings, 'SERVER_URL'):
        SERVER_URL = local_settings.SERVER_URL
    if hasattr(local_settings, 'CREDENTIALS'):
        CREDENTIALS = local_settings.CREDENTIALS
except ImportError:
    pass
