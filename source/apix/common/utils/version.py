from apix.config.base_config import VERSION


def compare_version(v: str) -> int:
    """
    Compare the given version string with the current system version.

    Args:
        v: The version string to compare (e.g., "1.2.3").

    Returns:
        int: 
            - 0  if ``v`` equals the current version (``VERSION``).
            - -1 if ``v`` is older (less than the current version).
            - 1  if ``v`` is newer (greater than the current version).
    """
    v1_parts = [int(x) for x in VERSION.split('.')]
    v2_parts = [int(x) for x in v.split('.')]

    max_len = max(len(v1_parts), len(v2_parts))
    v1_parts += [0] * (max_len - len(v1_parts))
    v2_parts += [0] * (max_len - len(v2_parts))

    if v2_parts == v1_parts:
        return 0
    elif v2_parts < v1_parts:
        return -1
    else:
        return 1


def print_logo():
    ap_color = "\033[38;2;0;200;170m"      # APIX teal
    ix_color = "\033[38;2;255;120;40m"     # APIX orange
    gray = "\033[38;2;140;140;140m"        # Light gray
    reset = "\033[0m"

    print(f"""{gray}
======================================
{reset}{ap_color}     ___      .______{reset}    {ix_color}__  ___   ___{reset}
{ap_color}    /   \\     |   _  \\{reset}  {ix_color}|  | \\  \\ /  /{reset}
{ap_color}   /  ^  \\    |  |_)  |{reset} {ix_color}|  |  \\  V  /{reset}
{ap_color}  /  /_\\  \\   |   ___/{reset}  {ix_color}|  |   >   <{reset}
{ap_color} /  _____  \\  |  |{reset}      {ix_color}|  |  /  ^  \\{reset}
{ap_color}/__/     \\__\\ | _|{reset}      {ix_color}|__| /__/ \\__\\{reset}

{gray}              NEXT {VERSION}
======================================
{reset}""")
