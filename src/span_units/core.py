"""Map exact scalar boundaries without changing source text."""

from array import array
from bisect import bisect_left

UNITS = ("codepoint", "utf8", "utf16")


class SpanError(ValueError):
    """A coded error that does not include input text."""

    def __init__(self, code: str, span: int | None = None, endpoint: str | None = None):
        self.code = code
        self.span = span
        self.endpoint = endpoint
        super().__init__(code)


class OffsetMap:
    """O(n) construction, O(log n) exact UTF boundary lookup."""

    def __init__(self, text: str):
        if not isinstance(text, str):
            raise SpanError("text_not_string")
        self.text = text
        self.utf8 = array("Q", [0])
        self.utf16 = array("Q", [0])
        for char in text:
            value = ord(char)
            if 0xD800 <= value <= 0xDFFF:
                raise SpanError("unpaired_surrogate")
            width8 = 1 if value < 0x80 else 2 if value < 0x800 else 3 if value < 0x10000 else 4
            self.utf8.append(self.utf8[-1] + width8)
            self.utf16.append(self.utf16[-1] + (1 if value < 0x10000 else 2))

    def boundary(self, offset: int, unit: str) -> int:
        if unit not in UNITS:
            raise ValueError("unknown_unit")
        if type(offset) is not int:
            raise SpanError("offset_not_integer")
        positions = range(len(self.text) + 1) if unit == "codepoint" else getattr(self, unit)
        if offset < 0 or offset > positions[-1]:
            raise SpanError("offset_out_of_range")
        position = bisect_left(positions, offset)
        if positions[position] != offset:
            raise SpanError("offset_splits_scalar")
        return position

    def convert(self, offset: int, source: str, target: str) -> int:
        if target not in UNITS:
            raise ValueError("unknown_unit")
        position = self.boundary(offset, source)
        return position if target == "codepoint" else getattr(self, target)[position]


def convert_record(
    record: object, source: str, target: str, max_chars: int = 2_000_000, max_spans: int = 100_000
) -> dict:
    """Convert the documented neutral JSON schema; never mutate the argument."""
    if source not in UNITS or target not in UNITS:
        raise ValueError("unknown_unit")
    if not isinstance(record, dict):
        raise SpanError("record_not_object")
    if "offset_unit" in record and record["offset_unit"] != source:
        raise SpanError("unit_metadata_mismatch")
    text = record.get("text")
    if not isinstance(text, str):
        raise SpanError("text_not_string")
    if len(text) > max_chars:
        raise SpanError("text_limit")
    spans = record.get("spans")
    if not isinstance(spans, list):
        raise SpanError("spans_not_array")
    if len(spans) > max_spans:
        raise SpanError("span_limit")
    mapping = OffsetMap(text)
    converted = []
    for index, span in enumerate(spans):
        if not isinstance(span, dict):
            raise SpanError("span_not_object", index)
        boundaries = {}
        for endpoint in ("start", "end"):
            if endpoint not in span:
                raise SpanError("missing_endpoint", index, endpoint)
            try:
                boundaries[endpoint] = mapping.boundary(span[endpoint], source)
            except SpanError as exc:
                raise SpanError(exc.code, index, endpoint) from exc
        if boundaries["end"] < boundaries["start"]:
            raise SpanError("reversed_span", index)
        if "text" in span and span["text"] != text[boundaries["start"] : boundaries["end"]]:
            raise SpanError("span_text_mismatch", index)
        converted.append(
            {
                **span,
                "start": mapping.convert(span["start"], source, target),
                "end": mapping.convert(span["end"], source, target),
            }
        )
    return {**record, "spans": converted, "offset_unit": target}
