"""Shared fuzzy-matching helpers for the playlist builder scripts."""
import re
import sys
from difflib import SequenceMatcher

# Candidates scoring at or above ACCEPT_SCORE are added automatically.
# Candidates between REJECT_SCORE and ACCEPT_SCORE trigger an ask_user()
# confirmation. Anything below REJECT_SCORE is treated as not found.
ACCEPT_SCORE = 0.70
REJECT_SCORE = 0.30


def norm(s):
    s = s.lower()
    s = re.sub(r'[^\w\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def similarity(a, b):
    """Fuzzy similarity of two strings in [0, 1], generous to substrings."""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 0.95
    return SequenceMatcher(None, na, nb).ratio()


def token_coverage(want, got):
    """Fraction of the words in `want` that appear in `got`."""
    want_tokens = set(norm(want).split())
    got_tokens = set(norm(got).split())
    if not want_tokens:
        return 0.0
    return len(want_tokens & got_tokens) / len(want_tokens)


def ask_user(question):
    """Print an ASK line and wait for a y/n answer on stdin.

    The web UI watches for the "ASK:" prefix and renders yes/no buttons
    that write the answer back to the job's stdin; in a terminal the user
    just types y or n. Returns False on EOF (no one to ask).
    """
    print(f'ASK: {question} (y/n)', flush=True)
    try:
        answer = sys.stdin.readline()
    except (OSError, ValueError):
        return False
    if not answer:
        return False
    return answer.strip().lower() in ('y', 'yes')
