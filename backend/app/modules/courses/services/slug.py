"""Slug generation for courses.

Cyrillic titles are transliterated to Latin so public URLs stay readable and
stable. Uniqueness is guaranteed by the service with a numeric suffix; the
database unique index is the final safety net.
"""

from __future__ import annotations

import re

from app.modules.courses.repositories.course import CourseRepository

MAX_SLUG_LENGTH = 200

_TRANSLITERATION: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    "і": "i",
    "ї": "yi",
    "є": "ye",
    "ґ": "g",
}

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Turn an arbitrary title into a lowercase hyphenated slug."""
    lowered = value.strip().lower()
    transliterated = "".join(_TRANSLITERATION.get(char, char) for char in lowered)
    slug = _NON_SLUG.sub("-", transliterated).strip("-")
    if not slug:
        slug = "course"
    return slug[:MAX_SLUG_LENGTH].rstrip("-")


def _with_suffix(base: str, suffix: int) -> str:
    tail = f"-{suffix}"
    return f"{base[: MAX_SLUG_LENGTH - len(tail)].rstrip('-')}{tail}"


async def unique_course_slug(repository: CourseRepository, title: str) -> str:
    """Return a slug that no other course uses.

    The numeric suffix keeps links predictable (``python-basics``,
    ``python-basics-2``) instead of appending random characters.
    """
    base = slugify(title)
    if not await repository.slug_exists(base):
        return base

    suffix = 2
    while await repository.slug_exists(_with_suffix(base, suffix)):
        suffix += 1
    return _with_suffix(base, suffix)
