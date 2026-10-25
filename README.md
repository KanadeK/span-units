# span-units

Convert annotation spans between **UTF-8 bytes**, **UTF-16 code units**, and
**Unicode code points** without changing the text. An emoji occupies different
numbers of these units; copying offsets between browser and Python pipelines can
silently select the wrong text.

span-units validates every boundary, verifies optional quoted span text, and
publishes a new JSONL file only when every record passes. It runs locally with
Python 3.11+ and no runtime dependencies.

## Install and try

```sh
git clone https://github.com/KanadeK/span-units.git
cd span-units
python -m venv .venv
# Activate .venv using your shell, then:
python -m pip install .
span-units examples/annotations.jsonl --from-unit utf16 --to-unit utf8 --output converted.jsonl
python scripts/example.py
```

Activation: `source .venv/bin/activate` on bash/zsh; `.venv\Scripts\Activate.ps1`
on PowerShell. If script activation is unavailable, invoke `.venv\Scripts\python.exe`
directly and use `python -m span_units` in place of `span-units`.
Release wheels can also be installed with `python -m pip install path/to/file.whl`.

The included input has text `A😀中` and span `[1,4)` in UTF-16. Its output span is
`[1,8)` in UTF-8. The example script creates and removes its own temporary files.
Omit `--output` for a validation-only run. An existing output path is always refused.

## Input and coordinate contract

Each UTF-8 JSONL line is an object:

```json
{"id":"example","text":"A😀中","spans":[{"start":1,"end":4,"text":"😀中","label":"demo"}]}
```

* Offsets are **zero-based, half-open** `[start,end)`. Both must be integers;
  booleans, negatives, reversed spans and out-of-range endpoints are errors.
* `codepoint` counts Unicode scalar values; `utf8` counts bytes; `utf16` counts
  16-bit code units, excluding any encoding BOM. A boundary inside one scalar
  encoding is rejected. No endpoint rounding or clipping occurs.
* Overlapping, unordered and empty spans are allowed. A span's optional `text`
  must exactly match the selected substring, including whitespace and newlines.
* Output preserves JSON values and metadata except the span `start`/`end` fields
  and the top-level `offset_unit`, which is set to the destination unit. If that
  property exists on input it must equal `--from-unit`.
* This is a neutral schema. Adapt a vendor export to `text` and `spans` first.
  It does not read native Label Studio, Doccano, LSP or tokenizer formats.
* JSON formatting is reserialized using escaped Unicode. Duplicate members,
  nonfinite numbers, blank lines, invalid UTF-8 and a JSONL file BOM are rejected.
  A U+FEFF inside the `text` value remains ordinary counted text.

## Reports and exit codes

The command prints one JSON report with record/span counts, invalid-record count,
line/span/endpoint locations and stable error codes. It does not include text,
IDs, labels or filenames. `spans` counts spans in valid records. Only the first
semantic error per invalid record is reported; `--max-findings` limits stored
examples without hiding the total invalid-record count.

| Exit | Meaning |
|---|---|
| 0 | All records valid; output written if requested |
| 1 | Invalid spans, text/schema mismatch, or per-record semantic limit |
| 2 | CLI, JSON, I/O or byte-limit error; validation incomplete |

Default limits: 8 MiB per raw JSONL line (including its newline), 512 MiB total,
2 million code points and 100,000 spans per record, 100 stored findings.
See `--help` for overrides. One record and two compact boundary arrays are held
in memory. Output is staged in the destination directory, then published using
an atomic no-clobber hard link. NTFS, APFS and typical Linux filesystems support
this; filesystems that do not support hard links return an I/O error without
publishing the result. A process kill may leave a `.span-units-*` staging file.

## Limits and alternatives

This does **not** count grapheme clusters or screen columns: `e` plus a combining
accent is two code points. It does not normalize text, change line endings inside
text, repair stale annotations or detect a wrongly declared unit that happens to
produce valid boundaries. Include span text when possible. Keep input files stable
during a run; this is not a filesystem snapshot tool.

[GateNLP](https://github.com/GateNLP/python-gatenlp) is a broader annotation framework
with offset mapping. [simdutf](https://github.com/simdutf/simdutf) is appropriate for
high-throughput native Unicode processing. This project focuses on a portable
batch migration workflow and its publication gate. The historical
[Label Studio emoji offset issue](https://github.com/HumanSignal/label-studio/issues/2007)
illustrates the problem class; that issue was fixed upstream.

## Development and cleanup

See [CONTRIBUTING.md](CONTRIBUTING.md) for lint, tests and wheel verification.
Tests compare mappings with Python's independent encoders over randomized scalar
strings and exercise successful and failing CLI workflows.

Uninstall with `python -m pip uninstall span-units`. Remove your virtual environment
and generated `converted.jsonl` when no longer needed. Input files are not modified.
MIT license; no bundled third-party code or data.

## 中文说明

本工具用于迁移文本标注的位置单位：UTF-8 字节、UTF-16 代码单元、Unicode 码点。
例如 emoji 在三种单位中的长度不同。程序拒绝切断字符编码的边界，可校验标注文本，
整份输入通过后才生成新文件；已有输出不会被覆盖。它不做字素簇分割、文本规范化或
自动修正错误标注。输入采用上面的通用 JSONL 格式，运行和卸载命令见英文示例。
