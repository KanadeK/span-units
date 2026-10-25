import copy
import random
import unittest

from span_units.core import UNITS, OffsetMap, SpanError, convert_record


class MappingTests(unittest.TestCase):
    def test_known_emoji_coordinates(self):
        mapping = OffsetMap("A😀中e\u0301\r\n")
        self.assertEqual(list(mapping.utf8), [0, 1, 5, 8, 9, 11, 12, 13])
        self.assertEqual(list(mapping.utf16), [0, 1, 3, 4, 5, 6, 7, 8])

    def test_all_units_against_encoding_oracle(self):
        rng = random.Random(73231)
        for _ in range(120):
            text = "".join(
                chr(rng.choice([rng.randrange(0xD800), rng.randrange(0xE000, 0x110000)]))
                for _ in range(rng.randrange(40))
            )
            mapping = OffsetMap(text)
            for index in range(len(text) + 1):
                offsets = {
                    "codepoint": index,
                    "utf8": len(text[:index].encode("utf-8")),
                    "utf16": len(text[:index].encode("utf-16-le")) // 2,
                }
                for source in UNITS:
                    for target in UNITS:
                        self.assertEqual(
                            mapping.convert(offsets[source], source, target), offsets[target]
                        )

    def test_every_nonboundary_rejected(self):
        text = "é中😀"
        mapping = OffsetMap(text)
        for unit in ("utf8", "utf16"):
            valid = set(getattr(mapping, unit))
            for offset in range(max(valid) + 1):
                if offset not in valid:
                    with self.assertRaisesRegex(SpanError, "offset_splits_scalar"):
                        mapping.convert(offset, unit, "codepoint")

    def test_invalid_offsets(self):
        for offset in (-1, 5, 1.0, True, None, "1"):
            with self.subTest(offset=offset), self.assertRaises(SpanError):
                OffsetMap("abc").boundary(offset, "codepoint")

    def test_empty(self):
        self.assertEqual(OffsetMap("").convert(0, "utf16", "utf8"), 0)

    def test_surrogates(self):
        for text in ("\ud800", "a\udfff", "\ud83d\ude00"):
            with self.subTest(text=repr(text)), self.assertRaises(SpanError):
                OffsetMap(text)

    def test_unknown_units(self):
        with self.assertRaises(ValueError):
            OffsetMap("a").convert(0, "grapheme", "utf8")
        with self.assertRaises(ValueError):
            OffsetMap("a").convert(0, "utf8", "byte")


class RecordTests(unittest.TestCase):
    def test_roundtrip_metadata_unchanged(self):
        record = {
            "text": "A😀中e\u0301",
            "offset_unit": "utf16",
            "id": "doc-1",
            "spans": [
                {"start": 1, "end": 4, "text": "😀中", "label": {"x": [1]}},
                {"start": 4, "end": 4},
                {"start": 0, "end": 6},
            ],
        }
        original = copy.deepcopy(record)
        result = convert_record(record, "utf16", "utf8")
        self.assertEqual(result["spans"][0]["end"], 8)
        self.assertEqual(convert_record(result, "utf8", "utf16"), original)
        self.assertEqual(record, original)

    def test_combining_boundary_is_not_grapheme_validation(self):
        result = convert_record(
            {"text": "e\u0301", "spans": [{"start": 1, "end": 2}]}, "codepoint", "utf8"
        )
        self.assertEqual(result["spans"][0], {"start": 1, "end": 3})

    def test_mismatched_quote(self):
        with self.assertRaisesRegex(SpanError, "span_text_mismatch"):
            convert_record(
                {"text": "abc", "spans": [{"start": 0, "end": 1, "text": "b"}]},
                "codepoint",
                "utf16",
            )

    def test_schema_rejections(self):
        records = [
            None,
            [],
            {},
            {"text": 4, "spans": []},
            {"text": "x", "spans": {}},
            {"text": "x", "spans": [[]]},
            {"text": "x", "spans": [{"start": 0}]},
            {"text": "x", "spans": [{"start": 1, "end": 0}]},
            {"text": "x", "spans": [], "offset_unit": "utf8"},
        ]
        for record in records:
            with self.subTest(record=record), self.assertRaises(SpanError):
                convert_record(record, "codepoint", "utf8")

    def test_limits(self):
        with self.assertRaisesRegex(SpanError, "text_limit"):
            convert_record({"text": "xx", "spans": []}, "utf8", "utf16", max_chars=1)
        with self.assertRaisesRegex(SpanError, "span_limit"):
            convert_record({"text": "", "spans": [{}, {}]}, "utf8", "utf16", max_spans=1)

    def test_error_location(self):
        with self.assertRaises(SpanError) as caught:
            convert_record({"text": "😀", "spans": [{"start": 0, "end": 1}]}, "utf16", "utf8")
        self.assertEqual((caught.exception.span, caught.exception.endpoint), (0, "end"))
