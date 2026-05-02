from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.message import Message
from textual.widgets import DataTable, Footer, Header, Label, Static

from py_partizan.partizan_guard.widgets.key_list import (
    KeyInfo,
    _expand_trust,
    _format_algorithm,
    _format_expiry
)


_PLACEHOLDER = "- select a key to view details -"


_USAGE_FLAGS: dict[str, str] = {
    "e": "encrypt",
    "s": "sign",
    "c": "certify",
    "a": "auth",
}


def _decode_usage(usage_str: str) -> str:
    """
    Decode a gpg usage flag string (e.g. 'esca') into a readable label.
    Returns comma-separated capability names, e.g. "sign, certify".
    """
    if not usage_str:
        return "-"
    parts = [_USAGE_FLAGS.get(ch, ch) for ch in usage_str.lower()]
    return ", ".join(dict.fromkeys(parts))


class KeyDetailWidget(ScrollableContainer):
    """
    Scrollable panel displaying full details for a single GPG key.
    
    """
    class ExportCompleted(Message):
        """Posted after a quick-export attempt (success or failure)."""
        def __init__(self, path: Path | None, ok: bool) -> None:
            super().__init__()
            self.path = path
            self.ok = ok

    BINDINGS = [
        Binding("c", "copy_fingerprint", "Copy FP", show=True),
        Binding("x", "export_key", "Export .asc", show=True),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_info: KeyInfo | None = None
        self._gpg: None

    def compose(self) -> ComposeResult:
        # yield Static(_PLACEHOLDER, id="kd-placeholder")
        yield Static(_PLACEHOLDER, classes="kd-placeholder")
        
    def show(self, key_info: KeyInfo, gpg) -> None:
        """
        Render full details for the given KeyInfo.
        
        Fetches subkey data from the live keyring (requires gpg).
        Replaces current current content entirely - safe to call repeatedly
        as the user moves through the key list.
        
        Parameters
        ----------
        key_info : KeyInfo
            The key to display (from KeyListWidget.CursorMoved).
        gpg : gnupg.GPG
            Shared GPG instance - used to fetch subkeys and for export.
            
        """
        self._current_info = key_info
        self._gpg = gpg

        subkeys = self._fetch_subkeys(gpg, key_info.fingerprint)
        self._rebuild(key_info, subkeys)

    def clear(self) -> None:
        """Return the widget to it's empty placeholder state."""
        self._current_info = None
        # self._replace_content([Static(_PLACEHOLDER, id="kd-placeholder")])
        self._replace_content([Static(_PLACEHOLDER, classes="kd-placeholder")])
        
    def action_copy_fingerprint(self) -> None:
        """
        Copy the full fingerprint of the currently displayed key to the
        system clipboard via pyperclip.
        
        Falls back gracefully if pyperclip is not installed or if the
        platform clipboard is unavailable (e.g. headless server).
        
        """
        if self._current_info is None:
            return
        fp = self._current_info.fingerprint
        try:
            import pyperclip
            pyperclip.copy(fp)
            self.notify(f"Fingerprint copied to clipboard.", title="Copied")
        except ImportError:
            self.notify(
                "pyperclip is not installed.\n"
                "pip install pyperclip  to enable clipboard support.\n"
                f"FP: {fp}",
                title="Clipboard unavailable",
                severity="warning"
            )
        except Exception as exc:
            self.notify(str(exc), title="Clipboard error", severity="warning")

    def action_export_key(self) -> None:
        """
        Quick-export the displayed public key as an ASCII-armored .asc file
        to the current working directory.
        
        Filename: <last-16-of-fingerprint>.asc
        Posts ExportCompleted so the parent screen can log the result.
        
        """
        if self._current_info is None or self._gpg is None:
            return
        
        info = self._current_info
        filename = f"{info.key_id}.asc"
        dest = Path.cwd() / filename

        try:
            armored = self._gpg.export_keys(info.fingerprint, armor=True)
            if not armored:
                self.post_message(self.ExportCompleted(path=None, ok=False))
                self.notify("Export failed - no key data returned.", severity="error")
                return
            dest.write_text(armored, encoding="utf-8")
            self.post_message(self.ExportCompleted(path=dest, ok=True))
            self.notify(f"Exported → {dest.name}", title="Export complete")
        except OSError as exc:
            self.post_message(self.ExportCompleted(path=None, ok=False))
            self.notify(str(exc), title="Export failed", severity="error")

    def _rebuild(self, info: KeyInfo, subkeys: list[dict]) -> None:
        """Rebuild the full detail content for a given KeyInfo."""
        nodes = []

        nodes.append(self._section_label("KEY IDENTITY"))
        # nodes.append(self._field("Type", "Pub + Sec" if info.has_secret else "Public only"))
        nodes.append(self._field(
            "Type",
            "Pub + Sec" if info.has_secret else "Public only",
            value_style="bold cyan" if info.has_secret else "dim"
        ))
        nodes.append(self._field("Key ID", info.key_id))
        nodes.append(self._field("Algorithm", info.algorithm))
        nodes.append(self._field(
            "Expires",
            info.expires,
            value_style="yellow" if info.expires != "never" else ""
        ))
        nodes.append(self._field(
            "Trust",
            info.trust,
            value_style=_trust_style_str(info.trust)
        ))

        nodes.append(self._section_label("FINGERPRINT"))
        nodes.append(Static(
            _format_fingerprint(info.fingerprint),
            # id="kd-fingerprint"
            classes="kd-fingerprint"
        ))

        nodes.append(self._section_label(f"USER IDs  ({len(info.uids)})"))
        # for i, uid in enumerate(info.uids):
        for uid in info.uids:
            # nodes.append(Static(f"[{i+1}]  {uid}", id=f"kd-uid-{i+1}", classes="kd-uid"))
            nodes.append(Static(f"  {uid}", classes="kd-uid"))

        nodes.append(self._section_label(f"SUBKEYS  ({len(subkeys)})"))
        if subkeys:
            nodes.append(self._build_subkey_table(subkeys))
        else:
            nodes.append(Static("  (no subkeys)", classes="kd-empty"))

        nodes.append(Static(
            "\n  [b]C[/b] - copy fingerprint    [b]X[/b] - export public key (.asc)",
            # id="kd-hint",
            classes="kd-hint",
            markup=True
        ))

        self._replace_content(nodes)

    def _replace_content(self, nodes: list) -> None:
        # """
        # Remove all current children and mount the new node list.
        # Uses `remove_children()` + `mount()` which is the correct Textual
        # pattern for dynamic content replacement inside a container.
        # """
        """
        """
        self._pending_nodes = nodes
        self.remove_children()
        # self.mount(*nodes)
        self.call_after_refresh(self._mount_pending)
        # self.scroll_home(animate=False)

    def _mount_pending(self) -> None:
        nodes = getattr(self, "_pending_nodes", [])
        if nodes:
            self.mount(*nodes)
            self.scroll_home(animate=False)
            self._pending_nodes = []

    def _section_label(self, text: str) -> Static:
        """A styled section heading."""
        return Static(f"\n  {text}", classes="kd-section-label")
    
    def _field(
        self,
        label: str,
        value: str,
        *,
        value_style: str = ""
    ) -> Static:
        """
        A single label: value line
        Rich Text is used so the label and value can have independent styles.
        """
        line = Text()
        line.append(f"  {label:<12}", style="dim")
        line.append(value, style=value_style)
        return Static(line, classes="kd-field")
    
    def _build_subkey_table(self, subkeys: list[dict]) -> DataTable:
        """
        Build a non-interactive DataTable for the subkey list.
        Columns: Key ID | Algorithm | Usage | Expires
        """
        table: DataTable = DataTable(
            show_cursor=False,
            zebra_stripes=True,
            # id="kd-subkey-table",
            classes="kd-subkey-table"
        )
        table.add_column("Subkey ID", width=18)
        table.add_column("Algorithm", width=12)
        table.add_column("Usage", width=20)
        table.add_column("Expires", width=12)

        for sk in subkeys:
            sk_id = (sk.get("keyid", "") or "")[-16:]
            sk_algo = _format_algorithm(sk)
            sk_use = _decode_usage(sk.get("cap", sk.get("usage", "")))
            sk_exp = _format_expiry(sk.get("expires", ""))

            exp_text = Text(sk_exp)
            if sk_exp not in ("never", ""):
                exp_text.stylize("yellow")

            table.add_row(
                Text(sk_id, style="dim"),
                Text(sk_algo),
                Text(sk_use),
                exp_text
            )
        return table
    
    def _fetch_subkeys(self, gpg, fingerprint: str) -> list[dict]:
        try:
            all_keys = gpg.list_keys(False)
        except Exception:
            return []
        
        for key in all_keys:
            if key.get("fingerprint") == fingerprint:
                return _parse_subkeys(key)
        return []
    

def _parse_subkeys(key_dict: dict) -> list[dict]:
    raw_subkeys = key_dict.get("subkeys", [])
    subkey_info = key_dict.get("subkey_info", {})
    results = []

    for entry in raw_subkeys:
        if not entry:
            continue
        sk_keyid = entry[0] if len(entry) > 0 else ""
        sk_cap = entry[1] if len(entry) > 1 else ""
        sk_fp = entry[2] if len(entry) > 2 else ""

        extra = subkey_info.get(sk_fp, {})

        results.append({
            "keyid": sk_keyid,
            "cap": sk_cap,
            "algo": extra.get("algo", key_dict.get("algo", "")),
            "length": extra.get("length", key_dict.get("length", "")),
            "curve": extra.get("curve", key_dict.get("curve", "")),
            "expires": extra.get("expires", ""),
        })

    return results


def _format_fingerprint(fp: str) -> str:
    if len(fp) != 40:
        return f"  {fp}"
    halves = []
    for half_start in (0, 20):
        half = fp[half_start:half_start + 20]
        groups = [half[i:i+4] for i in range(0, 20, 4)]
        halves.append(" ".join(groups))
    return f"  {halves[0]}  {halves[1]}"


def _trust_style_str(trust_label: str) -> str:
    return {
        "ultimate": "bold green",
        "full": "green",
        "marginal": "yellow",
        "not trusted": "dim red",
        "expired": "bold red",
        "revoked": "bold red",
        "unknown": "dim",
        "undefined": "dim",
    }.get(trust_label, "")


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))

    try:
        from py_partizan.cipherlib import build_gpg, generate_key
    except ImportError:
        print("cipherlib not found - run from the project root.")
        sys.exit(1)

    from textual.containers import Horizontal
    from py_partizan.partizan_guard.widgets.key_list import KeyListWidget

    class _DemoApp(App):
        TITLE = "KeyDetailWidget - demo"
        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("tag", "switch_focus", "Switch pane"),
        ]
        CSS = """
        Horizontal { height: 1fr; }
        KeyListWidget { width: 1fr; border: tall $primary-darken-1; }
        KeyDetailWidget { width: 1fr; border: tall $primary-darken-1; padding: 0 1; }
        .kd-section-label { color: $primary; text-style: bold; }
        .kd-field { color: $text; }
        .kd-uid { color: $text-muted; }
        .kd-empty { color: $text-muted; }
        #kd-fingerprint { color: $text; padding: 0 0 0 0; }
        #kd-hint { color: $text-muted; }
        #kd-subkey-table { height: auto; max-height: 10; margin: 0 2; }
        #kd-placeholder { color: $text-muted; padding: 2 2; }
        """

        def compose(self) -> ComposeResult:
            yield Header()
            with Horizontal():
                yield KeyListWidget(id="key-list")
                yield KeyDetailWidget(id="key-detail")
            yield Footer()

        def on_mount(self) -> None:
            self._gpg = build_gpg()
            generate_key(
                self._gpg,
                "Alice Demo",
                "alice@demo.text",
                algorithm="ecc",
                expire="1y",
                comment="ECC demo key",
                passphrase="password666"
            )
            generate_key(
                self._gpg,
                "Bob Demo",
                "bob@demo.test",
                algorithm="rsa",
                expire="2y",
                comment="RSA demo key",
                passphrase="password666"
            )
            self.query_one("#key-list", KeyListWidget).load(self._gpg)
            self.query_one("#key-list").focus()

        def on_key_list_widget_cursor_moved(
            self,
            event: KeyListWidget.CursorMoved
        ) -> None:
            self.query_one("#key-detail", KeyDetailWidget).show(
                event.key_info,
                self._gpg
            )
        
        def on_key_detail_widget_export_completed(
            self,
            event: KeyDetailWidget.ExportCompleted
        ) -> None:
            status = f"Exported → {event.path}" if event.ok else "Export failed"
            self.notify(status)

        def action_switch_focus(self) -> None:
            focused = self.focused
            if focused and focused.id == "key-list":
                self.query_one("#key-detail").focus()
            else:
                self.query_one("#key-list").focus()

    _DemoApp().run()
