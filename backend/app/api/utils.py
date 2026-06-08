from datetime import datetime

from fastapi import HTTPException


def parse_date_param(value: str, param_name: str) -> datetime:
    """Parse a YYYY-MM-DD date string from a query parameter, raising 400 on invalid format."""
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {param_name} format. Use YYYY-MM-DD")
