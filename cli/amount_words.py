"""Turn a check's written amount into a number, and back.

    >>> words_to_amount("One thousand two hundred fifty and 00/100 dollars")
    Decimal('1250.00')
    >>> amount_to_words(Decimal("1250.00"))
    'One thousand two hundred fifty and 00/100'

Handles the ways people actually write checks: "and 45/100", "& 45/100",
"45 cents", "xx/100", "no/100", hyphens ("forty-five"), "dollars only",
leading "**" fill and stray commas. Standard library only.
"""
import re
from decimal import Decimal

ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
SCALES = {"thousand": 1000, "million": 1000000}


class WordsError(ValueError):
    pass


def _words_to_int(text):
    tokens = [t for t in re.split(r"[\s\-]+", text.lower()) if t and t not in ("and", "dollars", "dollar", "only", "exactly")]
    if not tokens:
        raise WordsError("no words")
    total, current = 0, 0
    for t in tokens:
        if t in ONES:
            current += ONES[t]
        elif t in TENS:
            current += TENS[t]
        elif t == "hundred":
            current = (current or 1) * 100
        elif t in SCALES:
            total += (current or 1) * SCALES[t]
            current = 0
        else:
            raise WordsError(f"unknown word '{t}'")
    return total + current


def words_to_amount(text):
    """Return the Decimal a written amount means. Raises WordsError if it can't be read."""
    s = text.strip().strip("*").replace(",", " ").strip()
    s = re.sub(r"\s+", " ", s)
    cents = 0
    m = re.search(r"(?:\band\b|&)?\s*(\d{1,2}|xx|no|00)\s*/\s*100\b.*$", s, re.I)
    if m:
        frac = m.group(1).lower()
        cents = 0 if frac in ("xx", "no") else int(frac)
        s = s[: m.start()]
    else:
        m = re.search(r"(?:\band\b|&)\s*(.+?)\s+cents?\b.*$", s, re.I)
        if m:
            part = m.group(1)
            cents = int(part) if part.isdigit() else _words_to_int(part)
            s = s[: m.start()]
    s = re.sub(r"\bdollars?\b.*$", "", s, flags=re.I).strip()
    s = re.sub(r"(\band\b|&)\s*$", "", s, flags=re.I).strip()
    dollars = _words_to_int(s) if s else 0
    if cents > 99:
        raise WordsError("cents over 99")
    return Decimal(dollars) + Decimal(cents) / 100


def _int_to_words(n):
    if n == 0:
        return "zero"
    names = {v: k for k, v in ONES.items()}
    names.update({v: k for k, v in TENS.items() if k != "fourty"})
    parts = []
    for scale, word in ((1000000, "million"), (1000, "thousand")):
        if n >= scale:
            parts.append(_int_to_words(n // scale) + " " + word)
            n %= scale
    if n >= 100:
        parts.append(names[n // 100] + " hundred")
        n %= 100
    if n >= 20:
        parts.append(names[n - n % 10] + ("-" + names[n % 10] if n % 10 else ""))
    elif n:
        parts.append(names[n])
    return " ".join(parts)


def amount_to_words(amount):
    amount = Decimal(amount).quantize(Decimal("0.01"))
    dollars = int(amount)
    cents = int((amount - dollars) * 100)
    w = _int_to_words(dollars)
    return f"{w[0].upper()}{w[1:]} and {cents:02d}/100"
