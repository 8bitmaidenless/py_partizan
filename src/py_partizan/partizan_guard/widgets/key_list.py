from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import DataTable, Footer, Header, Label


@dataclass
class KeyInfo:
    """
    Normalized representation of a single GPG key for display purposes.
    Built from a python-gnupg key dict via KeyInfo.from_gnupg_dict()
    """
    fingerprint: str
    key_id: str
    uids: list[str]
    name: str
    algorithm: str
    expires: str
    trust: str
    has_secret: bool

    @classmethod
    def from_gnupg_dict(
        cls,
        pub_dict: dict,
        secret_fingerprints: set[str]
    ) -> "KeyInfo":
        """
        Build a KeyInfo from a python-gnupg public key dict plus the set
        of fingerprints that have a corresponding secret key.
        
        Parameters
        ----------
        pub_dict : dict
            One element from `gpg.list_keys(False)`.
        secret_fingerprints : set[str]
            Set of fingerprints from `gpg.list_keys(True)`.
        """
        fp = pub_dict.get("fingerprint", "")
        key_id = fp[-16:] if len(fp) >= 16 else fp
        uids = pub_dict.get("uids", []) or ["<no UID>"]
        name = _first_uid_name(uids[0])
        algo = _format_algorithm(pub_dict)
        expires = _format_expiry(pub_dict.get("expires", ""))
        trust = _expand_trust(pub_dict.get("ownertrust", pub_dict.get("trust", "?")))
        has_sec = fp in secret_fingerprints

        return cls(
            fingerprint=fp,
            key_id=key_id,
            uids=uids,
            name=name,
            algorithm=algo,
            expires=expires,
            trust=trust,
            has_secret=has_sec
        )


_COLUMNS: list[tuple[str, int]] = [
    ("+", 3),
    ("Name / UID", 28),
    ("Key ID", 18),
    ("Algorithm", 12),
    ("Expires", 12),
    ("Trust", 14),
]


class KeyListWidget(DataTable):
    """
    DataTable subclass that displays GPG keys with multi-select support.
    
    Inherit from DataTable directly so we get cursor navigation, keyboard
    handling, and scrolling for free. We extend it with:
        - Custom column schema
        - Row-key -> KeyInfo mapping
        - Multi-select set (Space to toggle)
        - Three outbound message types
        - Optional confirm callback
    """

    class CursorMoved(Message):
        """Posted when the DataTable cursor moves to a new row."""
        def __init__(self, key_info: KeyInfo) -> None:
            super().__init__()
            self.key_info = key_info

    class KeyConfirmed(Message):
        """Posted when the user presses Enter on a row."""
        def __init__(self, key_info: KeyInfo) -> None:
            super().__init__()
            self.key_info = key_info

    class SelectionChanged(Message):
        """Posted when the multi-select set changes."""
        def __init__(self, fingerprints: frozenset[str]) -> None:
            super().__init__()
            self.fingerprints = fingerprints

    BINDINGS = [
        Binding("space", "toggle_select", "Select", show=True),
        Binding("escape", "clear_select", "Clear selection", show=True),
        Binding("enter", "confirm_key", "Confirm", show=True),
        Binding("r", "refresh_table", "Refresh", show=True),
    ]

    def __init__(
        self,
        gpg=None,
        *,
        confirm_callback: Callable[[KeyInfo], None] | None = None,
        **kwargs
    ) -> None:
        """
        Parameters
        ----------
        gpg : gnupg.GPG | None
            The shared GPG instance. If provided, keys are loaded on mount.
            Can be None for standalone demo use.
        confirm_callback : callback | None
            Optional function called with a KeyInfo when the user confirms
            a row (Enter). Called in addition to posting KeyConfirmed.
        """
        super().__init__(cursor_type="row", zebra_stripes=True, **kwargs)
        self._gpg = gpg
        self._confirm_callback = confirm_callback

        self._key_map: dict[str, KeyInfo] = {}
        self._row_key_to_fp: dict[str, str] = {}
        self._selected_fps: set[str] = set()

    def on_mount(self) -> None:
        """Add columns and load keys if a GPG instance was provided."""
        for label, width in _COLUMNS:
            self.add_column(label, width=width)
        if self._gpg is not None:
            self.load(self._gpg)
        
    def load(self, gpg) -> None:
        """
        (Re)load all keys from the keyring into the table.
        
        Clears the current table, fetches public + secret key lists,
        rebuilds `_key_map` and `_row_key_to_fp`, then repopulates the
        DataTable rows. Also clears the multi-select set.
        
        Call this after any operation that mutates the keyring
        (generate, import, delete).
        """
        self._gpg = gpg
        self.clear(columns=False)
        self._key_map.clear()
        self._row_key_to_fp.clear()
        self._selected_fps.clear()

        pub_keys = gpg.list_keys(False)
        secret_fps = {k["fingerprint"] for k in gpg.list_keys(True)}

        for pub_dict in pub_keys:
            info = KeyInfo.from_gnupg_dict(pub_dict, secret_fps)
            self._key_map[info.fingerprint] = info
            row_key = info.fingerprint
            self._row_key_to_fp[row_key] = info.fingerprint
            self.add_row(
                *self._build_row_cells(info, selected=False),
                key=row_key
            )

    def refresh_keys(self, gpg=None) -> None:
        """Alias for `load()`. Accepts an optional updated gpg instance."""
        self.load(gpg or self._gpg)

    def get_selected(self) -> frozenset[str]:
        return frozenset(self._selected_fps)
    
    def get_cursor_key(self) -> KeyInfo | None:
        """Return the KeyInfo for the row currently under the cursor, or None."""
        try:
            row_key = self.get_row_at(self.cursor_row)
        except Exception:
            return None
        
    def clear_selection(self) -> None:
        """Programmatically clear the multi-select set and redraw."""
        self.action_clear_select()

    def select_by_fingerprint(self, fingerprint: str) -> None:
        """Programmatically add a fingerprint to the selection set."""
        if fingerprint in self._key_map:
            self._selected_fps.add(fingerprint)
            self._redraw_row(fingerprint)
            self.post_message(self.SelectionChanged(self.get_selected()))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Fires when cursor moves to a new row - post CursorMoved."""
        event.stop()
        fp = self._row_key_to_fp.get(str(event.row_key.value), "")
        info = self._key_map.get(fp)
        if info:
            self.post_message(self.CursorMoved(info))

    def action_toggle_select(self) -> None:
        """Space - toggle cursor row in/out of the selection set."""
        info = self._info_at_cursor()
        if info is None:
            return
        fp = info.fingerprint
        if fp in self._selected_fps:
            self._selected_fps.discard(fp)
        else:
            self._selected_fps.add(fp)
        self._redraw_row(fp)
        self.post_message(self.SelectionChanged(self.get_selected()))

    def action_clear_select(self) -> None:
        """Escape - clear the entire selection set."""
        fps_to_redraw = set(self._selected_fps)
        self._selected_fps.clear()
        for fp in fps_to_redraw:
            self._redraw_row(fp)
        self.post_message(self.SelectionChanged(self.get_selected()))

    def action_confirm_key(self) -> None:
        """Enter - confirm the current cursor row."""
        info = self._info_at_cursor()
        if info is None:
            return
        self.post_message(self.KeyConfirmed(info))
        if self._confirm_callback:
            self._confirm_callback(info)

    def action_refresh_table(self) -> None:
        """R - reload keys from the keyring."""
        if self._gpg:
            self.load(self._gpg)

    def _info_at_cursor(self) -> KeyInfo | None:
        """Return KeyInfo for the rrow currently under the cursor."""
        if self.row_count == 0:
            return None
        try:
            fp_list = list(self._row_key_to_fp.values())
            if self.cursor_row >= len(fp_list):
                return None
            fp = fp_list[self.cursor_row]
            return self._key_map.get(fp)
        except Exception:
            return None
        
    def _build_row_cells(
        self,
        info: KeyInfo,
        *,
        selected: bool
    ) -> tuple[Text | str, ...]:
        """
        Build the tupls of Rich Text / str cell values for a single row.
        The indicator column combines selection marker and secret-key marker.
        
        """
        sel_marker = "▶" if selected else " "
        sec_marker = "+" if info.has_secret else "·"
        indicator = Text(f"{sel_marker}{sec_marker}", no_wrap=True)
        if selected:
            indicator.stylize("bold yellow")
        elif info.has_secret:
            indicator.stylize("bold cyan")
        else:
            indicator.stylize("dim")

        name_cell = Text(info.name[:26], no_wrap=True)
        if info.has_secret:
            name_cell.stylize("cyan")
        
        key_id_cell = Text(info.key_id, no_wrap=True, style="dim")

        algo_cell = Text(info.algorithm, no_wrap=True)

        expires_cell = Text(info.expires, no_wrap=True)
        if info.expires not in ("never", ""):
            expires_cell.stylize("yellow")

        trust_cell = Text(info.trust, no_wrap=True)
        trust_cell.stylize(_trust_style(info.trust))

        return (
            indicator,
            name_cell,
            key_id_cell,
            algo_cell,
            expires_cell,
            trust_cell,
        )
    
    def _redraw_row(self, fingerprint: str) -> None:
        """
        Update all cells in a row to reflect current selection state.
        DataTable.update_cell() is used per-column since there is no 
        bulk row-update API.
        """
        info = self._key_map.get(fingerprint)
        if info is None:
            return
        selected = fingerprint in self._selected_fps
        cells = self._build_row_cells(info, selected=selected)
        col_keys = [col.key for col in self.columns.values()]
        for col_key, cell_value in zip(col_keys, cells):
            try:
                self.update_cell(
                    row_key=fingerprint,
                    column_key=col_key,
                    value=cell_value,
                    update_width=False,

                )
            except Exception:
                pass

        
def _first_uid_name(uid: str) -> str:
    """
    Extract the display name from a UID string.
    UID Format: "Name (comment) <email>"
    Falls back to the whole UID string if no name part is found.
    """
    m = re.match(r"^([^<(]+)", uid)
    return m.group(1).strip() if m else uid.strip()


def _format_algorithm(key_dict: dict) -> str:
    """
    Build a short algorithm string from a python-gnupg key dict.
    Example: "RSA 4096", "EdDSA 255", "ECDH 256".
    """
    algo = key_dict.get("algo", "")
    length = key_dict.get("length", "")
    curve = key_dict.get("curve", "")

    algo_names = {
        "1": "RSA",
        "2": "RSA",
        "3": "RSA",
        "17": "DSA",
        "18": "ECDH",
        "19": "ECDSA",
        "22": "EdDSA",
    }
    name = algo_names.get(str(algo), str(algo))

    if curve:
        curve_short = {
            "ed25519": "255",
            "cv25519": "255",
            "nistp256": "P256",
            "nistp384": "P384",
            "nistp521": "P521",
        }.get(curve.lower(), curve)
        return f"{name} {curve_short}"
    if length:
        return f"{name} {length}"
    return name


def _format_expiry(expires: str) -> str:
    """Convert a Unix timestamp string to ISO date, or return 'never'."""
    if not expires:
        return "never"
    try:
        import datetime
        ts = int(expires)
        # return datetime.datetime.utcfromtimestamp(datetime.timezone.utc)
        return datetime.datetime.fromtimstamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return expires
    

def _expand_trust(code: str) -> str:
    """Expand a single-char gpg trust code to a short human label."""
    return {
        "u": "ultimate",
        "f": "full",
        "m": "marginal",
        "n": "not trusted",
        "e": "expired",
        "r": "revoked",
        "?": "unknown",
        "-": "unknown",
        "q": "undefined",
    }.get(code.lower(), code)


def _trust_style(trust_label: str) -> str:
    """Return a Rich style string based on the expanded trust label."""
    return {
        "ultimate": "bold green",
        "full": "green",
        "marginal": "yellow",
        "not trusted": "dim red",
        "expired": "bold red",
        "revoked": "bold red",
        "unknown": "dim",
        "undefined": "dim,"
    }.get(trust_label, "")


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))

    try:
        from py_partizan.cipherlib import build_gpg, generate_key
    except ImportError:
        print("`cipherlib` not found - run from the project root.")
        sys.exit(1)

    class _DemoApp(App):
        TITLE = "KeyListWidget - demo"
        BINDINGS = [Binding("q", "quit", "Quit")]

        def compose(self) -> ComposeResult:
            yield Header()
            yield KeyListWidget(id="key-list")
            yield Label("", id="status")
            yield Footer()

        def on_mount(self) -> None:
            gpg = build_gpg()

            generate_key(
                gpg,
                "Alice Demo",
                "alice@demo.test",
                algorithm="ecc",
                expire="1y",
                comment="Test ECC key",
                passphrase="password666",
            )
            generate_key(
                gpg,
                "Bob Demo",
                "bob@demo.test",
                algorithm="rsa",
                expire="2y",
                comment="Test RSA key",
                passphrase="password666"
            )
            self.query_one("#key-list", KeyListWidget).load(gpg)

        def on_key_list_widget_cursor_move(
            self,
            event: KeyListWidget.CursorMoved
        ) -> None:
            self.query_one("#status", Label).update(
                f"  Cursor → {event.key_info.name}  |  {event.key_info.key_id}"
            )

        def on_key_list_widget_key_confirmed(
            self,
            event: KeyListWidget.KeyConfirmed
        ) -> None:
            self.query_one("#status", Label).update(
                f"  Confirmed: {event.key_info.name}  FP:  {event.key_info.fingerprint}"
            )

        def on_key_list_widget_selection_changed(
            self,
            event: KeyListWidget.SelectionChanged
        ) -> None:
            n = len(event.fingerprints)
            self.query_one("#status", Label).update(
                f"  {n} key(s) selected"
                if n else "  Selection cleared"
            )

    _DemoApp().run()


