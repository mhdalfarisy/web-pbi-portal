"""Pengaman parameter dan hasil tool, dipakai semua agent supaya AI tidak menjawab dari hasil query yang keliru."""
import re


class ToolArgError(Exception):
    """Parameter dari AI tidak cocok dengan data. Dikembalikan ke AI beserta pilihan yang valid."""

    def __init__(self, name, value, options):
        super().__init__(f"{name} '{value}' is not recognised")
        self.name, self.value, self.options = name, value, list(options)

    def result(self):
        return {"error": f"{self.name} '{self.value}' is not recognised. Use one of valid_options.",
                "valid_options": self.options[:40]}


def norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def resolve(name, value, options, prefixes=("fp", "all")):
    """Cocokkan nilai dari AI ke nilai asli di data: persis, tanpa awalan (mis. FP/All), atau satu-satunya yang
    mengandung teks itu. Kalau tidak ada / ambigu, lempar ToolArgError berisi pilihan yang valid."""
    key = norm(value)
    exact = {norm(o): o for o in options}
    if key in exact:
        return exact[key]
    if prefixes:
        pattern = re.compile(rf"^({'|'.join(prefixes)})(?=.)")
        core = {pattern.sub("", k): o for k, o in exact.items()}  # "FP Not Ready" -> "notready"
        if key in core:
            return core[key]
    hits = [o for k, o in exact.items() if key and key in k]
    if len(hits) == 1:
        return hits[0]
    raise ToolArgError(name, value, sorted(options))


def week_key(value):
    """'44 - 2026', '44-2026', 'week 44 2026', '2026 W44' -> (2026, 44)."""
    text = str(value)
    m = re.search(r"(\d{1,2})\D+(\d{4})", text)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.search(r"(\d{4})\D+(\d{1,2})\b", text)
    return (int(m.group(1)), int(m.group(2))) if m else None


def resolve_week(value, weeks):
    by_key = {week_key(w): w for w in weeks}
    key = week_key(value)
    if key in by_key:
        return by_key[key]
    latest = sorted((k, w) for k, w in by_key.items() if k)[-20:]
    raise ToolArgError("week (format 'week - year')", value, [w for _, w in latest])


EMPTY_HINT = ("No rows for these filters. That does not necessarily mean the data does not exist: mention the filters "
              "used, then suggest widening the period or searching for a specific code/number.")


def add_hint(result):
    if isinstance(result, dict) and "error" not in result and \
            (result.get("total") == 0 or result.get("total_rows") == 0 or result.get("groups") == []):
        result["hint"] = EMPTY_HINT
    return result
