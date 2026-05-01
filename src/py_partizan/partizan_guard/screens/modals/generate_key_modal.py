from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static


@dataclass
class GenerateKeyResult:
    name: str
    email: str
    algorithm: str
    expire: str
    passphrase: str | None
    cancelled: bool = False

    @classmethod
    def from_cancel(cls) -> "GenerateKeyResult":
        return cls(
            name="",
            email="",
            algorithm="rsa",
            expire="2y",
            passphrase=None,
            cancelled=True
        )

    @property
    def was_empty_passphrase(self) -> bool:
        return not bool(self.passphrase)
    

class GenerateKeyModal(ModalScreen[GenerateKeyResult]):

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    _ALGO_OPTIONS = [
        ("RSA 4096", "rsa"),
        ("ECC (Ed25519/Cv25519)", "ecc"),
    ]
    _EXPIRE_OPTIONS = [
        ("Never", "0"),
        ("1 year", "1y"),
        ("2 years", "2y"),
        ("5 years", "5y"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="gkm-outer"):
            with Vertical(id="gkm-inner"):
                yield Label("Generate New Key", id="gkm-title")
                yield Static("-" * 38, id="gkm-divider")

                yield Label("Name", classes="gkm-label")
                yield Input(
                    placeholder="Alice Example",
                    id="gkm-name"
                )

                yield Label("Email", classes="gkm-label")
                yield Input(
                    placeholder="alice@example.com",
                    id="gkm-email"
                )

                yield Label("Algorithm", classes="gkm-label")
                yield Select(
                    self._ALGO_OPTIONS,
                    value="rsa",
                    id="gkm-algo",
                    allow_blank=False
                )

                yield Label("Expiry", classes="gkm-label")
                yield Select(
                    self._EXPIRE_OPTIONS,
                    value="2y",
                    id="gkm-expire",
                    allow_blank=False
                )

                yield Label("Passphrase (optional)", classes="gkm-label")
                yield Input(
                    placeholder="leave blank for *no* passphrase",
                    password=True,
                    id="gkm-passphrase"
                )

                yield Static(
                    " Empty passphrase = unprotected secret key.",
                    id="gkm-hint"
                )

                with Horizontal(id="gkm-buttons"):
                    yield Button("Generate", variant="primary", id="gkm-ok")
                    yield Button("Cancel", variant="default", id="gkm-cancel")

    def on_mount(self) -> None:
        self.query_one("#gkm-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "gkm-ok":
            self._submit()
        else:
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "gkm-passphrase":
            self._submit()
        
    def action_cancel(self) -> None:
        self.dismiss(GenerateKeyResult.from_cancel())

    def _submit(self) -> None:
        name = self.query_one("#gkm-name", Input).value.strip()
        email = self.query_one("#gkm-email", Input).value.strip()
        algo = self.query_one("#gkm-algo", Select).value
        expire = self.query_one("#gkm-expire", Select).value
        passphrase = self.query_one("#gkm-passphrase", Input).value

        if not name:
            self.query_one("#gkm-name", Input).focus()
            self.notify("Name is required.", severity="warning")
            return
        if not email or "@" not in email:
            self.query_one("#gkm-email", Input).focus()
            self.notify(
                "A valid email address is required.",
                severity="warning"
            )
            return
        
        self.dismiss(GenerateKeyResult(
            name=name,
            email=email,
            algorithm=str(algo),
            expire=str(expire),
            passphrase=passphrase or None
        ))