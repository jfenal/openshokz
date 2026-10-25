"""Language selector section."""

from __future__ import annotations

import gi

import openshokz.core as _core
from openshokz.ui.headset import ModelData, run_async

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

_LANGUAGES = [
    ("en", "English"),
    ("zh", "Chinese"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
]


class LanguageSection(Adw.PreferencesGroup):
    def __init__(self) -> None:
        super().__init__()
        self.set_title("Language")
        self.set_description("Voice prompt language for the headset")

        self._codes = [code for code, _ in _LANGUAGES]
        self._connection: tuple[str, ModelData, int] | None = None

        self._combo = Adw.ComboRow()
        self._combo.set_title("Voice Language")
        self._combo.set_model(Gtk.StringList.new([name for _, name in _LANGUAGES]))
        self._combo.set_sensitive(False)
        self._combo.connect("notify::selected", self._on_changed)
        self.add(self._combo)

    def _on_changed(self, combo: Adw.ComboRow, _pspec: object) -> None:
        if self._connection is None:
            return
        idx = combo.get_selected()
        if idx >= len(self._codes):
            return
        mac, model, channel = self._connection
        combo.set_sensitive(False)

        def _done(_result: object, _error: object) -> None:
            combo.set_sensitive(self._connection is not None)

        run_async(_done, _core.apply_lang_slots, mac, model, channel, [self._codes[idx]])

    def refresh(
        self,
        connected: bool,
        mac: str | None = None,
        model: ModelData | None = None,
        channel: int | None = None,
    ) -> None:
        self._connection = (
            (mac, model, channel) if connected and mac and model and channel else None
        )  # type: ignore[assignment]
        self._combo.set_sensitive(connected)
