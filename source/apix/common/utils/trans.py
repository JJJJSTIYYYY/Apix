from datetime import datetime
from typing import Literal
import inflect


def get_date_natural_language():
    '''
    Get current date in natural language.

    Example: "Wednesday, April 15th, 2026"
    '''

    now = datetime.now()
    
    day = now.day
    month = now.strftime("%B")
    year = now.year
    weekday = now.strftime("%A")
    
    p = inflect.engine()
    ordinal_day = p.ordinal(day)
    
    natural_date = f"DATE: {weekday}, {month} {ordinal_day}, {year}"
    
    return natural_date


def convert_generation_id_to_message_node_id(
    generation_id: str | list[str] | set[str],
    role: Literal['user', 'ai', 'assistant']
) -> str | list[str] | set[str]:
    '''
    Convert generation id to message node id.
    '''

    suffix = "-user" if role == 'user' else "-apix"

    def convert(gid: str) -> str:
        return gid[-12:] + suffix

    if isinstance(generation_id, str):
        return convert(generation_id)

    return type(generation_id)(
        convert(gid)
        for gid in generation_id
    )