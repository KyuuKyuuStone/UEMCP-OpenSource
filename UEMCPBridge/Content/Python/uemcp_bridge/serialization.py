"""Convert UE Python values into JSON-serializable Python values.

Rules from architecture doc section 5.9:

* primitives pass through;
* list/tuple/set/dict recurse;
* ``unreal.Vector`` / ``Rotator`` / ``LinearColor`` become plain dicts;
* ``unreal.Name`` / ``Text`` become strings;
* ``unreal.Object`` becomes its path name;
* anything else uses ``repr()`` truncated to 2000 characters;
* circular references raise :class:`NotSerializable`.
"""

import math

try:
    import unreal  # type: ignore
except Exception:  # pragma: no cover - only absent outside the editor
    unreal = None

_MAX_DEPTH = 12
_MAX_REPR = 2000


class NotSerializable(Exception):
    pass


def _is_instance(value, type_name):
    if unreal is None:
        return False
    type_object = getattr(unreal, type_name, None)
    if type_object is None:
        return False
    try:
        return isinstance(value, type_object)
    except Exception:
        return False


def _normalize_axis(angle):
    """Mirror ``FRotator::NormalizeAxis`` (wrap to (-180, 180])."""
    angle = angle % 360.0
    if angle > 180.0:
        angle -= 360.0
    return angle


def _quat_to_rotator_dict(x, y, z, w):
    """Convert a quaternion to pitch/yaw/roll, mirroring ``FQuat::Rotator()``.

    ``FTransform.rotation`` is an ``unreal.Quat`` (x/y/z/w only); it has no
    pitch/yaw/roll attributes.  This conversion avoids depending on optional
    Python helpers such as ``Quat.rotator()``.
    """
    singularity_test = z * x - w * y
    yaw_y = 2.0 * (w * z + x * y)
    yaw_x = 1.0 - 2.0 * (y * y + z * z)
    threshold = 0.4999995
    rad_to_deg = 180.0 / math.pi

    if singularity_test < -threshold:
        pitch = -90.0
        yaw = math.atan2(yaw_y, yaw_x) * rad_to_deg
        roll = _normalize_axis(-yaw - (2.0 * math.atan2(x, w) * rad_to_deg))
    elif singularity_test > threshold:
        pitch = 90.0
        yaw = math.atan2(yaw_y, yaw_x) * rad_to_deg
        roll = _normalize_axis(yaw - (2.0 * math.atan2(x, w) * rad_to_deg))
    else:
        pitch = math.asin(max(-1.0, min(1.0, 2.0 * singularity_test))) * rad_to_deg
        yaw = math.atan2(yaw_y, yaw_x) * rad_to_deg
        roll = (
            math.atan2(
                -2.0 * (w * x + y * z),
                1.0 - 2.0 * (x * x + y * y),
            )
            * rad_to_deg
        )
    return {"pitch": pitch, "yaw": yaw, "roll": roll}


def rotation_to_dict(value):
    """Serialize an ``FRotator`` or ``FQuat`` as ``{pitch, yaw, roll}``."""
    if value is None:
        return None
    if all(hasattr(value, axis) for axis in ("pitch", "yaw", "roll")):
        return {
            "pitch": float(value.pitch),
            "yaw": float(value.yaw),
            "roll": float(value.roll),
        }
    if all(hasattr(value, axis) for axis in ("x", "y", "z", "w")):
        return _quat_to_rotator_dict(
            float(value.x), float(value.y), float(value.z), float(value.w)
        )
    raise TypeError("not a rotation type: %s" % type(value).__name__)


def to_jsonable(value, _seen=None, _depth=0):
    if _depth > _MAX_DEPTH:
        return repr(value)[:_MAX_REPR]

    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")

    if isinstance(value, dict):
        if _seen is None:
            _seen = set()
        marker = id(value)
        if marker in _seen:
            raise NotSerializable("circular reference in dict")
        _seen.add(marker)
        try:
            result = {}
            for key, item in value.items():
                result[str(to_jsonable(key, _seen, _depth + 1))] = to_jsonable(
                    item, _seen, _depth + 1
                )
            return result
        finally:
            _seen.discard(marker)

    if isinstance(value, (list, tuple, set, frozenset)):
        if _seen is None:
            _seen = set()
        marker = id(value)
        if marker in _seen:
            raise NotSerializable("circular reference in sequence")
        _seen.add(marker)
        try:
            return [to_jsonable(item, _seen, _depth + 1) for item in value]
        finally:
            _seen.discard(marker)

    if _is_instance(value, "Vector"):
        return {"x": float(value.x), "y": float(value.y), "z": float(value.z)}
    # FTransform.rotation is a Quat (x/y/z/w).  Check it explicitly so it
    # never falls through to generic repr serialization.
    if _is_instance(value, "Quat") or _is_instance(value, "Rotator"):
        return rotation_to_dict(value)
    if _is_instance(value, "LinearColor"):
        return {
            "r": float(value.r),
            "g": float(value.g),
            "b": float(value.b),
            "a": float(value.a),
        }
    if _is_instance(value, "Name") or _is_instance(value, "Text"):
        return str(value)
    if _is_instance(value, "Object"):
        try:
            return str(unreal.SystemLibrary.get_path_name(value))
        except Exception:
            return str(value)

    # Enums in UE Python expose ``name``; fall back to repr.
    enum_name = getattr(value, "name", None)
    if isinstance(enum_name, str):
        return enum_name

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return to_jsonable(to_dict(), _seen, _depth + 1)
        except Exception:
            pass

    return repr(value)[:_MAX_REPR]
