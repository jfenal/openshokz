"""Language priority section with drag-to-reorder rows."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from ui.headset import run_openshokz  # noqa: E402

LANGUAGES = [
    ("en", "🇬🇧 English"),
    ("zh", "🇨🇳 Chinese"),
    ("ko", "🇰🇷 Korean"),
    ("ja", "🇯🇵 Japanese"),
]


class LanguageSection(Adw.PreferencesGroup):
    def __init__(self) -> None:
        super().__init__()
        self.set_title("Language Priority")
        self.set_description("Drag to reorder voice prompt languages")

        self._order: list[int] = list(range(len(LANGUAGES)))  # indices into LANGUAGES

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._listbox.add_css_class("boxed-list")
        self._rows: list[Adw.ActionRow] = []

        for i, (_code, display) in enumerate(LANGUAGES):
            row = Adw.ActionRow()
            row.set_title(display)

            handle = Gtk.Image.new_from_icon_name("open-menu-symbolic")
            handle.set_tooltip_text("Drag to reorder")
            row.add_suffix(handle)

            drag_source = Gtk.DragSource()
            drag_source.connect("prepare", self._on_drag_prepare, i)
            drag_source.connect("drag-begin", self._on_drag_begin, row)
            row.add_controller(drag_source)

            drop_target = Gtk.DropTarget.new(GLib.TYPE_INT, Gdk.DragAction.MOVE)
            drop_target.connect("drop", self._on_drop, i)
            row.add_controller(drop_target)

            self._rows.append(row)
            self._listbox.append(row)

        self.add(self._listbox)  # type: ignore[arg-type]

        self._apply_btn = Adw.ButtonRow()
        self._apply_btn.set_title("Apply order")
        self._apply_btn.add_css_class("suggested-action")
        self._apply_btn.connect("activated", self._on_apply)
        self.add(self._apply_btn)

    def _on_drag_prepare(
        self, _source: Gtk.DragSource, _x: float, _y: float, idx: int
    ) -> Gdk.ContentProvider:
        return Gdk.ContentProvider.new_for_value(GLib.Variant("i", idx))

    def _on_drag_begin(self, source: Gtk.DragSource, drag: Gdk.Drag, row: Adw.ActionRow) -> None:
        icon = Gtk.DragIcon.get_for_drag(drag)
        label = Gtk.Label(label=row.get_title())
        label.add_css_class("drag-icon")
        icon.set_child(label)

    def _on_drop(
        self, _target: Gtk.DropTarget, value: int, _x: float, _y: float, dest_idx: int
    ) -> bool:
        src_idx = int(value)
        if src_idx == dest_idx:
            return False
        self._order.insert(dest_idx, self._order.pop(src_idx))
        self._rebuild_list()
        return True

    def _rebuild_list(self) -> None:
        for row in self._rows:
            self._listbox.remove(row)
        self._rows = [self._rows[i] for i in self._order]
        for row in self._rows:
            self._listbox.append(row)
        self._order = list(range(len(LANGUAGES)))

    def _on_apply(self, _: Adw.ButtonRow) -> None:
        codes = [LANGUAGES[i][0] for i in range(len(self._rows))]
        run_openshokz("lang", *codes)

    def refresh(self, connected: bool) -> None:
        self._apply_btn.set_sensitive(connected)
        for row in self._rows:
            row.set_sensitive(connected)
