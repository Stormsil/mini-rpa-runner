from __future__ import annotations


def parse_duration(text: str | int | float | None) -> float | None:
    """
    Преобразует '400ms', '2s', '1m' в секунды (float).
    Если передано число — вернёт float без изменений.
    Если None — вернёт None.
    """
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).strip().lower()
    if s.endswith("ms"):
        return float(s[:-2]) / 1000.0
    if s.endswith("s"):
        return float(s[:-1])
    if s.endswith("m"):
        return float(s[:-1]) * 60.0
    # по умолчанию пытаемся как число в секундах
    return float(s)
