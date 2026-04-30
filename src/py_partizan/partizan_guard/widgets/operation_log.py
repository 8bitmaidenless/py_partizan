from __future__ import annotations

import datetime
from pathlib import Path
from typing import Literal

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Label, RichLog


Level = Literal["OK", "ERR", "WARN", "INFO"]

_LEVEL_STYLE: dict[str, tuple[str, str]] = {
    "OK": ("[OK]  ", "green"),
    "ERR": ("[ERR]  ", "bold red"),
    "WARN": ("[WARN]", "yellow"),
    "INFO": ("[INFO]", "dim white"),
}

_LEVEL_ALIASES: dict[str, str] = {
    "ok": "OK",
    "err": "ERR",
    "error": "ERR",
    "warn": "WARN",
    "warning": "WARN",
    "info": "INFO",
}


def _normalize_level(level: str) -> str:
    return _LEVEL_ALIASES.get(level.lower(), _LEVEL_ALIASES.get(level, "INFO"))


class OperationLog(RichLog):
    DEFAULT_CSS = ""
    COMPONENT_CLASSES = {"operation-log"}

    def __init__(self, **kwargs):
        super().__init__(
            highlight=False,
            markup=False,
            wrap=True,
            **kwargs
        )

        self._plain_lines: list[str] = []

    def log(self, message: str, level: str = "INFO") -> None:
        canonical = _normalize_level(level)
        prefix, color = _LEVEL_STYLE[canonical]
        timestamp = _timestamp()

        line = Text()
        line.append(timestamp, style="dim")
        line.append("  ")
        line.append(prefix, style=color)
        line.append("  ")
        line.append(message, style=color if canonical == "ERR" else "")

        plain = f"{timestamp}  {prefix}  {message}"
        self._plain_lines.append(plain)

        self.write(line)

    def log_result(
        self,
        ok: bool,
        label: str,
        detail: str | None = None,
    ) -> None:
        self.log(label, level="OK" if ok else "ERR")
        if detail:
            self.log(detail, level="INFO")

    def log_separator(self, label: str = "") -> None:
        width = 60
        if label:
            pad = max(0, (width - len(label) - 2) // 2)
            text = f"{'-' * pad} {label} {'-' * pad}"
        else:
            text = "-" * width

        line = Text(text, style="dim")
        self._plain_lines.append(text)
        self.write(line)

    def clear(self) -> None:
        super().clear()
        self._plain_lines.clear()

    def save(self, path: Path | str | None = None) -> Path | None:
        if not self._plain_lines:
            self.log("Log is empty - nothing to save.", level="WARN")
            return None
        
        if path is None:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = Path.cwd() / f"gpg_log_{stamp}.txt"

        dest = Path(path)
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("\n".join(self._plain_lines) + "\n", encoding="utf-8")

            self.log(f"Log saved → {dest}", level="OK")
            return dest
        except OSError as exc:
            self.log(f"Failed to save log: {exc}", level="ERR")
            return None


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


if __name__ == "__main__":
    import asyncio

    class _DemoApp(App):

        TITLE = "OperationLog - demo"
        BINDINGS = [
            Binding("s", "save_log", "Save log"),
            Binding("c", "clear_log", "Clear"),
            Binding("q", "quit", "Quit"),
        ]

        def compose(self) -> ComposeResult:
            yield Header()
            yield Label(
                "  Press [b]S[/b] to save log  |  [b]C[/b] to clear  |  [b]Q[/b] to quit",
                id="demo-hint",
                markup=True
            )
            yield OperationLog(id="op-log")
            yield Footer()

        def on_mount(self) -> None:
            log = self.query_one("#op-log", OperationLog)
            log.clear()

            log.log_separator("Key Generation")
            log.log_result(
                ok=True,
                label="generate_key(alice@example.com)",
                detail="FP: A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2"
            )
            log.log_result(
                ok=True,
                label="generate_key(bob@example.com)",
                detail="FP: 0011223344556677889900112233445566778899",
            )

            log.log_separator("Encryption")
            log.log_result(
                ok=True,
                label="encrypt_to_recipients([bob@example.com])"
            )
            log.log_result(
                ok=False,
                label="encrypt_to_recipients([unknown@example.com])",
                detail="No public key found for recipient."
            )

            log.log_separator("Miscellaneous")
            log.log("Symmetric passphrase was empty.", level="WARN")
            log.log("GPG binary not found at /usr/bin/gpg2", level="ERR")
            log.log("Keyring path: /home/user/.gnupg", level="INFO")
        
        def action_save_log(self) -> None:
            log = self.query_one("#op-log", OperationLog)
            log.save()

        def action_clear_log(self) -> None:
            log = self.query_one("#op-log", OperationLog)
            log.clear()
            log.log("Log cleared.", level="INFO")

    _DemoApp().run()