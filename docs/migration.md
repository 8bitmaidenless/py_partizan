# Project Migration Document
**GPG/PGP TUI Application — Sprint 1 Handoff**

---

## How to Use This Document

This document is a complete handoff package for a **fresh Claude instance** to continue this project without access to the original chat. It contains:

1. Developer profile and working preferences
2. Full project context and goals
3. Complete current codebase (verbatim)
4. Precise current status and what is done vs. not done
5. Exact next-step instructions for Part 2 (the Textual TUI)

Paste this entire document as the opening message to a new Claude session. You can then say something like: *"Read the migration doc and let's pick up where we left off — starting on the Textual TUI."*

---

## 1. Developer Profile

- **Experience:** Self-taught Python programmer, ~8 years of consistent coding and project building
- **Style preferences:** Reusable, scalable, well-commented code. Explicit is better than implicit. Each module should be independently runnable as a standalone demo/test as well as importable as a library.
- **TUI interest:** Actively exploring Textual as a lightweight, aesthetic, versatile frontend solution for Python projects
- **Project phase:** Early planning / proof-of-concept sprint

---

## 2. Project Overview

A **GnuPG / PGP application** with a Textual TUI frontend. The final application is not yet fully scoped — only the cryptographic backend and the TUI layer are confirmed requirements at this stage.

The project is structured as a **two-part proof-of-concept sprint:**

**Part 1 (COMPLETE):** Build a reusable, well-documented `gnupg_workflows` Python package using the `python-gnupg` library. This package abstracts all common GnuPG CLI operations into clean, callable Python functions. Each module was tested and verified working.

**Part 2 (NEXT):** Use the completed `gnupg_workflows` package as the backend and build a minimally viable **Textual TUI application** that exposes key management and encrypt/decrypt operations through a real interactive interface.

---

## 3. Technology Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12+ | Uses `str \| None` union syntax throughout |
| GPG backend | `python-gnupg` | Wraps the system `gpg` binary via subprocess |
| GPG binary | `gpg` (or `gpg2`) | Must be installed on the host system |
| TUI framework | `Textual` | Part 2 target; not yet started |
| Package structure | `gnupg_workflows/` | Local package, no PyPI publishing needed |

**Install dependencies:**
```bash
pip install python-gnupg textual
```

---

## 4. Repository / File Structure

```
project_root/
├── gnupg_workflows/               ← The completed Part 1 package
│   ├── __init__.py                ← Public API surface, re-exports all symbols
│   ├── _00_gpg_context.py         ← GPG instance builder + result inspector
│   ├── _01_key_management.py      ← Key gen, import, export, list, delete
│   ├── _02_encrypt_decrypt.py     ← Asymmetric + symmetric encrypt/decrypt
│   ├── _03_sign_verify.py         ← Clearsign, detached, inline sign + verify
│   └── _04_armor_binary.py        ← Armor detection, dearmor, re-armor, I/O
├── test_keyring/                  ← Auto-created isolated GNUPGHOME for tests
├── test_keyring_import/           ← Auto-created secondary keyring for import tests
├── test_exports/                  ← Auto-created dir for exported key files
└── test_files/                    ← Auto-created dir for file encrypt/decrypt tests
```

The `test_*` directories are created automatically by the demo scripts and can be deleted freely between runs.

---

## 5. Key Design Decisions (Do Not Revert Without Reason)

**Isolated keyring by default.** `build_gpg()` defaults to `./test_keyring/` rather than `~/.gnupg`. This keeps all testing isolated from the user's real keyring. When building the TUI, expose a config option to point at the system keyring or a user-specified path.

**`always_trust=True` throughout demos.** This bypasses the Web of Trust for scripted workflows. For the TUI, when users import third-party keys, expose explicit trust management via `gpg.trust_keys(fingerprint, "TRUST_FULLY")`. The parameter is already threaded through every relevant function.

**`%no-protection` in key generation batch strings.** Demo keys have no passphrase on the secret key. The `generate_key()` function has a `passphrase=` argument ready — it swaps `%no-protection` for `Passphrase: <value>` in the batch string. The TUI should expose this.

**`_XX_` file naming convention.** Modules are named `_00_gpg_context.py` etc. (with leading underscore) so they work as a proper Python package with clean `from ._00_gpg_context import …` syntax in `__init__.py`, while the numeric prefix keeps them sorted correctly in file explorers.

**`check_result()` is normalisation glue.** python-gnupg result objects are not uniform across operations. `check_result()` in `_00_gpg_context.py` handles the inconsistency so all other modules have a consistent success/failure check. Do not bypass it.

**`verify_inline()` routes through `gpg.decrypt()`.** python-gnupg has no dedicated verify-without-decrypt API for opaque inline signatures. This is a known library limitation. The signature metadata is still correctly populated on the result object. For the TUI, prefer clearsign and detached modes — they are better-supported and more user-friendly.

---

## 6. Complete Codebase

### `gnupg_workflows/__init__.py`

```python
"""
gnupg_workflows
===============
A collection of reusable python-gnupg workflow modules.

Modules
-------
  00_gpg_context    – build_gpg(), check_result(), inspect_gpg_version()
  01_key_management – generate_key(), list_keys_verbose(), export_*(), import_*(), delete_key()
  02_encrypt_decrypt – encrypt_to_recipients(), encrypt_symmetric(), decrypt_data(), *_file()
  03_sign_verify    – clearsign(), sign_detached(), verify_*, VerificationResult
  04_armor_binary   – is_armored(), detect_armor_type(), dearmor(), reenarmor(), split_armored_stream()

Quick start
-----------
    from gnupg_workflows import build_gpg, generate_key, encrypt_to_recipients, decrypt_data

    gpg = build_gpg()
    fp  = generate_key(gpg, "Alice", "alice@example.com")
    ct  = encrypt_to_recipients(gpg, b"secret", [fp])
    pt  = decrypt_data(gpg, ct)
"""

from ._00_gpg_context import build_gpg, check_result, inspect_gpg_version

from ._01_key_management import (
    generate_key,
    list_keys_verbose,
    find_key,
    export_public_key,
    export_secret_key,
    import_key_data,
    import_key_file,
    delete_key,
)

from ._02_encrypt_decrypt import (
    encrypt_to_recipients,
    encrypt_symmetric,
    decrypt_data,
    encrypt_file,
    decrypt_file,
    print_decrypt_signature_info,
)

from ._03_sign_verify import (
    clearsign,
    sign_detached,
    sign_inline,
    sign_file_detached,
    verify_clearsign,
    verify_detached,
    verify_detached_file,
    verify_inline,
    VerificationResult,
)

from ._04_armor_binary import (
    is_armored,
    detect_armor_type,
    dearmor,
    reenarmor,
    read_gpg_file,
    write_gpg_file,
    split_armored_stream,
    parse_armor_headers,
)

__all__ = [
    "build_gpg", "check_result", "inspect_gpg_version",
    "generate_key", "list_keys_verbose", "find_key",
    "export_public_key", "export_secret_key",
    "import_key_data", "import_key_file", "delete_key",
    "encrypt_to_recipients", "encrypt_symmetric",
    "decrypt_data", "encrypt_file", "decrypt_file",
    "print_decrypt_signature_info",
    "clearsign", "sign_detached", "sign_inline", "sign_file_detached",
    "verify_clearsign", "verify_detached", "verify_detached_file",
    "verify_inline", "VerificationResult",
    "is_armored", "detect_armor_type", "dearmor", "reenarmor",
    "read_gpg_file", "write_gpg_file", "split_armored_stream",
    "parse_armor_headers",
]
```

---

### `gnupg_workflows/_00_gpg_context.py`

```python
"""
00_gpg_context.py
-----------------
GPG context setup and configuration.

This is the foundation every other module imports from. It handles:
  - Locating (or creating) a keyring directory
  - Instantiating a python-gnupg GPG object with sane defaults
  - Verifying the gpg binary is reachable
  - Exposing a ready-to-use GPG instance + a lightweight result inspector

Usage (standalone test):
    python 00_gpg_context.py

Usage (as a module):
    from gnupg_workflows._00_gpg_context import build_gpg, check_result
"""

import os
import sys
import gnupg
from pathlib import Path


DEFAULT_GNUPGHOME = Path(__file__).parent / "test_keyring"
GPG_BINARY = "gpg"


def build_gpg(
    gnupghome: Path | str | None = None,
    binary: str = GPG_BINARY,
    *,
    verbose: bool = False,
    use_agent: bool = False,
    options: list[str] | None = None,
) -> gnupg.GPG:
    """
    Construct and return a configured gnupg.GPG instance.

    Parameters
    ----------
    gnupghome : path-like or None
        Directory used as GNUPGHOME. Created automatically if absent.
        Defaults to DEFAULT_GNUPGHOME (project-local, isolated from ~/.gnupg).
    binary : str
        Name or full path of the gpg binary.
    verbose : bool
        If True, python-gnupg emits extra debug output.
    use_agent : bool
        Pass --use-agent to gpg. False for scripted workflows.
    options : list[str] or None
        Extra command-line options forwarded verbatim to gpg.

    Returns
    -------
    gnupg.GPG

    Raises
    ------
    RuntimeError
        If the gpg binary cannot be found or the keyring dir cannot be created.
    """
    home = Path(gnupghome) if gnupghome else DEFAULT_GNUPGHOME

    try:
        home.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Cannot create GNUPGHOME at {home}: {exc}") from exc

    try:
        gpg = gnupg.GPG(
            gnupghome=str(home),
            gpgbinary=binary,
            verbose=verbose,
            use_agent=use_agent,
            options=options or [],
        )
    except ValueError as exc:
        raise RuntimeError(
            f"Failed to initialise GPG (binary='{binary}'): {exc}\n"
            "Is gpg installed and on your PATH?"
        ) from exc

    return gpg


def check_result(result, *, label: str = "operation") -> bool:
    """
    Inspect a python-gnupg result object and print a human-readable summary.

    Normalises across the inconsistent result object shapes that python-gnupg
    returns from different operations. Returns True on success, False on failure.
    """
    ok_attr = getattr(result, "ok", None)
    status      = getattr(result, "status",      "")
    stderr      = getattr(result, "stderr",      "")
    fingerprint = getattr(result, "fingerprint", None)
    fingerprints = getattr(result, "fingerprints", None)

    success = bool(ok_attr) if ok_attr is not None else (status not in ("", None))

    if success:
        print(f"[OK]  {label}")
    else:
        print(f"[ERR] {label}")

    if fingerprint:
        print(f"      fingerprint : {fingerprint}")
    if fingerprints:
        print(f"      fingerprints: {fingerprints}")
    if status:
        print(f"      status      : {status}")
    if stderr:
        lines = [ln for ln in stderr.strip().splitlines() if ln]
        tail = lines[-5:] if len(lines) > 5 else lines
        for ln in tail:
            print(f"      stderr      : {ln}")

    return success


def inspect_gpg_version(gpg: gnupg.GPG) -> None:
    """Print the gpg binary version string and GNUPGHOME path."""
    print(f"gpg binary version : {gpg.binary_version}")
    print(f"GNUPGHOME          : {gpg.gnupghome}")


if __name__ == "__main__":
    print("=== 00_gpg_context: smoke test ===\n")
    try:
        gpg = build_gpg(verbose=False)
    except RuntimeError as exc:
        print(f"FATAL: {exc}")
        sys.exit(1)
    inspect_gpg_version(gpg)
    public_keys  = gpg.list_keys(False)
    private_keys = gpg.list_keys(True)
    print(f"\nPublic keys in keyring  : {len(public_keys)}")
    print(f"Private keys in keyring : {len(private_keys)}")
    print("\n[PASS] Context module loaded successfully.")
```

---

### `gnupg_workflows/_01_key_management.py`

```python
"""
01_key_management.py
--------------------
Key lifecycle workflows: generate, import, export, list, inspect, and delete.

Covers:
  - Batch key generation (RSA 4096 and Ed25519/Cv25519 ECC)
  - Listing keys with rich attribute access
  - Exporting public and secret keys (ASCII-armored and binary)
  - Importing keys from file or string
  - Searching and filtering keys by fingerprint / UID
  - Deleting public and secret keys safely
"""

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _00_gpg_context import build_gpg, check_result


RSA_KEY_PARAMS = textwrap.dedent("""\
    Key-Type: RSA
    Key-Length: 4096
    Subkey-Type: RSA
    Subkey-Length: 4096
    Name-Real: {name}
    Name-Email: {email}
    Name-Comment: {comment}
    Expire-Date: {expire}
    %no-protection
""")

ECC_KEY_PARAMS = textwrap.dedent("""\
    Key-Type: EDDSA
    Key-Curve: ed25519
    Subkey-Type: ECDH
    Subkey-Curve: cv25519
    Name-Real: {name}
    Name-Email: {email}
    Name-Comment: {comment}
    Expire-Date: {expire}
    %no-protection
""")


def generate_key(
    gpg,
    name: str,
    email: str,
    *,
    comment: str = "",
    expire: str = "2y",
    algorithm: str = "rsa",
    passphrase: str | None = None,
) -> str | None:
    """
    Generate a new GPG key pair and return the fingerprint on success.

    algorithm : "rsa" (4096-bit) or "ecc" (Ed25519/Cv25519)
    expire    : "0" = no expiry, "1y", "2y", etc.
    passphrase: If provided, secret key is protected. Otherwise %no-protection.
    """
    template = RSA_KEY_PARAMS if algorithm.lower() == "rsa" else ECC_KEY_PARAMS
    params = template.format(name=name, email=email, comment=comment, expire=expire)
    if passphrase:
        params = params.replace("%no-protection", f"Passphrase: {passphrase}")

    print(f"Generating {algorithm.upper()} key for <{email}> …")
    result = gpg.gen_key(params)
    if check_result(result, label=f"gen_key({email})"):
        return result.fingerprint
    return None


def list_keys_verbose(gpg, *, secret: bool = False) -> list[dict]:
    """Return list of key dicts and print a summary table."""
    keys = gpg.list_keys(secret)
    kind = "secret" if secret else "public"
    print(f"\n{'='*60}")
    print(f"  {kind.upper()} KEYS  ({len(keys)} total)")
    print(f"{'='*60}")
    for key in keys:
        uid_str = "; ".join(key.get("uids", ["<no UID>"]))
        print(f"\n  Fingerprint : {key['fingerprint']}")
        print(f"  Key ID      : {key['keyid']}")
        print(f"  UID(s)      : {uid_str}")
        print(f"  Type/Length : {key.get('type', '?')} / {key.get('length', '?')}")
        print(f"  Trust       : {key.get('trust', '?')}")
        print(f"  Expires     : {key.get('expires', 'never') or 'never'}")
        print(f"  Subkeys     : {len(key.get('subkeys', []))}")
    return list(keys)


def find_key(gpg, identifier: str, *, secret: bool = False) -> dict | None:
    """Return the first key whose fingerprint or any UID contains `identifier`."""
    keys = gpg.list_keys(secret)
    ident_lower = identifier.lower()
    for key in keys:
        if ident_lower in key.get("fingerprint", "").lower():
            return dict(key)
        for uid in key.get("uids", []):
            if ident_lower in uid.lower():
                return dict(key)
    return None


def export_public_key(
    gpg,
    fingerprint: str,
    *,
    armor: bool = True,
    output_path: Path | None = None,
) -> str | bytes:
    """Export a public key by fingerprint. Returns armored str or binary bytes."""
    data = gpg.export_keys(fingerprint, armor=armor)
    if not data:
        print(f"[ERR] export_public_key: no data for {fingerprint}")
        return b"" if not armor else ""
    if output_path:
        Path(output_path).write_text(data) if armor else Path(output_path).write_bytes(data.encode())
        print(f"[OK]  Public key written to {output_path}")
    else:
        print(f"[OK]  export_public_key({fingerprint[:16]}…)")
    return data


def export_secret_key(
    gpg,
    fingerprint: str,
    *,
    armor: bool = True,
    passphrase: str | None = None,
    output_path: Path | None = None,
) -> str | bytes:
    """
    Export a secret key by fingerprint.
    WARNING: Do not log or print the returned data in production.
    """
    data = gpg.export_keys(fingerprint, secret=True, armor=armor, passphrase=passphrase)
    if not data:
        print(f"[ERR] export_secret_key: no data for {fingerprint}")
        return b"" if not armor else ""
    if output_path:
        Path(output_path).write_text(data) if armor else Path(output_path).write_bytes(data.encode())
        print(f"[OK]  Secret key written to {output_path}")
    else:
        print(f"[OK]  export_secret_key({fingerprint[:16]}…)")
    return data


def import_key_data(gpg, key_data: str | bytes, *, label: str = "import") -> list[str]:
    """
    Import one or more keys from a string or bytes blob.
    Returns list of imported fingerprints. Empty list = failure or duplicates.
    """
    result = gpg.import_keys(key_data)
    check_result(result, label=label)
    fps = result.fingerprints
    print(f"      imported    : {len(fps)} key(s)")
    for fp in fps:
        print(f"                    {fp}")
    return fps


def import_key_file(gpg, path: Path | str, *, label: str | None = None) -> list[str]:
    """Import keys from a file on disk."""
    p = Path(path)
    label = label or f"import_key_file({p.name})"
    key_data = p.read_text() if p.suffix in (".asc", ".txt") else p.read_bytes()
    return import_key_data(gpg, key_data, label=label)


def delete_key(
    gpg,
    fingerprint: str,
    *,
    secret: bool = False,
    passphrase: str | None = None,
) -> bool:
    """
    Delete a key from the keyring.
    IMPORTANT: Delete secret key first (secret=True), then public key (secret=False).
    """
    kind = "secret" if secret else "public"
    result = gpg.delete_keys(fingerprint, secret=secret, passphrase=passphrase)
    return check_result(result, label=f"delete_key({kind}, {fingerprint[:16]}…)")


if __name__ == "__main__":
    print("=== 01_key_management: demo ===\n")
    gpg = build_gpg()
    fp_rsa = generate_key(gpg, "Alice Example", "alice@example.com", comment="test RSA key", algorithm="rsa", expire="1y")
    if not fp_rsa:
        sys.exit(1)
    print(f"\nRSA key fingerprint: {fp_rsa}")
    fp_ecc = generate_key(gpg, "Bob Example", "bob@example.com", comment="test ECC key", algorithm="ecc", expire="1y")
    print(f"ECC key fingerprint: {fp_ecc}")
    list_keys_verbose(gpg, secret=False)
    list_keys_verbose(gpg, secret=True)
    found = find_key(gpg, "alice@example.com")
    if found:
        print(f"\nfind_key('alice@example.com') -> {found['fingerprint']}")
    armor_data = export_public_key(gpg, fp_rsa)
    print(f"\nExported public key (first 64 chars): {armor_data[:64]}…")
    out_dir = Path(__file__).parent / "test_exports"
    out_dir.mkdir(exist_ok=True)
    export_public_key(gpg, fp_rsa, output_path=out_dir / "alice_pub.asc")
    export_secret_key(gpg, fp_rsa, output_path=out_dir / "alice_sec.asc")
    print("\n--- Round-trip import test ---")
    fresh_gpg = build_gpg(gnupghome=Path(__file__).parent / "test_keyring_import")
    imported = import_key_data(fresh_gpg, armor_data, label="round-trip import")
    print(f"Round-trip imported fingerprints: {imported}")
    print("\n--- Delete keys ---")
    if fp_ecc:
        delete_key(gpg, fp_ecc, secret=True)
        delete_key(gpg, fp_ecc, secret=False)
    print("\n[DONE] 01_key_management demo complete.")
```

---

### `gnupg_workflows/_02_encrypt_decrypt.py`

```python
"""
02_encrypt_decrypt.py
---------------------
Encryption and decryption workflows:
  - Asymmetric encryption to one or more recipients (public-key)
  - Symmetric encryption (passphrase only, no recipient key needed)
  - ASCII-armor vs. binary output
  - Encrypt-and-sign in one pass
  - File-to-file encryption / decryption
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _00_gpg_context import build_gpg, check_result


def encrypt_to_recipients(
    gpg,
    plaintext: str | bytes,
    recipients: list[str],
    *,
    armor: bool = True,
    sign: str | None = None,
    passphrase: str | None = None,
    always_trust: bool = True,
    extra_args: list[str] | None = None,
) -> str | bytes | None:
    """
    Encrypt plaintext to one or more recipient key fingerprints / key IDs.

    sign         : Fingerprint of signing key for combined encrypt+sign.
    always_trust : Skip web-of-trust check. Set False in production with real trust model.
    Returns armored str (armor=True) or binary bytes (armor=False), or None on failure.
    """
    result = gpg.encrypt(
        plaintext,
        recipients,
        armor=armor,
        sign=sign,
        passphrase=passphrase,
        always_trust=always_trust,
        extra_args=extra_args or [],
    )
    if not check_result(result, label=f"encrypt_to_recipients({recipients})"):
        return None
    return result.data.decode("ascii") if armor else result.data


def encrypt_symmetric(
    gpg,
    plaintext: str | bytes,
    passphrase: str,
    *,
    armor: bool = True,
    cipher_algo: str = "AES256",
) -> str | bytes | None:
    """
    Encrypt plaintext symmetrically using passphrase only (no recipient key needed).
    cipher_algo options: AES256, CAMELLIA256, TWOFISH, AES192, AES128.
    """
    result = gpg.encrypt(
        plaintext,
        recipients=None,
        symmetric=True,
        passphrase=passphrase,
        armor=armor,
        extra_args=["--cipher-algo", cipher_algo, "--no-symkey-cache"],
    )
    if not check_result(result, label="encrypt_symmetric"):
        return None
    return result.data.decode("ascii") if armor else result.data


def decrypt_data(
    gpg,
    ciphertext: str | bytes,
    *,
    passphrase: str | None = None,
    always_trust: bool = True,
) -> bytes | None:
    """
    Decrypt ciphertext and return plaintext bytes.

    Works for both asymmetric (private key in keyring) and symmetric
    (passphrase-only) ciphertext. gpg detects the type automatically.

    Useful result object fields after gpg.decrypt():
      result.data         -> bytes plaintext
      result.ok           -> bool
      result.status       -> status string
      result.stderr       -> raw gpg stderr
      result.username     -> UID of signing key (if signed)
      result.key_id       -> key ID used for decryption
      result.signature_id -> signature ID if signed
    """
    result = gpg.decrypt(ciphertext, passphrase=passphrase, always_trust=always_trust)
    if not check_result(result, label="decrypt_data"):
        return None
    return result.data


def encrypt_file(
    gpg,
    input_path: Path | str,
    recipients: list[str],
    *,
    output_path: Path | str | None = None,
    armor: bool = True,
    sign: str | None = None,
    passphrase: str | None = None,
    always_trust: bool = True,
) -> Path | None:
    """Encrypt a file on disk to one or more recipients. Returns output Path or None."""
    src = Path(input_path)
    if not src.exists():
        print(f"[ERR] encrypt_file: {src} not found")
        return None
    dst = Path(output_path) if output_path else src.with_suffix(src.suffix + (".asc" if armor else ".gpg"))
    with open(src, "rb") as fh:
        result = gpg.encrypt_file(fh, recipients=recipients, armor=armor, sign=sign,
                                   passphrase=passphrase, always_trust=always_trust, output=str(dst))
    if not check_result(result, label=f"encrypt_file({src.name})"):
        return None
    print(f"      output: {dst}")
    return dst


def decrypt_file(
    gpg,
    input_path: Path | str,
    *,
    output_path: Path | str | None = None,
    passphrase: str | None = None,
    always_trust: bool = True,
) -> Path | None:
    """
    Decrypt a file on disk. output_path defaults to input with final extension stripped.
    Returns output Path or None.
    """
    src = Path(input_path)
    if not src.exists():
        print(f"[ERR] decrypt_file: {src} not found")
        return None
    dst = Path(output_path) if output_path else src.with_suffix("")
    with open(src, "rb") as fh:
        result = gpg.decrypt_file(fh, passphrase=passphrase, always_trust=always_trust, output=str(dst))
    if not check_result(result, label=f"decrypt_file({src.name})"):
        return None
    print(f"      output: {dst}")
    return dst


def print_decrypt_signature_info(result) -> None:
    """
    After gpg.decrypt(), check for embedded signature and print signer identity.
    Fields: result.username, result.key_id, result.signature_id, result.trust_text
    """
    sig_id = getattr(result, "signature_id", None)
    key_id = getattr(result, "key_id", None)
    uid    = getattr(result, "username", None)
    trust  = getattr(result, "trust_text", None)
    if sig_id or key_id:
        print("\n  [Signature embedded in ciphertext]")
        print(f"    signer UID  : {uid or '<unknown>'}")
        print(f"    key ID      : {key_id or '<unknown>'}")
        print(f"    trust       : {trust or '<unknown>'}")
    else:
        print("\n  [No embedded signature detected]")


if __name__ == "__main__":
    print("=== 02_encrypt_decrypt: demo ===\n")
    from _01_key_management import generate_key
    gpg = build_gpg()
    print("--- Setup: generating test keys ---")
    fp_alice = generate_key(gpg, "Alice Demo", "alice_enc@example.com", algorithm="ecc", expire="1y")
    fp_bob   = generate_key(gpg, "Bob Demo",   "bob_enc@example.com",   algorithm="ecc", expire="1y")
    if not fp_alice or not fp_bob:
        sys.exit(1)
    MESSAGE = b"Hello, Bob!  This is a secret message from Alice."
    print("\n--- 1. Asymmetric encryption (Alice -> Bob) ---")
    ciphertext = encrypt_to_recipients(gpg, MESSAGE, [fp_bob], armor=True)
    if ciphertext:
        print(f"Ciphertext (first 80 chars):\n{ciphertext[:80]}…")
    print("\n--- 2. Decrypt ---")
    if ciphertext:
        plaintext = decrypt_data(gpg, ciphertext)
        assert plaintext == MESSAGE
        print(f"Decrypted: {plaintext}\n[PASS] Round-trip successful.")
    print("\n--- 3. Encrypt-and-sign ---")
    ct_signed = encrypt_to_recipients(gpg, MESSAGE, [fp_bob], armor=True, sign=fp_alice)
    if ct_signed:
        raw_result = gpg.decrypt(ct_signed, passphrase=None, always_trust=True)
        print_decrypt_signature_info(raw_result)
    print("\n--- 4. Symmetric encryption ---")
    PASSPHRASE = "hunter2-not-a-real-password"
    sym_ct = encrypt_symmetric(gpg, MESSAGE, PASSPHRASE, armor=True)
    if sym_ct:
        sym_pt = decrypt_data(gpg, sym_ct, passphrase=PASSPHRASE)
        assert sym_pt == MESSAGE
        print("[PASS] Symmetric round-trip successful.")
    print("\n--- 5. Binary (non-armored) round-trip ---")
    binary_ct = encrypt_to_recipients(gpg, MESSAGE, [fp_bob], armor=False)
    if binary_ct:
        binary_pt = decrypt_data(gpg, binary_ct)
        assert binary_pt == MESSAGE
        print("[PASS] Binary round-trip successful.")
    print("\n--- 6. File encrypt/decrypt ---")
    tmp_dir = Path(__file__).parent / "test_files"
    tmp_dir.mkdir(exist_ok=True)
    plain_file = tmp_dir / "message.txt"
    plain_file.write_bytes(MESSAGE)
    enc_path = encrypt_file(gpg, plain_file, [fp_bob], armor=True)
    if enc_path:
        dec_path = decrypt_file(gpg, enc_path, output_path=tmp_dir / "message_decrypted.txt")
        if dec_path:
            assert dec_path.read_bytes() == MESSAGE
            print("[PASS] File round-trip successful.")
    print("\n[DONE] 02_encrypt_decrypt demo complete.")
```

---

### `gnupg_workflows/_03_sign_verify.py`

```python
"""
03_sign_verify.py
-----------------
Signing and verification workflows covering all three GnuPG signing modes:

  1. Clearsign   – plaintext + signature in a single armored block (human-readable)
  2. Detached    – signature in a separate .sig/.asc file (original unchanged)
  3. Inline      – binary message + signature in one blob (requires gpg to read)

VerificationResult dataclass normalises the inconsistent python-gnupg result
objects into a clean structured type.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _00_gpg_context import build_gpg, check_result


@dataclass
class VerificationResult:
    """
    Normalised output from a gpg signature verification.

    valid            : True if signature is cryptographically valid AND key is trusted.
    fingerprint      : Fingerprint of the signing key.
    key_id           : Short key ID of the signing key.
    username         : UID string of the signing key.
    status           : gpg status string (e.g. "signature valid").
    timestamp        : Unix timestamp of the signature, or None.
    expire_timestamp : Expiry of the signature, or None.
    trust_level      : gpg trust level string (e.g. "TRUST_FULLY").
    stderr           : Raw gpg stderr output (for debugging).
    """
    valid: bool
    fingerprint: str
    key_id: str
    username: str
    status: str
    timestamp: int | None
    expire_timestamp: int | None
    trust_level: str
    stderr: str

    def __str__(self) -> str:
        return "\n".join([
            f"  valid          : {self.valid}",
            f"  fingerprint    : {self.fingerprint}",
            f"  key_id         : {self.key_id}",
            f"  username       : {self.username}",
            f"  status         : {self.status}",
            f"  timestamp      : {self.timestamp}",
            f"  trust_level    : {self.trust_level}",
        ])

    @classmethod
    def from_gnupg(cls, result) -> "VerificationResult":
        """Build a VerificationResult from a python-gnupg Verify object."""
        sigs = getattr(result, "sig_info", {})
        if sigs:
            fp, info = next(iter(sigs.items()))
            key_id   = info.get("keyid", "")
            username = info.get("username", "")
            status   = info.get("status", "")
            ts       = info.get("timestamp")
            exp_ts   = info.get("expire_timestamp")
            trust    = info.get("trust_level", "")
        else:
            fp       = getattr(result, "fingerprint", "") or ""
            key_id   = getattr(result, "key_id", "") or ""
            username = getattr(result, "username", "") or ""
            status   = getattr(result, "status", "") or ""
            ts       = getattr(result, "timestamp", None)
            exp_ts   = None
            trust    = getattr(result, "trust_level", "") or ""
        valid = bool(getattr(result, "valid", False))
        return cls(valid=valid, fingerprint=fp, key_id=key_id, username=username,
                   status=status, timestamp=int(ts) if ts else None,
                   expire_timestamp=int(exp_ts) if exp_ts else None,
                   trust_level=trust, stderr=getattr(result, "stderr", "") or "")


def clearsign(gpg, message: str | bytes, signing_fingerprint: str,
              *, passphrase: str | None = None) -> str | None:
    """Produce a clearsigned message (--clearsign). Human-readable without gpg."""
    result = gpg.sign(message, keyid=signing_fingerprint, passphrase=passphrase, clearsign=True)
    if not result:
        print(f"[ERR] clearsign failed: {result.stderr}")
        return None
    print(f"[OK]  clearsign({signing_fingerprint[:16]}…)")
    return str(result)


def sign_detached(gpg, message: str | bytes, signing_fingerprint: str,
                  *, passphrase: str | None = None, armor: bool = True) -> str | bytes | None:
    """Produce a detached signature (--detach-sign). Original message unchanged."""
    result = gpg.sign(message, keyid=signing_fingerprint, passphrase=passphrase,
                      detach=True, clearsign=False)
    if not result:
        print(f"[ERR] sign_detached failed: {result.stderr}")
        return None
    print(f"[OK]  sign_detached({signing_fingerprint[:16]}…)")
    return str(result)


def sign_inline(gpg, message: str | bytes, signing_fingerprint: str,
                *, passphrase: str | None = None) -> bytes | None:
    """Produce an inline (opaque) signed message (--sign). Not human-readable."""
    result = gpg.sign(message, keyid=signing_fingerprint, passphrase=passphrase,
                      detach=False, clearsign=False, binary=True)
    if not result:
        print(f"[ERR] sign_inline failed")
        return None
    print(f"[OK]  sign_inline({signing_fingerprint[:16]}…)")
    return result.data


def sign_file_detached(gpg, file_path: Path | str, signing_fingerprint: str,
                       *, passphrase: str | None = None, output_path: Path | str | None = None,
                       armor: bool = True) -> Path | None:
    """Create a detached signature file for a file on disk. Returns sig path or None."""
    src = Path(file_path)
    if not src.exists():
        print(f"[ERR] sign_file_detached: {src} not found")
        return None
    ext = ".asc" if armor else ".sig"
    dst = Path(output_path) if output_path else src.with_suffix(src.suffix + ext)
    with open(src, "rb") as fh:
        result = gpg.sign_file(fh, keyid=signing_fingerprint, passphrase=passphrase,
                                detach=True, clearsign=False, output=str(dst))
    if not result:
        print(f"[ERR] sign_file_detached: {result.stderr}")
        return None
    print(f"[OK]  sign_file_detached -> {dst}")
    return dst


def verify_clearsign(gpg, signed_message: str, *, always_trust: bool = True) -> VerificationResult:
    """Verify a clearsigned message. Returns VerificationResult."""
    result = gpg.verify(signed_message)
    vr = VerificationResult.from_gnupg(result)
    print(f"[{'OK' if vr.valid else 'ERR'}]  verify_clearsign")
    print(vr)
    return vr


def verify_detached(gpg, message: str | bytes, signature: str | bytes) -> VerificationResult:
    """Verify a detached signature against the original message."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(delete=False, suffix=".asc") as tmp:
        tmp.write(signature.encode() if isinstance(signature, str) else signature)
        tmp_path = tmp.name
    try:
        if isinstance(message, str):
            message = message.encode()
        result = gpg.verify_data(tmp_path, message)
    finally:
        os.unlink(tmp_path)
    vr = VerificationResult.from_gnupg(result)
    print(f"[{'OK' if vr.valid else 'ERR'}]  verify_detached")
    print(vr)
    return vr


def verify_detached_file(gpg, file_path: Path | str, sig_path: Path | str) -> VerificationResult:
    """Verify a detached signature against a file on disk."""
    return verify_detached(gpg, Path(file_path).read_bytes(), Path(sig_path).read_bytes())


def verify_inline(gpg, signed_data: bytes) -> VerificationResult:
    """
    Verify and extract an inline-signed blob.
    NOTE: Routes through gpg.decrypt() — python-gnupg limitation.
    Signature metadata is still populated. Prefer clearsign/detached in the TUI.
    """
    result = gpg.decrypt(signed_data, always_trust=True)
    vr = VerificationResult.from_gnupg(result)
    print(f"[{'OK' if vr.valid else 'WARN'}]  verify_inline")
    print(vr)
    return vr


if __name__ == "__main__":
    print("=== 03_sign_verify: demo ===\n")
    from _01_key_management import generate_key
    gpg = build_gpg()
    fp_alice = generate_key(gpg, "Alice Signer", "alice_sig@example.com", algorithm="ecc", expire="1y")
    if not fp_alice:
        sys.exit(1)
    MESSAGE = "This document certifies that Bob owes Alice one coffee.\n"
    print("\n--- 1. Clearsign + verify ---")
    cs = clearsign(gpg, MESSAGE, fp_alice)
    if cs:
        vr = verify_clearsign(gpg, cs)
        assert vr.valid
        print("[PASS] Clearsign verified.")
    print("\n--- 2. Tamper test ---")
    if cs:
        tampered = cs.replace("one coffee", "a million dollars")
        vr_t = verify_clearsign(gpg, tampered)
        assert not vr_t.valid
        print("[PASS] Tampered message correctly rejected.")
    print("\n--- 3. Detached signature ---")
    sig = sign_detached(gpg, MESSAGE, fp_alice)
    if sig:
        vr_d = verify_detached(gpg, MESSAGE, sig)
        assert vr_d.valid
        print("[PASS] Detached signature verified.")
    print("\n--- 4. File detached signature ---")
    tmp_dir = Path(__file__).parent / "test_files"
    tmp_dir.mkdir(exist_ok=True)
    doc = tmp_dir / "document.txt"
    doc.write_text(MESSAGE)
    sig_file = sign_file_detached(gpg, doc, fp_alice)
    if sig_file:
        vr_f = verify_detached_file(gpg, doc, sig_file)
        assert vr_f.valid
        print("[PASS] File detached signature verified.")
    print("\n[DONE] 03_sign_verify demo complete.")
```

---

### `gnupg_workflows/_04_armor_binary.py`

```python
"""
04_armor_binary.py
------------------
ASCII-armor ↔ binary conversion utilities and format-detection helpers.

Handles:
  - Detecting whether a blob is armored or binary
  - Dearmoring (ASCII → binary) without gpg (pure Python base64)
  - Re-armoring (binary → ASCII) using gpg --enarmor via subprocess
  - Reading and writing .asc / .gpg / .sig files safely
  - Extracting the embedded payload type from an armor header
  - Splitting multi-message armor streams
"""

import base64
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _00_gpg_context import build_gpg, check_result


_ARMOR_HEADER_RE = re.compile(
    r"^-----BEGIN PGP (MESSAGE|PUBLIC KEY BLOCK|PRIVATE KEY BLOCK|"
    r"SIGNED MESSAGE|SIGNATURE|ARMORED FILE)-----",
    re.MULTILINE,
)

_ARMOR_TYPES = {
    "MESSAGE":           "encrypted or inline-signed message",
    "PUBLIC KEY BLOCK":  "public key export",
    "PRIVATE KEY BLOCK": "secret key export",
    "SIGNED MESSAGE":    "clearsigned message",
    "SIGNATURE":         "detached signature",
    "ARMORED FILE":      "generic armored file (enarmor output)",
}


def is_armored(data: str | bytes) -> bool:
    """Return True if data looks like an ASCII-armored PGP block."""
    if isinstance(data, bytes):
        try:
            data = data.decode("ascii", errors="ignore")
        except Exception:
            return False
    return bool(_ARMOR_HEADER_RE.search(data))


def detect_armor_type(data: str | bytes) -> str | None:
    """Return a human-readable description of the armored block type, or None."""
    if isinstance(data, bytes):
        try:
            data = data.decode("ascii", errors="ignore")
        except Exception:
            return None
    m = _ARMOR_HEADER_RE.search(data)
    if not m:
        return None
    return _ARMOR_TYPES.get(m.group(1), f"unknown PGP block ({m.group(1)})")


def dearmor(armored: str | bytes) -> bytes:
    """
    Convert ASCII-armored PGP block to raw binary using pure Python (no gpg subprocess).
    Strips CRC24 checksum line. Raises ValueError if no armor header/footer found.
    """
    if isinstance(armored, bytes):
        armored = armored.decode("ascii")
    lines = armored.strip().splitlines()
    header_idx = next((i for i, ln in enumerate(lines) if ln.startswith("-----BEGIN PGP")), None)
    footer_idx = next((i for i, ln in enumerate(lines) if ln.startswith("-----END PGP")), None)
    if header_idx is None or footer_idx is None:
        raise ValueError("No PGP armor header/footer found.")
    body_start = header_idx + 1
    while body_start < footer_idx and lines[body_start].strip():
        body_start += 1
    body_start += 1
    body_lines = [ln for ln in lines[body_start:footer_idx] if not ln.startswith("=")]
    return base64.b64decode("".join(body_lines))


def reenarmor(gpg, binary_data: bytes, *, header_comment: str | None = None) -> str | None:
    """
    Convert raw binary PGP data to ASCII-armored form using gpg --enarmor.
    Note: produces a generic 'ARMORED FILE' block. Prefer armor=True on original ops.
    """
    import subprocess, tempfile, os
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp:
        tmp.write(binary_data)
        tmp_path = tmp.name
    try:
        cmd = [gpg.gpgbinary, "--homedir", gpg.gnupghome, "--batch", "--no-tty", "--enarmor", tmp_path]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            print(f"[ERR] reenarmor: {proc.stderr.decode()}")
            return None
        print("[OK]  reenarmor")
        return proc.stdout.decode("ascii")
    finally:
        os.unlink(tmp_path)


def read_gpg_file(path: Path | str) -> tuple[bytes, bool]:
    """Read a .gpg/.asc/.sig file. Returns (raw_bytes, is_armored_flag)."""
    p = Path(path)
    raw = p.read_bytes()
    return raw, is_armored(raw)


def write_gpg_file(data: str | bytes, path: Path | str, *, mode: str | None = None) -> Path:
    """Write PGP data to a file, auto-detecting text vs binary mode."""
    p = Path(path)
    if mode is None:
        mode = "w" if isinstance(data, str) else "wb"
    if mode == "w":
        p.write_text(data if isinstance(data, str) else data.decode("ascii"))
    else:
        p.write_bytes(data if isinstance(data, bytes) else data.encode("ascii"))
    print(f"[OK]  write_gpg_file -> {p}  ({p.stat().st_size} bytes)")
    return p


def split_armored_stream(text: str) -> list[str]:
    """
    Split a string containing multiple concatenated PGP armored blocks
    into a list of individual armored block strings.
    Useful for keyserver dumps or files with many concatenated exports.
    """
    blocks: list[str] = []
    current_lines: list[str] = []
    in_block = False
    for line in text.splitlines(keepends=True):
        if line.startswith("-----BEGIN PGP"):
            in_block = True
            current_lines = [line]
        elif line.startswith("-----END PGP") and in_block:
            current_lines.append(line)
            blocks.append("".join(current_lines))
            current_lines = []
            in_block = False
        elif in_block:
            current_lines.append(line)
    return blocks


def parse_armor_headers(armored: str | bytes) -> dict[str, str]:
    """
    Extract header key-value pairs from an armored PGP block.
    Standard headers: Version, Comment, Hash, Charset.
    Returns dict[str, str], empty if no headers found.
    """
    if isinstance(armored, bytes):
        armored = armored.decode("ascii", errors="ignore")
    headers: dict[str, str] = {}
    lines = armored.strip().splitlines()
    idx = next((i for i, ln in enumerate(lines) if ln.startswith("-----BEGIN PGP")), None)
    if idx is None:
        return headers
    for line in lines[idx + 1:]:
        if not line.strip():
            break
        if ":" in line:
            key, _, val = line.partition(":")
            headers[key.strip()] = val.strip()
    return headers


if __name__ == "__main__":
    print("=== 04_armor_binary: demo ===\n")
    from _01_key_management import generate_key, export_public_key
    from _02_encrypt_decrypt import encrypt_to_recipients
    gpg = build_gpg()
    fp = generate_key(gpg, "Armor Test", "armor@example.com", algorithm="ecc", expire="1y")
    if not fp:
        sys.exit(1)
    pub_key_armor = export_public_key(gpg, fp, armor=True)
    print(f"Public key armor type  : {detect_armor_type(pub_key_armor)}")
    ct_armor = encrypt_to_recipients(gpg, b"hello", [fp], armor=True)
    if ct_armor:
        print(f"Ciphertext armor type  : {detect_armor_type(ct_armor)}")
    print(f"is_armored(pub key)    : {is_armored(pub_key_armor)}")
    headers = parse_armor_headers(pub_key_armor)
    print(f"Armor headers: {headers}")
    raw_key_bytes = dearmor(pub_key_armor)
    print(f"Armored: {len(pub_key_armor)} chars → Binary: {len(raw_key_bytes)} bytes")
    print(f"First 8 bytes: {raw_key_bytes[:8].hex()}")
    fp2 = generate_key(gpg, "Armor Test 2", "armor2@example.com", algorithm="ecc", expire="1y")
    if fp2:
        pub2 = export_public_key(gpg, fp2, armor=True)
        blocks = split_armored_stream(pub_key_armor + "\n" + pub2)
        print(f"Blocks in combined stream: {len(blocks)}")
    print("\n[DONE] 04_armor_binary demo complete.")
```

---

## 7. Current Status

### Done (Part 1 — Complete)

All five modules written, syntax-verified, and tested on a live system. All standalone demos pass.

| Module | Status | Key exports |
|---|---|---|
| `_00_gpg_context` | Complete | `build_gpg`, `check_result`, `inspect_gpg_version` |
| `_01_key_management` | Complete | `generate_key`, `find_key`, `export_public_key`, `export_secret_key`, `import_key_data`, `import_key_file`, `list_keys_verbose`, `delete_key` |
| `_02_encrypt_decrypt` | Complete | `encrypt_to_recipients`, `encrypt_symmetric`, `decrypt_data`, `encrypt_file`, `decrypt_file`, `print_decrypt_signature_info` |
| `_03_sign_verify` | Complete | `clearsign`, `sign_detached`, `sign_inline`, `sign_file_detached`, `verify_clearsign`, `verify_detached`, `verify_detached_file`, `verify_inline`, `VerificationResult` |
| `_04_armor_binary` | Complete | `is_armored`, `detect_armor_type`, `dearmor`, `reenarmor`, `read_gpg_file`, `write_gpg_file`, `split_armored_stream`, `parse_armor_headers` |
| `__init__.py` | Complete | All symbols re-exported at package level |

### Not Yet Started (Part 2)

The entire Textual TUI layer. No Textual code exists yet.

---

## 8. Part 2 Specification: The Textual TUI

### Goal

Build a minimally viable Textual application that wraps the `gnupg_workflows` package into an interactive TUI. The emphasis is on MVP — working functionality over polish.

### Confirmed Requirements

The TUI must support these two capability areas at minimum:

**Key Management screen:**
- List all keys in the keyring (public + secret indicators)
- Generate a new key (name, email, algorithm choice, expiry, optional passphrase)
- Import a key from a `.asc` file path or pasted ASCII armor
- Export a selected key to file or clipboard
- Delete a key (with confirmation prompt)
- Show key detail (fingerprint, UIDs, subkeys, trust, expiry)

**Encrypt / Decrypt screen:**
- Encrypt text or a file to one or more selected recipients from the keyring
- Symmetric encrypt with passphrase
- Decrypt a ciphertext blob (text paste or file path) and display the result
- Show embedded signature metadata after decrypt if present
- Optionally sign while encrypting (select signing key from keyring)

### Suggested TUI Architecture

```
app.py                     ← Textual App subclass, mounts screens, holds gpg instance
screens/
  key_management.py        ← KeyManagementScreen
  encrypt_decrypt.py       ← EncryptDecryptScreen
widgets/
  key_list.py              ← KeyListWidget (DataTable of keys)
  key_detail.py            ← KeyDetailWidget (static panel)
  operation_log.py         ← OperationLogWidget (scrollable output log)
  passphrase_modal.py      ← PassphraseModal (Input widget in overlay)
gnupg_workflows/           ← The completed Part 1 package (unchanged)
```

### Important Textual Notes

- **Threading:** All `gnupg_workflows` calls must be run in a worker thread (`self.run_worker` or `asyncio.to_thread`) because python-gnupg blocks on subprocess I/O. Never call them directly from reactive handlers or `on_mount`.
- **GPG instance sharing:** Create one `gpg = build_gpg()` instance in the App class and pass it to screens/widgets. Do not create multiple instances.
- **Passphrase input:** Use Textual's `Input` widget with `password=True` inside a `ModalScreen` for passphrase prompts. Do not pass passphrases as constructor args to screens — collect them at the point of use.
- **GNUPGHOME config:** Add a settings/config screen or CLI arg to let users point at their real `~/.gnupg` rather than the test keyring. `build_gpg(gnupghome=Path.home() / ".gnupg")` is all that's needed.

### Style Preferences

- Consistent with the developer's general preference: clean, well-commented, each screen/widget independently testable
- Use Textual CSS (`.tcss` files) for layout rather than inline styles
- Use `DataTable` for the key list — it handles sorting and selection well
- `RichLog` or a `TextArea` (read-only) works well for the operation log output

---

