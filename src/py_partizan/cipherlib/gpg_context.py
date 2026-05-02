"""
GPG context setup and configuration.

This is the foundation every other module imports from. It handles:
+ Locating (or creating) a keyring directory
+ Instantiating a python-gnupg GPG object with some defaults
+ Verifying the gpg binary is reachable
+ Exposing a ready-to-use GPG instance + a lightweight result inspector

"""

import os
import sys
from pathlib import Path

import gnupg


DEFAULT_GNUPGHOME = Path(__file__).parent / "test_keyring"

GPG_BINARY = "gpg"


def build_gpg(
    gnupghome: Path | str | None = None,
    binary: str = GPG_BINARY,
    *,
    verbose: bool = False,
    use_agent: bool = False,
    options: list[str] | None = None
) -> gnupg.GPG:
    """
    Construct and return a configured gnupg.GPG instance.
    
    parameters
    ----------
    gnupghome : path-like or None
        Directory that will be used as GNUPGHOME. Created automatically if
        it does not exist. Defaults to DEFAULT_GNUPGHOME.
    binary: str
        Name or full path of the gpg binary.
    verbose: bool
        If True, python-gnupg will emit extra debug output.
    use_agent: bool
        Pass --use-agent to gpg. Usually False for scripted/non-interactive 
        workflows; True when you want the gpg-agent to cache passphrases.
    options: list[str] or None
        Extra command-line options forwarded verbatim to gpg.

    Returns
    -------
    gnupg.GPG
        A ready-to-use GPG instance.

    Raises
    ------
    RuntimeError
        If the GPG binary cannot be found or the keyring dir cannot be
        created.
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
            options=options or []
        )
    except ValueError as exc:
        raise RuntimeError(
            f"Failed to initialize GPG (binary='{binary}'): {exc}\n"
            "Is gpg installed and on your PATH?"
        ) from exc
    
    return gpg


def check_result(result, *, label: str = "operation") -> bool:
    """
    Inspect a python-gnupg result object and print a human-readable summary.
    
    python-gnupg result objects are not uniform - some expose `.ok`, some
    expose `.status`, some expose `.returncode`. This helper normalizes the
    differences so calling code doesn't have to.
    
    Return True when the operation succeeded, False otherwise.
    
    """
    ok_attr = getattr(result, "ok", None)
    status = getattr(result, "status", "")
    stderr = getattr(result, "stderr", "")
    fingerprint = getattr(result, "fingerprint", None)
    fingerprints = getattr(result, "fingerprints", None)

    success = bool(ok_attr) if ok_attr is not None else (status not in ("", None))

    if success:
        print(f"[OK] {label}")
    else:
        print(f"[ERR] {label}")

    if fingerprint:
        print(f"\t\tfingerprint : {fingerprint}")
    if fingerprints:
        print(f"\t\tfingerprints : {fingerprints}")
    if status:
        print(f"\t\t      status : {status}")
    if stderr:
        lines = [ln for ln in stderr.strip().splitlines() if ln]
        tail = lines[-5:] if len(lines) > 5 else lines
        for ln in tail:
            print(f"\t\t      stderr : {ln}")

    return success


def inspect_gpg_version(gpg: gnupg.GPG) -> None:
    """Print the gpg binary version string."""
    version = gpg.version
    print(f"gpg binary version : {version}")
    print(f"GNUPGHOME          : {gpg.gnupghome}")


if __name__ == "__main__":
    print("=====Smoke Test======")

    try:
        gpg = build_gpg(verbose=False)
    except RuntimeError as exc:
        print(f"FATAL: {exc}")
        sys.exit(1)
    
    inspect_gpg_version(gpg)

    public_keys = gpg.list_keys(False)
    private_keys = gpg.list_keys(True)

    print(f"\nPublic keys in keyring : {len(public_keys)}")
    print(f"Private keys in keyring : {len(private_keys)}")

    print("\n[PASS] Context module loaded successfully.")