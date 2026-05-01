from __future__ import annotations

from dataclasses import dataclass

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, Static


@dataclass
class PassphraseResult:
    passphrase: str | None
    cancelled: bool = False
    was_empty: bool = False

    @classmethod
    def from_submit(cls, value: str) -> "PassphraseResult":
        return cls(
            passphrase=value,
            cancelled=False,
            was_empty=(value == "")
        )
    
    @classmethod
    def from_cancel(cls) -> "PassphraseResult":
        return cls(passphrase=None, cancelled=True, was_empty=False)
    

class PassphraseModal(ModalScreen[PassphraseResult]):
    DEFAULT_CSS = ""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True)
    ]

    def __init__(self, title: str = "Enter Passphrase") -> None:
        super().__init__()
        self._modal_title = title

    def compose(self) -> ComposeResult:
        with Container(id="passphrase-modal-outer"):
            with Vertical(id="passphrase-modal-inner"):
                yield Label(self._modal_title, id="passphrase-modal-title")
                yield Static("-" * 36, id="passphrase-modal-divider")
                yield Label("Passphrase", id="passphrase-field-label")
                yield Input(
                    placeholder="(leave no blank for no passphrase)",
                    password=True,
                    id="passphrase-input"
                )
                with Container(id="passphrase-modal-buttons"):
                    yield Button("OK", variant="primary", id="btn-ok")
                    yield Button("Cancel", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#passphrase-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-ok":
            self._submit()
        elif event.button.id == "btn-cancel":
            self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(PassphraseResult.from_cancel())

    def _submit(self) -> None:
        value = self.query_one("#passphrase-input", Input).value
        self.dismiss(PassphraseResult.from_submit(value))


if __name__ == "__main__":
    from pathlib import Path

    class _DemoApp(App):

        TITLE = "PassphraseModal - demo"
        BINDINGS = [
            Binding("p", "open_modal", "Open modal"),
            Binding("q", "quit", "Quit"),
        ]
        # CSS_PATH = str(Path(__file__).parent.parent / "css" / "passphrase_modal.tcss")
        CSS_PATH = "/Users/glizzok/Desktop/py_partizan/src/py_partizan/partizan_guard/css/passphrase_modal.tcss"

        def compose(self) -> ComposeResult:
            yield Header()
            yield Label(
                "\n  Press [b]P[/b] to open the passphrase modal.\n",
                id="demo-status",
                markup=True
            )
            yield Footer()

        def action_open_modal(self) -> None:
            self.push_screen(
                PassphraseModal(title="Passphrase for: alice@example.com"),
                callback=self._on_passphrase_result
            )

        def _on_passphrase_result(self, result: PassphraseResult) -> None:
            label = self.query_one("#demo-status", Label)

            if result.cancelled:
                label.update("\n  Result: CANCELLED (Escape or Cancel presssed)\n")

                return
            
            if result.was_empty:
                status = "SUBMITTED - passphrase was EMPTY (WARN: key will be unprotected)"
            else:
                status = f"SUBMITTED - passphrase received ({len(result.passphrase)} chars)"

            label.update(f"\n  Result: {status}\n")

    _DemoApp().run()