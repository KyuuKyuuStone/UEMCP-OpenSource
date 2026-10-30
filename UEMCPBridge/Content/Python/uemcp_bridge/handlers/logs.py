"""``log.query``: read-only search over the project's Saved/Logs files."""

import datetime
import os
import re

from ..errors import RpcError
from . import HandlerResult, check_keys, get_int, get_list, get_str, get_unreal

LEVELS = {"Error", "Warning", "Log", "Display"}
_MAX_TEXT = 500
_LINE_TS_RE = re.compile(r"^\[(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})\.(\d{2}):(\d{3})\]")
_LEVEL_RE = re.compile(r"Log\w*: (Error|Warning|Log|Display):")
_FALLBACK_LEVEL_RE = re.compile(r"\b(Error|Warning|Display)\b")


def _project_dir():
    try:
        return os.path.abspath(str(get_unreal().Paths.project_dir()))
    except Exception:
        return os.getcwd()


def _logs_dir(project_dir):
    return os.path.join(project_dir, "Saved", "Logs")


def _project_name(project_dir):
    return os.path.basename(os.path.normpath(project_dir))


def _default_log_path(project_dir):
    logs_dir = _logs_dir(project_dir)
    expected = os.path.join(logs_dir, _project_name(project_dir) + ".log")
    if os.path.isfile(expected):
        return expected
    best = None
    best_mtime = -1.0
    try:
        for name in os.listdir(logs_dir):
            if not name.endswith(".log") or "-backup-" in name:
                continue
            path = os.path.join(logs_dir, name)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if mtime > best_mtime:
                best_mtime = mtime
                best = path
    except OSError:
        return None
    return best


def _safe_log_path(path, logs_dir):
    real = os.path.realpath(path)
    base = os.path.realpath(logs_dir)
    if real != base and not real.startswith(base + os.sep):
        raise RpcError(
            "PERMISSION_DENIED",
            "Log path escapes the project log directory",
            {"logsDir": base, "resolved": real},
        )
    return real


def _parse_line_time(line):
    match = _LINE_TS_RE.match(line)
    if not match:
        return None
    try:
        return datetime.datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            int(match.group(4)),
            int(match.group(5)),
            int(match.group(6)),
            int(match.group(7)) * 1000,
        )
    except ValueError:
        return None


def _parse_since(value):
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError as exc:
        raise RpcError(
            "INVALID_ARGUMENT",
            "since must be an ISO-8601 timestamp: %s" % exc,
            {"issues": [{"path": "since", "code": "invalid_format", "message": str(exc)}]},
        )
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def handle(server, params):
    check_keys(params, {"pattern", "levels", "since", "limit", "offset"})
    pattern = get_str(params, "pattern", default=None, max_length=200)
    levels = get_list(params, "levels", default=[], item_type=str, max_items=4)
    for level in levels:
        if level not in LEVELS:
            raise RpcError(
                "INVALID_ARGUMENT",
                "levels must contain only Error/Warning/Log/Display",
                {
                    "issues": [
                        {
                            "path": "levels",
                            "code": "invalid_enum_value",
                            "message": "unsupported level %r" % level,
                        }
                    ]
                },
            )
    since = get_str(params, "since", default=None, max_length=64)
    since_dt = _parse_since(since) if since else None
    limit = get_int(params, "limit", default=200, minimum=1, maximum=2000)
    offset = get_int(params, "offset", default=0, minimum=0)

    regex = None
    if pattern:
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise RpcError(
                "INVALID_ARGUMENT",
                "pattern is not a valid regular expression: %s" % exc,
                {
                    "issues": [
                        {"path": "pattern", "code": "invalid_format", "message": str(exc)}
                    ]
                },
            )

    project_dir = _project_dir()
    logs_dir = _logs_dir(project_dir)
    log_path = _default_log_path(project_dir)
    if not log_path or not os.path.isfile(log_path):
        raise RpcError(
            "NOT_FOUND",
            "No log file found for the current project",
            {
                "projectDir": project_dir,
                "logsDir": logs_dir,
                "expected": os.path.join(logs_dir, _project_name(project_dir) + ".log"),
            },
        )
    log_path = _safe_log_path(log_path, logs_dir)

    scanned = 0
    matched = 0
    selected = []
    with open(log_path, "r", encoding="utf-8", errors="replace") as handle_file:
        for line_no, raw in enumerate(handle_file, 1):
            scanned += 1
            text = raw.rstrip("\r\n")
            level_match = _LEVEL_RE.search(text) or _FALLBACK_LEVEL_RE.search(text)
            level = level_match.group(1) if level_match else None
            if levels and level not in levels:
                continue
            if since_dt is not None:
                line_time = _parse_line_time(text)
                if line_time is not None and line_time < since_dt:
                    continue
            if regex is not None and not regex.search(text):
                continue
            matched += 1
            if matched <= offset:
                continue
            if len(selected) >= limit:
                continue
            selected.append(
                {"lineNo": line_no, "level": level, "text": text[:_MAX_TEXT]}
            )

    return HandlerResult(
        {
            "logPath": log_path,
            "scannedLines": scanned,
            "matched": matched,
            "truncated": matched > offset + len(selected),
            "lines": selected,
        }
    )
