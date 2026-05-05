
"""
screens/modals/import_key_modal.py
-----------------------------------
ImportKeyModal — ModalScreen that collects either pasted ASCII-armor text
or a file path for gnupg_workflows.import_key_data() / import_key_file().

The user picks a mode (paste / file) via a toggle, then fills in the
relevant field. Only one field is active at a time.

Result
------
    ImportKeyResult dataclass returned via self.dismiss().
    mode      : "armor" | "file"
    armor_text: str  (mode=armor)
    file_path : str  (mode=file)
    cancelled : bool
"""

from __future__ import annotations

from dataclasses import dataclass, field

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static, TextArea


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ImportKeyResult:
    mode:       str        # "armor" | "file"
    armor_text: str = ""
    file_path:  str = ""
    cancelled:  bool = False

    @classmethod
    def from_cancel(cls) -> "ImportKeyResult":
        return cls(mode="armor", cancelled=True)


# ---------------------------------------------------------------------------
# Modal
# ---------------------------------------------------------------------------

class ImportKeyModal(ModalScreen[ImportKeyResult]):
    """Collect import source — pasted armor or file path."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    def compose(self) -> ComposeResult:
        with Container(id="ikm-outer"):
            with Vertical(id="ikm-inner"):
                yield Label("Import Key", id="ikm-title")
                yield Static("─" * 38, id="ikm-divider")

                # Mode selector
                yield Label("Import from", classes="ikm-label")
                with RadioSet(id="ikm-mode"):
                    yield RadioButton("Paste ASCII armor", value=True,
                                      id="ikm-radio-armor")
                    yield RadioButton("File path", id="ikm-radio-file")

                # Armor pane
                with Container(id="ikm-armor-pane"):
                    yield Label("Paste public key block below:",
                                classes="ikm-label")
                    yield TextArea(
                        "",
                        id="ikm-armor-text",
                        language=None,
                        show_line_numbers=False,
                    )

                # File pane (hidden until file mode selected)
                with Container(id="ikm-file-pane"):
                    yield Label("File path (.asc / .gpg / .txt):",
                                classes="ikm-label")
                    yield Input(
                        placeholder="/home/user/keys/alice_pub.asc",
                        id="ikm-file-path",
                    )

                yield Static("", id="ikm-validation-msg")

                with Horizontal(id="ikm-buttons"):
                    yield Button("Import", variant="primary", id="ikm-ok")
                    yield Button("Cancel", variant="default", id="ikm-cancel")

    def on_mount(self) -> None:
        # Start in armor mode — hide the file pane
        self._set_mode("armor")
        self.query_one("#ikm-armor-text", TextArea).focus()

    # ------------------------------------------------------------------
    # Mode toggle
    # ------------------------------------------------------------------

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        mode = "armor" if event.radio_set.pressed_index == 0 else "file"
        self._set_mode(mode)

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        armor_pane = self.query_one("#ikm-armor-pane", Container)
        file_pane  = self.query_one("#ikm-file-pane",  Container)
        if mode == "armor":
            armor_pane.display = True
            file_pane.display  = False
            self.query_one("#ikm-armor-text", TextArea).focus()
        else:
            armor_pane.display = False
            file_pane.display  = True
            self.query_one("#ikm-file-path", Input).focus()

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ikm-ok":
            self._submit()
        else:
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "ikm-file-path":
            self._submit()

    def action_cancel(self) -> None:
        self.dismiss(ImportKeyResult.from_cancel())

    # ------------------------------------------------------------------
    # Validation + submit
    # ------------------------------------------------------------------

    def _submit(self) -> None:
        mode = getattr(self, "_mode", "armor")
        msg  = self.query_one("#ikm-validation-msg", Static)

        if mode == "armor":
            text = self.query_one("#ikm-armor-text", TextArea).text.strip()
            if not text or "BEGIN PGP" not in text:
                msg.update("  ⚠ Paste a valid PGP public key block.")
                return
            self.dismiss(ImportKeyResult(mode="armor", armor_text=text))

        else:
            path = self.query_one("#ikm-file-path", Input).value.strip()
            if not path:
                msg.update("  ⚠ Enter a file path.")
                return
            self.dismiss(ImportKeyResult(mode="file", file_path=path))



# """
# screens/modals/import_key_modal.py
# ----------------------------------

# """
# from __future__ import annotations

# from dataclasses import dataclass, field

# from textual.app import ComposeResult
# from textual.binding import Binding
# from textual.containers import Container, Vertical, Horizontal
# from textual.screen import ModalScreen
# from textual.widgets import (
#     Button,
#     Input,
#     Label,
#     RadioButton,
#     RadioSet,
#     Static,
#     TextArea
# )


# @dataclass
# class ImportKeyResult:
#     mode: str
#     armor_text: str = ""
#     file_path: str = ""
#     cancelled: bool = False

#     @classmethod
#     def from_cancel(cls) -> "ImportKeyResult":
#         return cls(mode="armor", cancelled=False)
    

# class ImportKeyResult(ModalScreen[ImportKeyResult]):

#     BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

#     def compose(self) -> ComposeResult:
#         with Container(id="ikm-outer"):
#             with Vertical(id="ikm-inner"):
#                 yield Label("Import Key", id="ikm-title")
#                 yield Static("-" * 38, id="ikm-divider")

#                 yield Label("Import from", classes="ikm-label")
#                 with RadioSet(id="ikm-mode"):
#                     yield RadioButton(
#                         "Paste ASCII armor",
#                         value=True,
#                         id="ikm-radio-armor"
#                     )
#                     yield RadioButton(
#                         "File path",
#                         id="ikm-radio-file"
#                     )
#                 with Container(id="ikm-armor-pane"):
#                     yield Label("Paste [b]public key[/b] block below:", markup=True, classes="ikm-label")
#                     yield TextArea(
#                         "",
#                         id="ikm-armor-text",
#                         language=None,
#                         show_line_numbers=False
#                     )

#                 with Container(id="ikm-file-pane"):
#                     yield Label(
#                         "File path [i](.asc / .gpg / .txt)[/i]:",
#                         markup=True,
#                         classes="ikm-label"
#                     )
#                     yield Input(
#                         placeholder="/Users/alice/.gnupg/publickeys/alice_pub.asc",
#                         id="ikm-file-path"
#                     )

#                 yield Static("", id="ikm-validation-msg")

#                 with Horizontal(id="ikm-buttons"):
#                     yield Button("Import", variant="primary", id="ikm-ok")
#                     yield Button("Cancel", variant="default", id="ikm-cancel")

#     def on_mount(self) -> None:
#         self._set_mode("armor")
#         self.query_one("#ikm-armor-text", TextArea).focus()

#     def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
#         mode = "armor" if event.radio_set.pressed_index == 0 else "file"
#         self._set_mode(mode)

#     def _set_mode(self, mode: str) -> None:
#         self._mode = mode
#         armor_pane = self.query_one("#ikm-armor-pane", Container)
#         file_pane = self.query_one("#ikm-file-pane", Container)
#         if mode == "armor":
#             armor_pane.display = True
#             file_pane.display = False
#             self.query_one("#ikm-armor-text", TextArea).focus()
#         else:
#             armor_pane.display = False
#             file_pane.display = True
#             self.query_one("#ikm-file-path", Input).focus()

#     def on_button_pressed(self, event: Button.Pressed) -> None:
#         if event.button.id == "ikm-ok":
#             self._submit()
#         else:
#             self.action_cancel()

#     def on_input_submitted(self, event: Input.Submitted) -> None:
#         if event.input.id == "ikm-file-path":
#             self._submit()
        
#     def action_cancel(self) -> None:
#         self.dismiss(ImportKeyResult.from_cancel())

#     def _submit(self) -> None:
#         mode = getattr(self, "_mode", "armor")
#         msg = self.query_one("#ikm-validation-msg", Static)

#         if mode == "armor":
#             text = self.query_one("#ikm-armor-text", TextArea).text.strip()
#             if not text or "BEGIN PGP" not in text:
#                 msg.update("  ⚠ Paste a valid PGP public key block.")
#                 return
#             self.dismiss(ImportKeyResult(mode="armor", armor_text=text))
        
#         else:
#             path = self.query_one("#ikm-file-path", Input).value.strip()
#             if not path:
#                 msg.update("  ⚠ Enter a file path.")
#                 return
#             self.dismiss(ImportKeyResult(mode="file", file_path=path))


# # from __future__ import annotations

# # from dataclasses import dataclass, field

# # from textual.app import ComposeResult
# # from textual.binding import Binding
# # from textual.containers import Container, Vertical, Horizontal
# # from textual.screen import ModalScreen
# # from textual.widgets import (
# #     Button,
# #     Input,
# #     Label,
# #     RadioButton,
# #     RadioSet,
# #     Static,
# #     TextArea
# # )


# # @dataclass
# # class ImportKeyResult:
# #     mode: str
# #     armor_text: str = ""
# #     file_path: str = ""
# #     cancelled: bool = False

# #     @classmethod
# #     def from_cancel(cls) -> "ImportKeyResult":
# #         return cls(mode="armor", cancelled=True)
    

# # class ImportKeyModal(ModalScreen[ImportKeyResult]):

# #     BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

# #     def compose(self) -> ComposeResult:
# #         with Container(id="ikm-outer"):
# #             with Vertical(id="ikm-inner"):
# #                 yield Label("Import Key", id="ikm-title")
# #                 yield Static("-" * 38, id="ikm-divider")

# #                 yield Label("Import from", classes="ikm-label")
# #                 with RadioSet(id="ikm-mode"):
# #                     yield RadioButton(
# #                         "Paste ASCII Armor",
# #                         value=True,
# #                         id="ikm-radio-armor"
# #                     )
# #                     yield RadioButton(
# #                         "File path",
# #                         id="ikm-radio-file"
# #                     )

# #                 with Container(id="ikm-armor-pane"):
# #                     yield Label(
# #                         "Paste [b]public key block[/b] below:",
# #                         classes="ikm-label",
# #                         markup=True
# #                     )
# #                     yield TextArea(
# #                         "",
# #                         id="ikm-armor-text",
# #                         language=None
# #                     )

# #                 with Container(id="ikm-file-pane"):
# #                     yield Label("File path [i]([b].asc[/b], [b].gpg[/b], [b].txt[/b])[/i]:", markup=True, classes="ikm-label")
# #                     yield Input(
# #                         placeholder="/home/user/keys/alice_pub.asc",
# #                         id="ikm-file-path"
# #                     )

# #                 yield Static("", id="ikm-validation-msg")

# #                 with Horizontal(id="ikm-buttons"):
# #                     yield Button("Import", variant="primary", id="ikm-ok")
# #                     yield Button("Cancel", variant="default", id="ikm-cancel")

# #     def on_mount(self) -> None:
# #         self._set_mode("armor")
# #         self.query_one("#ikm-armor-text", TextArea).focus()

# #     def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
# #         mode = "armor" if event.radio_set.pressed_index == 0 else "file"
# #         self._set_mode(mode)

# #     def _set_mode(self, mode: str) -> None:
# #         self._mode = mode
# #         armor_pane = self.query_one("#ikm-armor-pane", Container)
# #         file_pane = self.query_one("#ikm-file-pane", Container)
# #         if mode == "armor":
# #             armor_pane.display = True
# #             file_pane.display = False
# #             self.query_one("#ikm-armor-text", TextArea).focus()
# #         else:
# #             armor_pane.display = False
# #             file_pane.display = True
# #             self.query_one("#ikm-file-path", Input).focus()
    
# #     def on_button_pressed(self, event: Button.Pressed) -> None:
# #         if event.button.id == "ikm-ok":
# #             self._submit()
# #         else:
# #             self.action_cancel()

# #     def on_input_submitted(self, event: Input.Submitted) -> None:
# #         if event.input.id == "ikm-file-path":
# #             self._submit()

# #     def action_cancel(self) -> None:
# #         self.dismiss(ImportKeyResult.from_cancel())

# #     def _submit(self) -> None:
# #         mode = getattr(self, "_mode", "armor")
# #         msg = self.query_one("#ikm-validation-msg", Static)

# #         if mode == "armor":
# #             text = self.query_one("#ikm-armor-text", TextArea).text.strip()
# #             if not text or "BEGIN PGP" not in text:
# #                 msg.update("  ⚠ Paste a valid PGP public key block.")
# #                 return
# #             self.dismiss(ImportKeyResult(mode="armor", armor_text=text))

# #         else:
# #             path = self.query_one("#ikm-file-path", Input).value.strip()
# #             if not path:
# #                 msg.update("  ⚠ Enter a file path.")
# #                 return
# #             self.dismiss(ImportKeyResult(mode="file", file_path=path))
            