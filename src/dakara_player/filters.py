def filter_duration(duration):
    """Format a duration.

    Args:
        duration (int): Duration in seconds.

    Returns:
        str: Formatted duration, either:

        - `H:MM:SS` if the duration exceeds one hour;
        - `M:SS` otherwise.
    """
    if duration is None:
        return ""

    try:
        hours, seconds = divmod(duration, 3600)
        minutes, seconds = divmod(seconds, 60)

    except TypeError:
        return str(duration)

    if hours > 0:
        return "{:d}:{:02d}:{:02d}".format(hours, minutes, seconds)

    return "{:d}:{:02d}".format(minutes, seconds)
