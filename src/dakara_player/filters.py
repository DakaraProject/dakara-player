def filter_duration_hhmm(duration):
    """Format a duration as hours and minutes.

    Args:
        duration (int): Duration in seconds.

    Returns:
        str: Formatted duration, either:

        - `H:MM` if the duration exceeds one hour;
        - `M` otherwise.
    """
    if duration is None:
        return ""

    try:
        hours, seconds = divmod(duration, 3600)
        minutes, _ = divmod(seconds, 60)

    except TypeError:
        return str(duration)

    if hours > 0:
        return f"{hours:d}:{minutes:02d}"

    return f"{minutes:d}"


def filter_duration_ss(duration):
    """Format a duration as seconds.

    Args:
        duration (int): Duration in seconds.

    Returns:
        str: Formatted duration, as `:SS`.
    """
    if duration is None:
        return ""

    try:
        seconds = duration % 60

    except TypeError:
        return str(duration)

    return f":{seconds:02d}"
