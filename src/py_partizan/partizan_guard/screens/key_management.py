from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header
from textual.worker import Worker, WorkerState

from py_partizan.cipherlib import (
    delete_key,
    export_public_key,
    generate_key,
    import_key_data,
    import_key_file
)
from py_partizan.partizan_guard.widgets.key_detail import KeyDetailWidget
from py_partizan.partizan_guard.widgets.key_list import KeyInfo, KeyListWidget
from py_partizan.partizan_guard.widgets.operation_log import OperationLogWidget
from py_partizan.partizan_guard.screens.modals.generate_key_modal import GenerateKeyModal, GenerateKeyResult
from py_partizan.partizan_guard.screens.modals.import_key_modal import ImportKeyModal, ImportKeyResult
from py_partizan.partizan_guard.screens.modals.trust_modal import TrustModal, TrustResult

_CSS_DIR = Path(__file__).parent.parent / "css"


class KeyManagementScreen(Screen):
    """
    Full key management interface.
    
    Receives the shared GPG instance from GPGApp and passes it down to
    every widget and worker that needs it. Never constructs its own GPG 
    instance.
    """

    TITLE = "Key Management"

    CSS_PATH = [
        str(_CSS_DIR / "key_list.tcss"),
        str(_CSS_DIR / "key_detail.tcss"),
        str(_CSS_DIR / "key_management.tcss"),
    ]

    BINDINGS = [
        Binding("g", "generate_key", "Generate", show=True),
        Binding("i", "import_key", "Import", show=True),
        Binding("e", "export_key", "Export", show=True),
        Binding("d", "delete_key", "Delete", show=True),
        Binding("t", "set_trust", "Trust", show=True),
        Binding("s", "save_log", "Save log", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("tab", "cycle_focus", "Switch pane", show=True),
        Binding("q", "go_home", "Home", show=True),
    ]

    def __init__(self, gpg, **kwargs) -> None:
        super().__init__(**kwargs)
        self.gpg = gpg

        self._pending_delete_fp: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="km-body"):
            with Horizontal(id="km-top"):
                yield KeyListWidget(
                    gpg=self.gpg,
                    id="km-key-list"
                )
                yield KeyDetailWidget(id="km-key-detail")
            yield OperationLogWidget(id="km-op-log")
        yield Footer()

    def on_mount(self) -> None:
        """Clear the log, load the key list, focus the list."""
        log = self._log
        log.clear()
        log.log_separator("Key Management")
        log.log(f"Keyring: {self.gpg.gnupghome}", level="INFO")

        key_list = self._key_list
        key_list.load(self.gpg)
        key_count = key_list.row_count
        log.log(f"{key_count} key(s) loaded from keyring.", level="INFO")
        key_list.focus()

    def on_screen_resume(self) -> None:
        """Called every time this screen becomes active after navigation."""
        self._log.clear()
        self._log.log_separator("Key Management")
        self._key_list.refresh_keys(self.gpg)
        self._key_list.focus()

    def on_key_list_widget_cursor_moved(
        self,
        event: KeyListWidget.CursorMoved
    ) -> None:
        """Update detail panel as cursor moves through the key list."""
        self._key_detail.show(event.key_info, self.gpg)

    def on_key_list_widget_key_confirmed(
        self,
        event: KeyListWidget.KeyConfirmed
    ) -> None:
        """Enter on the key list - focus the detail panel."""
        self._key_detail.focus()

    def on_key_detail_widget_export_completed(
        self,
        event: KeyDetailWidget.ExportCompleted
    ) -> None:
        """Quick-export from the detail panel - log the result."""
        log = self._log
        if event.ok:
            log.log_result(
                ok=True,
                label="quick-export",
                detail=f"→ {event.path}"
            )
        else:
            log.log_result(
                ok=False,
                label="quick-export failed"
            )

    def action_generate_key(self) -> None:
        """Open the GenerateKeyModal, then run `generate_key()` in a worker."""
        self.app.push_screen(
            GenerateKeyModal(),
            callback=self._on_generate_modal_result
        )
    
    def _on_generate_modal_result(self, result: GenerateKeyResult) -> None:
        if result.cancelled:
            self._log.log("Key Generation cancelled", level="INFO")
            return
        if result.was_empty_passphrase:
            self._log.log(
                "No passphrase provided - secret key will be unprotected.",
                level="WARN"
            )
        self._log.log_separator(f"Generating key for [b]{result.email}[/b]")
        self.run_worker(
            self._worker_generate(result),
            thread=True,
            name="generate_key"
        )

    async def _worker_generate(self, result: GenerateKeyResult) -> None:
        """Blocking GPG call - runs in a thread worker."""
        fp = await asyncio.to_thread(
            generate_key,
            self.gpg,
            result.name,
            result.email,
            comment="",
            expire=result.expire,
            algorithm=result.algorithm,
            passphrase=result.passphrase
        )
        self.app.call_from_thread(self._finish_generate, fp, result.email)

    def _finish_generate(self, fp: str | None, email: str) -> None:
        log = self._log
        if fp:
            log.log_result(
                ok=True,
                label=f"generate_key({email})",
                detail=f"FP: {fp}"
            )
            self._key_list.refresh_keys(self.gpg)
        else:
            log.log_result(ok=False, label=f"generate_key({email})")

    def action_import_key(self) -> None:
        """Open the `ImportKeyModal`, then run the appropriate import in a worker."""
        self.app.push_screen(
            ImportKeyModal(),
            callback=self._on_import_modal_result
        )

    def _on_import_modal_result(self, result: ImportKeyResult) -> None:
        if result.cancelled:
            self._log.log("Key import cancelled.", level="INFO")
            return
        self._log.log_separator("Import Key")
        self.run_worker(
            self._worker_import(result),
            thread=True,
            name="import_key"
        )

    async def _worker_import(self, result: ImportKeyResult) -> None:
        if result.mode == "armor":
            fps = await asyncio.to_thread(
                import_key_data,
                self.gpg,
                result.armor_text,
                label="import (armor)"
            )
        else:
            path = Path(result.file_path)
            fps = await asyncio.to_thread(
                import_key_file,
                self.gpg,
                path,
                label=f"import ({path.name})"
            )
        self.app.call_from_thread(self._finish_import, fps)

    def _finish_import(self, fps: list[str]) -> None:
        log = self._log
        if fps:
            log.log_result(
                ok=True,
                label=f"import_key - {len(fps)} key(s) imported",
                detail="; ".join(fp[-16:] for fp in fps)
            )
            self._key_list.refresh_keys(self.gpg)
        else:
            log.log_result(ok=False, label="import_key - no keys imported")

    def action_export_key(self) -> None:
        """Export the currently selected key's public key to cwd as <keyid>.asc."""
        info = self._cursor_key
        if info is None:
            self._log.log(
                "No key selected - move the cursor to a key first.",
                level="WARN"
            )
            return
        self._log.log_separator(f"Export: {info.name}")
        self.run_worker(
            self._worker_export(info),
            thread=True,
            name="export_key"
        )

    async def _worker_export(self, info: KeyInfo) -> None:
        dest = Path.cwd() / f"{info.key_id}.asc"
        data = await asyncio.to_thread(
            export_public_key,
            self.gpg,
            info.fingerprint,
            armor=True,
            output_path=dest
        )
        ok = bool(data)
        self.app.call_from_thread(self._finish_export, ok, dest)

    def _finish_export(self, ok: bool, dest: Path) -> None:
        self._log.log_result(
            ok=ok,
            label="export_public_key",
            detail=f"→ {dest}" if ok else None
        )
    
    def action_delete_key(self) -> None:
        """
        Prompt for confirmation via a notification, then delete both the
        secret and public keys for the selected fingerprint.
        """
        info = self._cursor_key
        if info is None:
            self._log.log("No key selected.", level="WARN")
            return
        
        self._pending_delete_fp = info.fingerprint
        self.notify(
            f"[i]Delete[/i] key for [b]{info.name}[/b]?\n"
            f"Key ID: [b]{info.key_id}[/b]\n\n"
            "[i]Press [b]Y[/b] to confirm, any other key to cancel.[/i]",
            title="Confirm Deletion",
            severity="warning",
            timeout=10,
            markup=True
        )

    def on_key(self, event) -> None:
        """Intercept Y/N after a delete confirmation notification."""
        if self._pending_delete_fp is None:
            return
        if event.key.lower() == "y":
            fp = self._pending_delete_fp
            self._pending_delete_fp = None
            event.stop()
            self._log.log_separator("Delete Key")
            self.run_worker(
                self._worker_delete(fp),
                thread=True,
                name="delete_key"
            )
        else:
            self._pending_delete_fp = None
            self._log.log("Deletion cancelled.", level="INFO")

    async def _worker_delete(self, fp: str) -> None:
        ok_sec = await asyncio.to_thread(
            delete_key,
            self.gpg,
            fp,
            secret=True
        )
        ok_pub = await asyncio.to_thread(
            delete_key,
            self.gpg,
            fp,
            secret=False
        )
        self.app.call_from_thread(self._finish_delete, ok_sec, ok_pub, fp)

    def _finish_delete(
        self,
        ok_sec: bool,
        ok_pub: bool,
        fp: str
    ) -> None:
        log = self._log
        log.log_result(ok=ok_sec, label=f"delete secret key ({fp[-16:]})")
        log.log_result(ok=ok_pub, label=f"delete public key ({fp[-16:]})")
        if ok_pub:
            self._key_detail.clear()
            self._key_list.refresh_keys(self.gpg)

    def action_set_trust(self) -> None:
        """Open the `TrustModal` for the currently selected key."""
        info = self._cursor_key
        if info is None:
            self._log.log("No key selected.", level="WARN")
            return
        self.app.push_screen(
            TrustModal(
                key_label=info.name,
                current_trust=info.trust
            ),
            callback=self._on_trust_modal_result
        )

    def _on_trust_modal_result(self, result: TrustResult) -> None:
        if result.cancelled:
            self._log.log("Trust assignment cancelled.", level="INFO")
            return
        info = self._cursor_key
        if info is None:
            return
        self._log.log_separator(f"Set Trust: {info.name}")
        self.run_worker(
            self._worker_set_trust(info.fingerprint, result.trust_value),
            thread=True,
            name="set_trust"
        )

    async def _worker_set_trust(self, fp: str, trust_value: str) -> None:
        try:
            await asyncio.to_thread(
                self.gpg.trust_keys,
                fp,
                trust_value
            )
            ok = True
        except Exception as exc:
            ok = False
        self.app.call_from_thread(self._finish_trust, ok, fp, trust_value)

    def _finish_trust(self, ok: bool, fp: str, trust_value: str) -> None:
        self._log.log_result(
            ok=ok,
            label=f"trust_keys({fp[-16:]}, {trust_value})"
        )
        if ok:
            self._key_list.refresh_keys(self.gpg)
            info = self._cursor_key
            if info:
                self._key_detail.show(info, self.gpg)

    def action_save_log(self) -> None:
        self._log.save()

    def action_refresh(self) -> None:
        self._log.log("Refreshing keyring...", level="INFO")
        self._key_list.refresh_keys(self.gpg)
        self._log.log(
            f"{self._key_list.row_count} key(s) in keyring.",
            level="INFO"
        )
    
    def action_cycle_focus(self) -> None:
        """Tab - cycle focus between the key list and detail panel."""
        focused = self.focused
        if focused and focused.id == "km-key-list":
            self._key_detail.focus()
        else:
            self._key_list.focus()

    def action_go_home(self) -> None:
        self.app.switch_screen("home") if "home" in self.app._installed_screens else self.app.pop_screen()

    @property
    def _log(self) -> OperationLogWidget:
        return self.query_one("#km-op-log", OperationLogWidget)
    
    @property
    def _key_list(self) -> KeyListWidget:
        return self.query_one("#km-key-list", KeyListWidget)
    
    @property
    def _key_detail(self) -> KeyDetailWidget:
        return self.query_one("#km-key-detail", KeyDetailWidget)
    
    @property
    def _cursor_key(self) -> KeyInfo | None:
        return self._key_list.get_cursor_key()