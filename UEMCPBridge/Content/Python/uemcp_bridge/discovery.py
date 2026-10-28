"""Bridge discovery files (architecture doc section 2.4).

Files written on startup and deleted on editor shutdown:

* ``~/.uemcp/bridges/<projectHash>.json`` (one per project)
* ``~/.uemcp/bridge.json`` (most recently started editor)

Writes are atomic (``.tmp`` + ``os.replace``).  Deletion only removes files that
still belong to this bridge instance (pid + token match).
"""

import ctypes
import datetime
import hashlib
import json
import os
from pathlib import Path

SCHEMA_VERSION = 1


def state_dir():
    return Path(os.path.expanduser("~")) / ".uemcp"


def bridges_dir():
    return state_dir() / "bridges"


def normalize_project_dir(project_dir):
    text = str(project_dir).replace("\\", "/").rstrip("/")
    return text


def project_hash(project_dir):
    # Architecture 2.4: normalize separators and strip the trailing slash,
    # then SHA-1 and keep the first 16 hex characters.  Do not change case;
    # the MCP server must compute the identical hash.
    normalized = normalize_project_dir(project_dir)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
    return digest[:16]


def project_file_path(project_dir):
    return bridges_dir() / ("%s.json" % project_hash(project_dir))


def latest_file_path():
    return state_dir() / "bridge.json"


def write_json_atomic(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        # Windows ACLs do not map to POSIX modes; this is best effort.
        pass


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def pid_alive(pid):
    """Best-effort PID liveness check.

    On Windows ``os.kill(pid, 0)`` terminates the target process, so use
    ``OpenProcess`` instead.  If liveness cannot be determined, assume alive:
    never delete a discovery file we cannot prove stale.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def mark_stale_file(path, reason):
    """Mark an existing discovery file as stale (best effort)."""
    data = _read_json(path)
    if not isinstance(data, dict):
        return False
    data["stale"] = True
    data["staleReason"] = str(reason)
    data["staleAt"] = _utc_now()
    try:
        write_json_atomic(path, data)
        return True
    except Exception:
        return False


def mark_stale(record, reason):
    """Mark the discovery files owned by ``record`` as stale."""
    marked = []
    for path in (project_file_path(record["projectDir"]), latest_file_path()):
        current = _read_json(path)
        if not isinstance(current, dict):
            continue
        if current.get("pid") != record.get("pid"):
            continue
        if current.get("token") != record.get("token"):
            continue
        if mark_stale_file(path, reason):
            marked.append(str(path))
    return marked


def cleanup_stale(project_dir):
    """Remove discovery files for this project whose owner is gone.

    Called on startup so a crash/force-kill cannot leave a permanently stale
    file behind.  Files owned by a live process are never touched.
    """
    removed = []
    for path in (project_file_path(project_dir), latest_file_path()):
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        if data.get("stale") or not pid_alive(data.get("pid")):
            try:
                os.unlink(path)
                removed.append(str(path))
            except OSError:
                # Try to leave a recognisable stale marker instead.
                mark_stale_file(path, "stale_cleanup_failed")
    return removed


def publish(record):
    write_json_atomic(project_file_path(record["projectDir"]), record)
    write_json_atomic(latest_file_path(), record)


def remove(record):
    """Delete only discovery files that still describe this instance."""
    candidates = (project_file_path(record["projectDir"]), latest_file_path())
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                current = json.load(handle)
            if current.get("pid") != record.get("pid"):
                continue
            if current.get("token") != record.get("token"):
                continue
            os.unlink(path)
        except FileNotFoundError:
            continue
        except Exception:
            # Deletion failed: at least leave an explicit stale marker so the
            # MCP server can skip it deterministically.
            mark_stale_file(path, "shutdown_cleanup_failed")
            continue
