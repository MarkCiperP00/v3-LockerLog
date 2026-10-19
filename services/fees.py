from decimal import Decimal
from db import query

def get_rate_per_day():
    row = query("SELECT setting_value FROM settings WHERE setting_key=%s",
                ("rate_per_day",), one=True)
    return Decimal(row["setting_value"])

def compute_assignment(semester, approval_date, rate_per_day):
    """Return (date_start, date_end, days, total_fee). Prorated from approval date."""
    sem_start, sem_end = semester["date_start"], semester["date_end"]  # date objects
    start = max(approval_date, sem_start)
    if start >= sem_end:
        raise ValueError("Semester has already ended")
    days = (sem_end - start).days + 1
    return start, sem_end, days, (rate_per_day * days).quantize(Decimal("0.01"))
