"""In-memory key-value store for bot conversation state.

Mirrors Marzban's MemoryStorage — simple dict wrapper used to hold
per-chat FSM state during multi-step bot interactions (user creation,
editing, etc.).  State is lost on process restart, which is acceptable
for a Telegram bot since the admin simply re-issues the command.
"""


class MemoryStorage:
    def __init__(self):
        self._data = {}

    def set(self, key, value):
        self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    def delete(self, key):
        self._data.pop(key, None)

    def clear(self):
        self._data.clear()
