"""Parsing hh asset codes, like hh1234, out of filenames."""
import re

# hh1234.jpg, HH01234_2.jpg, hh1234-front.jpg; not hh1234a.jpg, hh 1234.jpg or IMG_hh1234.jpg
# (?![^\W_]) means "not followed by a letter or digit"
_PREFIX_RE = re.compile(r'hh0*([1-9]\d*)(?![^\W_])', re.IGNORECASE)
# Also IMG_hh1234.jpg, rh1234.jpg, hh-1234.jpg, hh1234a.jpg; not bhh1234.jpg
_ANYWHERE_RE = re.compile(r'(?<![^\W\d_])[hr]h[ _-]?0*([1-9]\d*)', re.IGNORECASE)


def parse_hh_code(filename: str) -> int | None:
    """Asset ID from an hh code at the start of a filename, strict enough to assign the file automatically."""
    match = _PREFIX_RE.match(filename)
    return int(match[1]) if match else None


def find_hh_code_suggestion(filename: str) -> int | None:
    """Asset ID from the first code anywhere in a filename, which should only be suggested to the user."""
    match = _ANYWHERE_RE.search(filename)
    return int(match[1]) if match else None
