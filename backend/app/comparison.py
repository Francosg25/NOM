"""Bounded comparison of saved text; it does not infer regulatory applicability."""

from difflib import SequenceMatcher
from collections import OrderedDict
import re
from threading import Lock
import unicodedata

MAX_TEXT = 1_000_000
MAX_BLOCKS = 3000
BLOCK_SIZE = 1000


class ComparisonCache:
    """Keep two immutable results without retaining the original input texts."""

    def __init__(self):
        self.entries = OrderedDict()
        self.lock = Lock()

    def get(self, key):
        with self.lock:
            if key not in self.entries:
                return None
            self.entries.move_to_end(key)
            return self.entries[key]

    def put(self, key, result):
        with self.lock:
            self.entries[key] = result
            self.entries.move_to_end(key)
            while len(self.entries) > 2:
                self.entries.popitem(last=False)


comparison_cache = ComparisonCache()


def normalized(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def blocks(text):
    parts = re.split(r"(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÑ0-9])", normalized(text))
    result = []
    for part in parts:
        while len(part) > BLOCK_SIZE:
            end = part.rfind(" ", 0, BLOCK_SIZE)
            end = end if end > BLOCK_SIZE // 2 else BLOCK_SIZE
            result.append(part[:end])
            part = part[end:].lstrip()
        if part:
            result.append(part)
        if len(result) > MAX_BLOCKS:
            return None
    return result


def marked(before, after, budget):
    left, right = [], []
    old = re.findall(r"\s+|\w+|[^\w\s]", before)
    new = re.findall(r"\s+|\w+|[^\w\s]", after)
    cost = len(old) * len(new)
    if cost > min(30000, budget[0]):
        return [{"kind": "removed", "text": before}], [{"kind": "added", "text": after}]
    budget[0] -= cost
    for kind, i, j, k, end in SequenceMatcher(None, old, new, autojunk=True).get_opcodes():
        if i != j:
            left.append({"kind": "equal" if kind == "equal" else "removed", "text": "".join(old[i:j])})
        if k != end:
            right.append({"kind": "equal" if kind == "equal" else "added", "text": "".join(new[k:end])})
        if len(left) + len(right) > 160:
            return [{"kind": "removed", "text": before}], [{"kind": "added", "text": after}]
    return left, right


def compare_text(before, after):
    if len(before) > MAX_TEXT or len(after) > MAX_TEXT:
        return {"classification": "too_large", "rows": (), "added": 0, "removed": 0, "modified": 0}
    if not before.strip() or not after.strip():
        return {"classification": "unavailable", "rows": (), "added": 0, "removed": 0, "modified": 0}
    classification = (
        "unchanged"
        if before == after
        else "spacing_only"
        if normalized(before) == normalized(after)
        else "text_changed"
    )
    if classification != "text_changed":
        return {"classification": classification, "rows": (), "added": 0, "removed": 0, "modified": 0}
    old, new = blocks(before), blocks(after)
    if old is None or new is None:
        return {"classification": "too_large", "rows": (), "added": 0, "removed": 0, "modified": 0}
    rows = []
    counts = {"added": 0, "removed": 0, "modified": 0}
    budget = [250000]
    matcher = SequenceMatcher(None, old, new, autojunk=True)
    for group in matcher.get_grouped_opcodes(n=1):
        for kind, i, j, k, end in group:
            if kind == "equal":
                rows.extend({"kind": "context", "before": text, "after": text} for text in old[i:j])
            elif kind == "replace":
                length = max(j - i, end - k)
                for offset in range(length):
                    left = old[i + offset] if i + offset < j else ""
                    right = new[k + offset] if k + offset < end else ""
                    row_kind = "modified" if left and right else "removed" if left else "added"
                    left_marks, right_marks = marked(left, right, budget)
                    rows.append(
                        {
                            "kind": row_kind,
                            "before": left,
                            "after": right,
                            "before_marks": left_marks,
                            "after_marks": right_marks,
                        }
                    )
                    counts[row_kind] += 1
            else:
                row_kind = "removed" if kind == "delete" else "added"
                for text in old[i:j] if kind == "delete" else new[k:end]:
                    rows.append(
                        {
                            "kind": row_kind,
                            "before": text if kind == "delete" else "",
                            "after": text if kind == "insert" else "",
                        }
                    )
                    counts[row_kind] += 1
    return {"classification": classification, "rows": tuple(rows), **counts}
