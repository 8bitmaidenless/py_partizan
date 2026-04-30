"""
Key lifecycle workflows: generate, import, export, list, inspect, and delete.

Covers:
    + Batch key generation (RSA and ED25519)
    + Listing keys with rich attribute access
    + Exporting public and secret keys (ASCII-armored and binary)
    + Importing keys from file or string
    + Searching and filtering keys by fingerprint / UID
    + Deleting public and secret keys safely.
    
"""

import sys
import textwrap
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))
from gpg_context import build_gpg, check_result


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
    passphrase: str | None = None
) -> str | None:
    """
    Generate a new GPG key pair and return the fingerprint on success.
    
    """
    template = RSA_KEY_PARAMS if algorithm.lower() == "rsa" else ECC_KEY_PARAMS

    params = template.format(
        name=name,
        email=email,
        comment=comment,
        expire=expire
    )

    if passphrase:
        params = params.replace(
            "%no-protection",
            f"Passphrase: {passphrase}"
        )

    print(f"Generating {algorithm.upper()} key for <{email}> ... (this may take a moment)")
    result = gpg.gen_key(params)

    if check_result(result, label=f"gen_key({email})"):
        return result.fingerprint
    return None


def list_keys_verbose(gpg, *, secret: bool = False) -> list[dict]:
    keys = gpg.list_keys(secret)
    kind = "secret" if secret else "public"

    print(f"\n{'='*60}")
    print(f"{kind.upper()} KEYS  ({len(keys)} total)")
    print(f"{'='*60}")

    for key in keys:
        uid_str = "; ".join(key.get("uids", ["<no UID>"]))
        print(f"\nFingerprint : {key['fingerprint']}")
        print(f"Key ID : {key['keyid']}")
        print(f"UID(s) : {uid_str}")
        print(f"Type/Length : {key.get('type', '?')} / {key.get('length', '?')}")
        print(f"Trust : {key.get('trust', '?')}")
        print(f"Expires : {key.get('expires', 'never') or 'never'}")
        print(f"Subkeys : {len(key.get('subkeys', []))}")

    return list(keys)


def find_key(gpg, identifier: str, *, secret: bool = False) -> dict | None:
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
    output_path: Path | None = None
) -> str | bytes:
    data = gpg.export_keys(fingerprint, armor=armor)

    if not data:
        print(f"[ERR] export_public_key: no data returned for {fingerprint}")
        return b"" if not armor else ""
    
    if output_path:
        mode = "w" if armor else "wb"
        Path(output_path).write_text(data) if armor else Path(output_path).write_bytes(data.encode())
        print(f"[OK]  Public key written to {output_path}")
    else:
        print(f"[OK]  export_public_key({fingerprint[:16]}...)")
    
    return data


def export_secret_key(
    gpg,
    fingerprint: str,
    *,
    armor: bool = True,
    passphrase: str | None = None,
    output_path: Path | None = None
) -> str | bytes:
    data = gpg.export_keys(
        fingerprint,
        secret=True,
        armor=armor,
        passphrase=passphrase
    )

    if not data:
        print(f"[ERR] export_secret_key: no data returned for {fingerprint}")
        return b"" if not armor else ""
    
    if output_path:
        Path(output_path).write_text(data) if armor else Path(output_path).write_bytes(data.encode())
        print(f"[OK]  Secret key written to {output_path}")
    else:
        print(f"[OK]  export_secret_key({fingerprint[:16]}...)")

    return data


def import_key_data(
    gpg,
    key_data: str | bytes,
    *,
    label: str = "import",
) -> list[str]:
    result = gpg.import_keys(key_data)
    check_result(result, label=label)

    fps = result.fingerprints
    print(f"imported : {len(fps)} key(s)")
    for fp in fps:
        print(f"\t{fp}")

    return fps


def import_key_file(gpg, path: Path | str, *, label: str | None = None) -> list[str]:
    p = Path(path)
    label = label or f"import_key_file({p.name})"
    key_data = p.read_text() if p.suffix in (".asc", ".txt") else p.read_bytes()
    return import_key_data(gpg, key_data, label=label)


def delete_key(
    gpg,
    fingerprint: str,
    *,
    secret: bool = False,
    passphrase: str | None = None
) -> bool:
    kind = "secret" if secret else "public"
    result = gpg.delete_keys(fingerprint, secret=secret, passphrase=passphrase)
    return check_result(result, label=f"delete_key({kind}, {fingerprint[:16]}...)")


# if __name__ == "__main__":
#     print("=== key_management.py ===")

#     gpg = build_gpg()

#     fp_rsa = generate_key(
#         gpg,
#         name="Alice Example",
#         email="alice@example.com",
#         comment="test RSA key",
#         algorithm="rsa",
#         expire="1y"
#     )
#     if not fp_rsa:
#         print("Key generation failed - aborting demo.")
#         sys.exit(1)
    
#     print(f"\nRSA key fingerprint: {fp_rsa}")

#     fp_ecc = generate_key(

#     )