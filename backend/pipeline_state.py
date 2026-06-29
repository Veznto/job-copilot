"""In-memory pipeline progress tracking (per role_id)."""
from threading import Lock

_lock = Lock()
_state: dict[int, dict] = {}


def set_state(role_id: int, **kwargs):
    with _lock:
        _state.setdefault(role_id, {"status": "processing"})
        _state[role_id].update(kwargs)


def get_state(role_id: int) -> dict:
    with _lock:
        return dict(_state.get(role_id, {"status": "unknown"}))


def clear_state(role_id: int):
    with _lock:
        _state.pop(role_id, None)
