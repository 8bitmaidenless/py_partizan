import argparse
import sys
import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Label
from textual.screen import Screen

try:
    from py_partizan.cipherlib import build_gpg
except ImportError as exc:
    print(
        f"[FATAL] Cannot import py_partizan.cipherlib: {exc}\n"
        "Ensure the cipherlib/ package is in the right directory."
    )
    sys.exit(1)


def _import_key_management_screen():
    from py_partizan.partizan_guard.screens.key_management import KeyManagementScreen
    return KeyManagementScreen


def _import_encrypt_decrypt_screen():
    from py_partizan.partizan_guard.screens.encrypt_decrypt import EncryptDecryptScreen
    return EncryptDecryptScreen


class PlaceholderScreen(Screen):

    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]

    def __init__(self, title: str = "Coming soon"):
        super().__init__()
        self._title = title
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(
            f"\n  [ {self._title} ]\n\n This screen is not yet implemented.\n Press Q or Escape to go back.",
            id="placeholder-label"
        )
        yield Footer()


class GPGApp(App):
    TITLE = "Partizan GNUPG"
    SUB_TITLE = "GnuPG key management and cryptographic toolkit."

    CSS_PATH = os.path.join(".", "css", "app.tcss")

    BINDINGS = [
        Binding("k", "switch_screen('keys')", "Keys", priority=True),
        Binding("e", "switch_screen('encrypt')", "Encrypt", priority=True),
        Binding("q", "quit", "Quit", priority=True),
    ]

    def __init__(self, gpg_instance, **kwargs):
        super().__init__(**kwargs)
        self.gpg = gpg_instance

    def on_mount(self) -> None:
        self.install_screen(self._make_key_screen, name="keys")
        self.install_screen(self._make_encrypt_screen, name="encrypt")

    def _make_key_screen(self):
        try:
            KeyManagementScreen = _import_key_management_screen()
            return KeyManagementScreen(self.gpg)
        except (ImportError, ModuleNotFoundError):
            return PlaceholderScreen("Key Management (not yet implemented)")
        
    def _make_encrypt_screen(self):
        try:
            EncryptDecryptScreen = _import_encrypt_decrypt_screen()
            return EncryptDecryptScreen(self.gpg)
        except (ImportError, ModuleNotFoundError):
            return PlaceholderScreen("Encrypt / Decrypt (not yet implemented)")
        
    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(WELCOME_TEXT, id="welcome-label")
        yield Footer()

    def action_switch_screen(self, screen_name: str) -> None:
        self.switch_screen(screen_name)


WELCOME_TEXT = """\

  ██████╗ ██████╗  ██████╗
 ██╔════╝ ██╔══██╗██╔════╝
 ██║  ███╗██████╔╝██║  ███╗
 ██║   ██║██╔═══╝ ██║   ██║
 ╚██████╔╝██║     ╚██████╔╝
  ╚═════╝ ╚═╝      ╚═════╝   TUI

  GnuPG key management and cryptographic operations.

  Navigation
  ──────────
  K   →   Key Management    (generate, import, export, delete keys)
  E   →   Encrypt / Decrypt  (encrypt, decrypt, sign, verify)
  Q   →   Quit

  The keyring path is shown in the header subtitle.
  Use --gnupghome on the command line to point at a different keyring.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Partizan GNUPG - GnuPG key management and crypto operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--gnupghome",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to the GNUPGHOME keyring directory. "
            "Defaults to ../cipherlib/test_keyring/ (the isolated test keyring). "
            "Pass ~/.gnupg to use your real system keyring."
        )
    )
    parser.add_argument(
        "--gpg-binary",
        type=str,
        default="gpg",
        metavar="BINARY",
        help="Name or full path of the gpg binary (default: gpg)."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        gpg = build_gpg(gnupghome=args.gnupghome, binary=args.gpg_binary)
    except RuntimeError as exc:
        print(f"[FATAL] Failed to initialize GPG: {exc}")
        sys.exit(1)
    
    app = GPGApp(gpg_instance=gpg)
    app.SUB_TITLE = f"keyring: {gpg.gnupghome}"

    app.run()


if __name__ == "__main__":
    main()

