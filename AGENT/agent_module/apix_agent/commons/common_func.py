from datetime import datetime
import inflect

def get_date_natural_language():
    now = datetime.now()
    
    day = now.day
    month = now.strftime("%B")
    year = now.year
    weekday = now.strftime("%A")
    
    p = inflect.engine()
    ordinal_day = p.ordinal(day)
    
    # "Wednesday, April 15th, 2026"
    natural_date = f"DATE: {weekday}, {month} {ordinal_day}, {year}"
    
    return natural_date