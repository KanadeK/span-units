"""Bounded JSONL validation with no-clobber publication."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from . import __version__
from .core import UNITS, SpanError, convert_record


class InputError(ValueError):
    pass


def positive(value: str) -> int:
    value = int(value)
    if not 0 < value <= 2_147_483_647:
        raise argparse.ArgumentTypeError("must be between 1 and 2147483647")
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate_json_member")
        result[key] = value
    return result


def reject_constant(_):
    raise InputError("nonfinite_json_number")


def run(args) -> tuple[dict, int]:
    report = {
        "schema_version": 1,
        "tool": "span-units",
        "source_unit": args.from_unit,
        "target_unit": args.to_unit,
        "records": 0,
        "spans": 0,
        "invalid_records": 0,
        "findings": [],
        "output_written": False,
    }
    temporary = None
    line_number = 0
    try:
        source = Path(args.input)
        if not source.is_file():
            raise InputError("input_not_regular_file")
        if args.output:
            destination = Path(args.output)
            if os.path.lexists(destination):
                raise InputError("output_exists")
            fd, temporary = tempfile.mkstemp(prefix=".span-units-", dir=destination.parent)
            output = os.fdopen(fd, "wb")
        else:
            output = None
        try:
            with source.open("rb") as stream:
                total_bytes = 0
                while raw := stream.readline(args.max_line_bytes + 1):
                    line_number += 1
                    total_bytes += len(raw)
                    if len(raw) > args.max_line_bytes:
                        raise InputError("line_byte_limit")
                    if total_bytes > args.max_input_bytes:
                        raise InputError("input_byte_limit")
                    try:
                        record = json.loads(
                            raw.decode("utf-8"),
                            object_pairs_hook=unique_object,
                            parse_constant=reject_constant,
                        )
                    except (UnicodeError, ValueError, RecursionError) as exc:
                        code = str(exc) if isinstance(exc, InputError) else "invalid_json_line"
                        raise InputError(code) from exc
                    report["records"] += 1
                    try:
                        result = convert_record(
                            record, args.from_unit, args.to_unit, args.max_chars, args.max_spans
                        )
                        serialized = json.dumps(result, ensure_ascii=True, allow_nan=False)
                    except SpanError as exc:
                        report["invalid_records"] += 1
                        if len(report["findings"]) < args.max_findings:
                            report["findings"].append(
                                {
                                    "line": line_number,
                                    "span": exc.span,
                                    "endpoint": exc.endpoint,
                                    "code": exc.code,
                                }
                            )
                        continue
                    except (ValueError, RecursionError) as exc:
                        raise InputError("invalid_json_value") from exc
                    report["spans"] += len(result["spans"])
                    if output:
                        output.write(serialized.encode("ascii") + b"\n")
            if output:
                output.flush()
                os.fsync(output.fileno())
        finally:
            if output:
                output.close()
        if report["invalid_records"]:
            report["status"] = "invalid"
            return report, 1
        if args.output:
            # The complete sibling file is linked atomically; an existing name always wins.
            os.link(temporary, destination)
            report["output_written"] = True
        report["status"] = "ok"
        return report, 0
    except (InputError, OSError) as exc:
        report["status"] = "error"
        report["error"] = {
            "code": str(exc) if isinstance(exc, InputError) else "io_error",
            "line": line_number or None,
        }
        return report, 2
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Convert exact JSONL annotation span units.")
    parser.add_argument("--version", action="version", version=f"span-units {__version__}")
    parser.add_argument("input", help="UTF-8 JSONL, one text/spans object per line")
    parser.add_argument("--from-unit", choices=UNITS, required=True)
    parser.add_argument("--to-unit", choices=UNITS, required=True)
    parser.add_argument("--output", help="new output file; omit to validate only")
    parser.add_argument("--max-line-bytes", type=positive, default=8 * 1024 * 1024)
    parser.add_argument("--max-input-bytes", type=positive, default=512 * 1024 * 1024)
    parser.add_argument("--max-chars", type=positive, default=2_000_000)
    parser.add_argument("--max-spans", type=positive, default=100_000)
    parser.add_argument("--max-findings", type=positive, default=100)
    args = parser.parse_args(argv)
    report, status = run(args)
    try:
        sys.stdout.write(json.dumps(report, ensure_ascii=True, allow_nan=False) + "\n")
    except BrokenPipeError:
        return 2
    return status
