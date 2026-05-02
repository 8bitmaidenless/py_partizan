from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RadioButton, RadioSet, Static


@dataclass
class TrustResult:
    trust_value: str
    cancelled: bool = False

    @classmethod
    def from_cancel(cls) -> "TrustResult":
        return cls(trust_value="", cancelled=True)
    

_TRUST_OPTIONS: list[tuple[str, str]] = [
    ("Undefined  - trust not set", "TRUST_UNDEFINED"),
    ("Never      - do not trust this key", "TRUST_NEVER"),
    ("Marginal   - partially trust this key", "TRUST_MARGINAL"),
    ("Full       - fully trust this key", "TRUST_FULL"),
    ("Ultimate   - your own key / absolute trust", "TRUST_ULTIMATE"),
]


class TrustModal(ModalScreen[TrustResult]):

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    def __init__(self, key_label: str = "", current_trust: str = "") -> None:
        super().__init__()
        self._key_label = key_label
        self._current_trust = current_trust

    def compose(self) -> ComposeResult:
        with Container(id="tm-outer"):
            with Vertical(id="tm-inner"):
                yield Label(
                    f"Set Trust: [b]{self._key_label}[/b]",
                    id="tm-title",
                    markup=True
                )
                yield Static("-" * 42, id="tm-divider")
                yield Label(
                    "[b]Owner trust[/b] tells GPG [i]how much you trust this\n"
                    "key owner[/i] to correctly sign other keys.",
                    id="tm-description",
                    markup=True
                )
                yield Static("", id="tm-spacer")

                with RadioSet(id="tm-trust-set"):
                    for label, value in _TRUST_OPTIONS:
                        is_current = value.replace("TRUST_", "").lower() == self._current_trust
                        yield RadioButton(
                            label,
                            value=is_current,
                            id=f"tm-radio-{value.replace('TRUST_', '').lower()}"
                        )

                with Horizontal(id="tm-buttons"):
                    yield Button("Set Trust", variant="primary", id="tm-ok")
                    yield Button("Cancel", variant="default", id="tm-cancel")

    def on_mount(self) -> None:
        self.query_one("#tm-trust-set", RadioSet).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "tm-ok":
            self._submit()
        else:
            self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(TrustResult.from_cancel())

    def _submit(self) -> None:
        radio_set = self.query_one("#tm-trust-set", RadioSet)
        idx = radio_set.pressed_index
        if idx is None or idx < 0:
            self.notify(f"Select a trust level.", severity="warning")
            return
        _, trust_value = _TRUST_OPTIONS[idx]
        self.dismiss(TrustResult(trust_value=trust_value))