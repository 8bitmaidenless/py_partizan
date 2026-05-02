"""
screens/encrypt_decrypt.py
--------------------------
EncryptDecryptScreen - the cryptographic operations interface.

Layout
------
    ┌─────────────────────────────────────────────────────┐
    │  Header                                             │
    ├─────────────────────────────┬───────────────────────┤
    │  #ed-left (Vertical, 60%)   │  #ed-right (40%)      │
    │                             │                       │
    │  Mode selector (RadioSet)   │  KeyListWidget        │
    │  ─────────────────────────  │  (recipient /         │
    │  Input toggle (text/file)   │   signer picker)      │
    │  TextArea  OR  Input path   │                       │
    │  ─────────────────────────  │                       │
    │  Options bar (sign toggle,  │                       │
    │  armor toggle)              │                       │
    │  [Run] button               │                       │
    │  ─────────────────────────  │                       │
    │  Output TextArea (r/o)      │                       │
    ├─────────────────────────────┴───────────────────────┤
    │  OperationLogWidget (full width, fixed height)      │
    ├─────────────────────────────────────────────────────┤
    │  Footer                                             │
    └─────────────────────────────────────────────────────┘

Operations
----------
    1   Encrypt to recipients   -> encrypt_to_recipients()
    2   Symmetric encrypt       -> encrypt_symmetric()  + PassphraseModal
    3   Decrypt                 -> decrypt_data()       (auto-detect asym/sym)
    4   Clearsign               -> clearsign()
    5   Verify clearsign        -> verify_clearsign()   
    6   Detached sign           -> sign_detached()
    7   Verify detached         -> verify_detached()    (sig pasted separately)
    
Input modes
-----------
    Text  - paste / type directly into a TextArea
    File  - enter a file path; content is read before the GPG call
    
Key bindings
------------
    1-7     Select operation mode
    Enter   Run the current operation (when not in a TextArea)
    X       Run (explicit, works from anywhere)
    C       Copy output to clipboard
    S       Save log
    Tab     Cycle focus: input -> key list -> output
    Q       Back to home
    
Threading
---------
    All GPG calls run in thread workers via asyncio.to_thread().
    Output is written back to the main thread via call_from_thread().
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
    TextArea
)

from py_partizan.cipherlib import (
    clearsign,
    decrypt_data,
    encrypt_symmetric,
    encrypt_to_recipients,
    sign_detached,
    verify_clearsign,
    verify_detached
)
from py_partizan.partizan_guard.widgets.key_list import KeyInfo, KeyListWidget
from py_partizan.partizan_guard.widgets.operation_log import OperationLogWidget
from py_partizan.partizan_guard.widgets.passphrase_modal import PassphraseModal, PassphraseResult


_MODES: list[tuple[str, str, bool, bool]] = [
    ("1. Encrypt → recipients", "1", True, False),
    ("2. Symmetric encrypt", "2", False, False),
    ("3. Decrypt", "3", False, False),
    ("4. Clearsign", "4", False, False),
    ("5. Verify clearsign", "5", False, False),
    ("6. Detached sign", "6", False, False),
    ("7. Verify detached", "7", False, False),
]

_MODE_LABELS = [m[0] for m in _MODES]
_MODE_KEYS = [m[1] for m in _MODES]
_MODE_NEEDS_RECIPIENTS = [m[2] for m in _MODES]
_MODE_NEEDS_SIG = [m[3] for m in _MODES]


_CSS_DIR = Path(__file__).parent.parent / "css"


class EncryptDecryptScreen(Screen):
    """
    Cryptographic operations interface.
    
    Receives the shared GPG instance from GPGApp via the constructor.
    Never constructs its own GPG instance.
    """

    TITLE = "Encrypt / Decrypt"

    CSS_PATH = [
        str(_CSS_DIR / "key_list.tcss"),
        str(_CSS_DIR / "encrypt_decrypt.tcss"),
    ]

    BINDINGS = [
        Binding("1", "set_mode('0')", "Encrypt→recip.", show=False),
        Binding("2", "set_mode('1')", "Sym. encrypt", show=False),
        Binding("3", "set_mode('2')", "Decrypt", show=False),
        Binding("4", "set_mode('3')", "Clearsign", show=False),
        Binding("5", "set_mode('4')", "Verify clr.", show=False),
        Binding("6", "set_mode('5')", "Det. sign", show=False),
        Binding("7", "set_mode('6')", "Verify det.", show=False),
        Binding("x", "run_operation", "Run", show=True),
        Binding("c", "copy_output", "Copy output", show=True),
        Binding("s", "save_log", "Save log", show=True),
        Binding("tab", "cycle_focus", "Switch pane", show=True),
        Binding("q", "go_home", "Home", show=True),
    ]

    def __init__(self, gpg, **kwargs) -> None:
        super().__init__(**kwargs)
        self.gpg = gpg
        self._mode_idx = 0
        self._input_mode = "text"

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="ed-main"):
            with Vertical(id="ed-left"):
                yield Label("Operation", classes="ed-section-label")
                with RadioSet(id="ed-mode-set"):
                    for label in _MODE_LABELS:
                        yield RadioButton(label)

                yield Label("Input", classes="ed-section-label")
                with Horizontal(id="ed-input-toggle"):
                    yield Button("Text", id="ed-btn-text", variant="primary")
                    yield Button("File path", id="ed-btn-file", variant="default")

                yield TextArea(
                    "",
                    id="ed-input-text",
                    show_line_numbers=False
                )

                yield Input(
                    placeholder="Absolute or relative file path...",
                    id="ed-input-file"
                )

                yield Label(
                    "Detached signature [i](paste [b].asc[/b] content)[/i]:",
                    id="ed-sig-label",
                    classes="ed-section-label",
                    markup=True
                )
                yield TextArea(
                    "",
                    id="ed-sig-text",
                    show_line_numbers=False
                )

                with Horizontal(id="ed-options"):
                    yield Checkbox("Sign while encrypting", id="ed-opt-sign")
                    yield Checkbox("ASCII armor output", id="ed-opt-armor", value=True)

                yield Static(
                    "  Signing key: select in the key list →",
                    id="ed-sign-hint"
                )

                yield Button("▶  Run", variant="primary", id="ed-run-btn")

                yield Label("Output", classes="ed-section-label")
                yield TextArea(
                    "",
                    id="ed-output",
                    show_line_numbers=False
                )

            with Vertical(id="ed-right"):
                yield Label(
                    "[u]Keys[/u]  [i]([b]Space[/b] = select recipient / signer)[/i]",
                    classes="ed-section-label",
                    markup=True
                )
                yield KeyListWidget(gpg=self.gpg, id="ed-key-list")
                yield Static("", id="ed-selection-status", markup=True)

        yield OperationLogWidget(id="ed-op-log")
        yield Footer()

    def on_mount(self) -> None:
        self._log.clear()
        self._log.log_separator("Encrypt / Decrypt")
        self._log.log(f"Keyring: {self.gpg.gnupghome}", level="INFO")
        self._apply_mode(0)
        self._apply_input_mode("text")

        self._output.read_only = True
        self.query_one("#ed-mode-set", RadioSet).focus()

    def on_screem_resume(self) -> None:
        self._log.clear()
        self._log.log_separator("Encrypt / Decrypt")
        self._key_list.refresh_keys(self.gpg)
        self._apply_mode(self._mode_idx)

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Mode radio changed - update UI."""
        self._apply_mode(event.radio_set.pressed_index)

    def action_set_mode(self, idx_str: str) -> None:
        """Keyboard shortcuts 1-7 select a mode."""
        idx = int(idx_str)
        radio_set = self.query_one("#ed-mode-set", RadioSet)

        try:
            buttons = list(radio_set.query(RadioButton))
            if 0 <= idx < len(buttons):
                buttons[idx].value = True
        except Exception:
            pass
        self._apply_mode(idx)

    def _apply_mode(self, idx: int) -> None:
        """Show/hide UI sections based on the selected operation mode."""
        self._mode_idx = idx

        needs_recip = _MODE_NEEDS_RECIPIENTS[idx]
        needs_sig = _MODE_NEEDS_SIG[idx]

        sign_cb = self.query_one("#ed-opt-sign", Checkbox)
        sign_cb.display = (idx == 0)

        sign_hint = self.query_one("#ed-sign-hint", Static)
        sign_hint.display = (idx == 0 and sign_cb.value)

        sig_label = self.query_one("#ed-sig-label", Label)
        sig_text = self.query_one("#ed-sig-text", TextArea)
        sig_label.display = needs_sig
        sig_text.display = needs_sig

        key_label = self.query_one("#ed-right .ed-section-label", Label)
        if needs_recip:
            key_label.update(
                "[u]Recipients[/u]  [i]([b]Space[/b] = select, [b]Esc[/b] = clear)[/i]"
            )
        elif idx in (3, 5):
            key_label.update(
                "[u]Signing key[/u]  [i]([b]Space[/b] = select ONE key)[/i]"
            )
        else:
            key_label.update(
                "[u]Keys[/u]  [i](reference only)[/i]"
            )
        
        self._output.clear()
        self._log.log(f"Mode -> {_MODE_LABELS[idx]}", level="INFO")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "ed-btn-text":
            self._apply_input_mode("text")
        elif bid == "ed-btn-file":
            self._apply_input_mode("file")
        elif bid == "ed-run-btn":
            self.action_run_operation()

    def _apply_input_mode(self, mode: str) -> None:
        self._input_mode = mode
        text_area = self.query_one("#ed-input-text", TextArea)
        file_input = self.query_one("#ed-input-file", Input)
        btn_text = self.query_one("#ed-btn-text", Button)
        btn_file = self.query_one("#ed-btn-file", Button)

        text_area.display = (mode == "text")
        file_input.display = (mode == "file")

        btn_text.variant = "primary" if mode == "text" else "default"
        btn_file.variant = "primary" if mode == "file" else "default"

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "ed-opt-sign":
            hint = self.query_one("#ed-sign-hint", Static)
            hint.display = bool(event.value) and self._mode_idx == 0

    def on_key_list_widget_selection_changed(
        self,
        event: KeyListWidget.SelectionChanged
    ) -> None:
        n = len(event.fingerprints)
        status = self.query_one("#ed-selection-status", Static)
        if n == 0:
            status.update("")
        elif self._mode_idx in (3, 5):
            status.update(
                f"  ✦ {n} signing key selected"
                if n == 1
                else f"  ⚠ Select exactly ONE signing key [i]({n} selected)[/i]"
            )
        else:
            status.update(f"  ✦ {n} recipient(s) selected")

    def action_run_operation(self) -> None:
        """Dispatch the correct operation based on current mode."""
        dispatch = {
            0: self._run_encrypt_recipients,
            1: self._run_encrypt_symmetric,
            2: self._run_decrypt,
            3: self._run_clearsign,
            4: self._run_verify_clearsign,
            5: self._run_sign_detached,
            6: self._run_verify_detached,
        }
        fn = dispatch.get(self._mode_idx)
        if fn:
            fn()

    def _get_input_bytes(self) -> bytes | None:
        """
        Read the current input as bytes - either from the TextArea or by
        reading the file at the given path.
        Returns None and logs an error if the input is empty or file is missing.
        """
        if self._input_mode == "text":
            text = self.query_one("#ed-input-text", TextArea).text.strip()
            if not text:
                self._log.log("Input is empty.", level="WARN")
                return None
            return text.encode("utf-8")
        else:
            path_str = self.query_one("#ed-input-file", Input).value.strip()

            if not path_str:
                # self._log.log(f"File not found: {path}")
                self._log.log("No file path entered.", level="WARN")
                return None
            path = Path(path_str)
            if not path.exists():
                self._log.log(f"File not found: {path}", level="ERR")
                return None
            try:
                return path.read_bytes()
            except OSError as exc:
                self._log.log(f"Cannot read file: {exc}", level="ERR")
                return None
            
    def _get_input_str(self) -> str | None:
        """
        Like `_get_input_bytes` but returns a decoded string.
        """
        raw = self._get_input_bytes()
        if raw is None:
            return None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            self._log.log(
                "Input is not a valid UTF-8 text.",
                level="ERR"
            )
            return None
        
    def _get_selected_fingerprints(self) -> list[str]:
        return list(self._key_list.get_selected())
    
    def _get_single_signing_key(self) -> str | None:
        fps = self._get_selected_fingerprints()
        if len(fps) != 1:
            self._log.log(
                f"Select exactly ONE signing key ({len(fps)} selected).",
                level="WARN"
            )
            return None
        return fps[0]
    
    def _armor_requested(self) -> bool:
        return bool(self.query_one("#ed-opt-armor", Checkbox).value)
    
    def _write_output(self, data: str | bytes | None) -> None:
        """Put data in to the read-only output TextArea."""
        out = self._output
        out.clear()
        if data is None:
            return
        if isinstance(data, bytes):
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = f"<binary output - {len(data)} bytes>\n" \
                "(Use file-path mode and check output file)"
            
        else:
            text = data
        out.load_text(text)

    def _run_encrypt_recipients(self) -> None:
        plaintext = self._get_input_bytes()
        if plaintext is None:
            return
        recipients = self._get_selected_fingerprints()
        if not recipients:
            self._log.log(
                "Select at least one recipient in the key list (Spce).",
                level="WARN"
            )
            return
        armor = self._armor_requested()
        sign_fp = None
        if self.query_one("#ed-opt-sign", Checkbox).value:
            sign_fp = self._get_single_signing_key()
            if sign_fp is None:
                return
            
        self._log.log_separator(f"Encrypt -> {len(recipients)} recipient(s)")
        self.run_worker(
            self._worker_encrypt_recipients(
                plaintext,
                recipients,
                armor,
                sign_fp
            ),
            thread=True,
            name="encrypt_recipients"
        )

    async def _worker_encrypt_recipients(
        self,
        plaintext: bytes,
        recipients: list[str],
        armor: bool,
        sign_fp: str | None
    ) -> None:
        result = await asyncio.to_thread(
            encrypt_to_recipients,
            self.gpg,
            plaintext,
            recipients,
            armor=armor,
            sign=sign_fp,
            always_trust=True
        )
        self.app.call_from_thread(
            self._finish_encrypt_recipients,
            result,
            armor
        )

    def _finish_encrypt_recipients(
        self,
        result: str | bytes | None,
        armor: bool
    ) -> None:
        ok = result is not None
        self._log.log_result(
            ok=ok,
            label="encrypt_to_recipients",
            detail=f"{len(result)} chars" if ok and isinstance(result, str) \
                else f"{len(result)} bytes" if ok else None
        )
        self._write_output(result)

    def _run_encrypt_symmetric(self) -> None:
        plaintext = self._get_input_bytes()
        if plaintext is None:
            return
        
        self.app.push_screen(
            PassphraseModal(title="Passphrase for symmetric encryption."),
            callback=self._on_sym_passphrase
        )
        self._pending_sym_plaintext = plaintext

    def _on_sym_passphrase(self, result: PassphraseResult) -> None:
        if result.cancelled:
            self._log.log("Symmetric encrypt cancelled.", level="INFO")
            return
        if result.was_empty:
            self._log.log(
                "Empty passphrase - symmetric encryption will use blank key.",
                level="WARN"
            )
        plaintext = getattr(self, "_pending_sym_plaintext", b"")
        armor = self._armor_requested()
        self._log.log_separator("Symmetric Encrypt")
        self.run_worker(
            self._worker_encrypt_symmetric(
                plaintext,
                result.passphrase or "",
                armor
            ),
            thread=True,
            name="encrypt_symmetric"
        )

    async def _worker_encrypt_symmetric(
        self,
        plaintext: bytes,
        passphrase: str,
        armor: bool
    ) -> None:
        result = await asyncio.to_thread(
            encrypt_symmetric,
            self.gpg,
            plaintext,
            passphrase,
            armor=armor
        )
        self.app.call_from_thread(self._finish_encrypt_symmetric, result)

    def _finish_encrypt_symmetric(self, result: str | bytes | None) -> None:
        ok = result is not None
        self._log.log_result(ok=ok, label="encrypt_symmetric")
        self._write_output(result)

    def _run_decrypt(self) -> None:
        ciphertext = self._get_input_bytes()
        if ciphertext is None:
            return
        
        self.app.push_screen(
            PassphraseModal(
                title="Passphrase (leave blank for asymmetric decrypt)"
            ),
            callback=self._on_decrypt_passphrase
        )
        self._pending_ciphertext = ciphertext

    def _on_decrypt_passphrase(self, result: PassphraseResult) -> None:
        if result.cancelled:
            self._log.log("Decrypt cancelled.", level="INFO")
            return
        ciphertext = getattr(self, "_pending_ciphertext", b"")
        passphrase = result.passphrase if not result.was_empty else None
        self._log.log_separator("Decrypt")
        self.run_worker(
            self._worker_decrypt(ciphertext, passphrase),
            thread=True,
            name="decrypt"
        )

    async def _worker_decrypt(
        self,
        ciphertext: bytes,
        passphrase: str | None
    ) -> None:
        result = await asyncio.to_thread(
            decrypt_data,
            self.gpg,
            ciphertext,
            passphrase=passphrase,
            always_trust=True
        )
        self.app.call_from_thread(self._finish_decrypt, result)

    def _finish_decrypt(self, result: bytes | None) -> None:
        ok = result is not None
        self._log.log_result(
            ok=ok,
            label="decrypt_data",
            detail=f"{len(result)} bytes plaintext" if ok else None
        )
        self._write_output(result)

    def _run_clearsign(self) -> None:
        message = self._get_input_str()
        if message is None:
            return
        sign_fp = self._get_single_signing_key()
        if sign_fp is None:
            return
        self._log.log_separator("Clearsign")
        self.run_worker(
            self._worker_clearsign(message, sign_fp),
            thread=True,
            name="clearsign"
        )

    async def _worker_clearsign(self, message: str, sign_fp: str) -> None:
        result = await asyncio.to_thread(
            clearsign,
            self.gpg,
            message,
            sign_fp
        )
        self.app.call_from_thread(self._finish_clearsign, result)

    def _finish_clearsign(self, result: str | None) -> None:
        ok = result is not None
        self._log.log_result(ok=ok, label="clearsign")
        self._write_output(result)

    def _run_verify_clearsign(self) -> None:
        signed_msg = self._get_input_str()
        if signed_msg is None:
            return
        self._log.log_separator("Verify clearsign")
        self.run_worker(
            self._worker_verify_clearsign(signed_msg),
            thread=True,
            name="verify_clearsign"
        )

    async def _worker_verify_clearsign(self, signed_msg: str) -> None:
        from py_partizan.cipherlib import verify_clearsign as _verify_cs
        vr = await asyncio.to_thread(_verify_cs, self.gpg, signed_msg)
        self.app.call_from_thread(self._finish_verify_clearsign, vr)
        
    def _finish_verify_clearsign(self, vr) -> None:
        self._log.log_result(
            ok=vr.valid,
            label="verify_clearsign",
            detail=str(vr) if vr.valid else f"status: {vr.status}"
        )
        self._write_output(str(vr))

    def _run_sign_detached(self) -> None:
        message = self._get_input_bytes()
        if message is None:
            return
        sign_fp = self._get_single_signing_key()
        if sign_fp is None:
            return
        self._log.log_separator("Detached Sign")
        self.run_worker(
            self._worker_sign_detached(message, sign_fp),
            thread=True,
            name="sign_detached"
        )
    
    async def _worker_sign_detached(
        self,
        message: bytes,
        sign_fp: str
    ) -> None:
        result = await asyncio.to_thread(
            sign_detached,
            self.gpg,
            message,
            sign_fp,
            armor=True
        )
        self.app.call_from_thread(self._finish_sign_detached, result)

    def _finish_sign_detached(self, result: str | bytes | None) -> None:
        ok = result is not None
        self._log.log_result(ok=ok, label="sign_detached")
        self._write_output(result)

    def _run_verify_detached(self) -> None:
        message = self._get_input_bytes()
        if message is None:
            return
        sig_text = self.query_one("#ed-sig-label", TextArea).text.strip()
        if not sig_text:
            self._log.log(
                "Paste the detached signature (.asc) in the signature field.",
                level="WARN"
            )
            return
        self._log.log_separator("Verify Detached")
        self.run_worker(
            self._worker_verify_detached(message, sig_text),
            thread=True,
            name="verify_detached"
        )

    async def _worker_verify_detached(
        self,
        message: bytes,
        signature: str
    ) -> None:
        vr = await asyncio.to_thread(
            verify_detached,
            self.gpg,
            message,
            signature
        )
        self.app.call_from_thread(self._finish_verify_detached, vr)

    def _finish_verify_detached(self, vr) -> None:
        self._log.log_result(
            ok=vr.valid,
            label="verify_detached",
            detail=str(vr) if vr.valid else f"status: {vr.status}"
        )
        self._write_output(str(vr))

    def action_copy_output(self) -> None:
        """Copy the output TextArea content to the clipboard."""
        text = self._output.text.strip()
        if not text:
            self._log.log("Output is empty - nothing to copy.", level="WARN")
            return
        try:
            import pyperclip
            pyperclip.copy(text)
            self._log.log("Output copied to clipboard.", level="OK")
        except ImportError:
            self._log.log(
                "pyperclip not installed. `pip install pyperclip` to enable.",
                level="WARN"
            )
        except Exception as exc:
            self._log.log(f"Clipboard error: {exc}", level="ERR")

    def action_save_log(self) -> None:
        self._log.save()

    def action_cycle_focus(self) -> None:
        """Tab - cycle: input area -> key list -> output area -> back."""
        focused = self.focused
        fid = getattr(focused, "id", None)
        if fid in ("ed-input-text", "ed-input-file"):
            self._key_list.focus()
        elif fid == "ed-key-list":
            self._output.focus()
        else:
            if self._input_mode == "text":
                self.query_one("#ed-input-text", TextArea).focus()
            else:
                self.query_one("#ed-input-file", Input).focus()
    
    def action_go_home(self) -> None:
        self.app.pop_screen()
        # installed = getattr(self.app, "_installed_screens", {})
        # if "home" in installed:
        #     self.app.switch_screen("home")
        # else:
        #     self.app.pop_screen()
        
    @property
    def _log(self) -> OperationLogWidget:
        return self.query_one("#ed-op-log", OperationLogWidget)
    
    @property
    def _key_list(self) -> KeyListWidget:
        return self.query_one("#ed-key-list", KeyListWidget)
    
    @property
    def _output(self) -> TextArea:
        return self.query_one("#ed-output", TextArea)


    