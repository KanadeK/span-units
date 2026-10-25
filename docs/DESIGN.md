# Design and acceptance

Target users: NLP dataset engineers moving existing annotation offsets between
UTF-16 producers and Python/UTF-8 consumers. The MVP accepts a documented neutral
JSONL schema, validates exact scalar boundaries and quoted text, preserves metadata
values, and produces a new file only when the entire input passes.

The mapping builds cumulative UTF-8 byte and UTF-16 code-unit counts in compact
64-bit arrays. Binary search rejects any offset not found in a boundary array.
No normalization, newline conversion or grapheme segmentation is performed.
Memory scales with one bounded record; output is staged to a sibling file and
published with an atomic no-clobber hard link. No race-prone check-and-overwrite.

Acceptance: mixed supplementary/BMP/combining text matches independent Python
encoding lengths; every valid boundary round-trips in all unit pairs; invalid
boundaries and stale quotes fail; a later bad record publishes no partial output;
existing output remains byte-identical; malformed JSON, duplicates, resource
limits and publication failure return nonzero without leaking payload text.

Review before release: no runtime dependencies, no network paths, no eval or
subprocess execution in the runtime package. API does not mutate the caller's
record. JSON number overflow and duplicate members are rejected. Tests include
randomized encoder comparisons and actual subprocess CLI runs. A fresh wheel
environment is used to detect accidental reliance on editable source imports.

Known tradeoffs: an explicit wrong unit can be numerically valid; quote checks
help but cannot prove intent. Staging requires a hard-link-capable destination.
No filesystem snapshot guarantee. Input size limits are guards, not a memory
isolation boundary. A kill can leave a hidden staging file for manual cleanup.
