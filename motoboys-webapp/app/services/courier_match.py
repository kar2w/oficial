import re
import unicodedata

_WS = re.compile(r"\s+")


def norm_text(value: str | None) -> str:
    s = (value or "").strip().upper()
    s = "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")
    s = _WS.sub(" ", s)
    return s
