"""
encrypt_decrypt.py
------------------
Encryption and decryption workflows covering the most common GnuPG use cases:

    - Asymmetric encryption to one or more recipients (public-key)
    - Symmetric encryption (passphrase only, no recipient key needed)
    - ASCII-armor vs. binary output
    - Encrypt-and-sign in one pass
    - Decrypt with passphrase callback
    - File-to-file encryption / decryption
    - Streaming large data through the gpg binary
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gpg_context import build_gpg, check_result


def encrypt_to_recipients(
    gpg,
    plaintext: str | bytes,
    recipients: list[str],
    *,
    armor: bool = True,
    sign: str | None = None,
    passphrase: str | None = None,
    always_trust: bool = True,
    extra_args: list[str] | None = None
) -> str | bytes | None:
    """
    Encrypt `plaintext` to one or more recipient key fingerprints / key IDS.
    
    Parameters
    ----------
    plaintext     : Data to encrypt (`str` or `bytes`)
    recipients    : List of fingerprints, key IDs, or email addresses that
                    gpg can resolve to public keys in the keyring.
    armor         : ASCII-armor the ciphertext (default True).
    sign          : Fingerprint of the signing key. If provided the,
                    ciphertext will be signed in the same gpg call.
    passphrase    : Passphrase for the signing key (if `sign` is set and the 
                    key is passphrase-protected).
    always_trust  : Skip the web-of-trust check. Useful in dev/test where 
                    keys have not been explicitly trusted.
    extra_args    : Additional raw gpg flags, e.g. [`--compress-level`, `"0"`].
    
    Returns
    -------
    `str` (armored) or `bytes` (binary) ciphertext, or `None` on failure.
    """
    result = gpg.encrypt(
        plaintext,
        recipients,
        armor=armor,
        sign=sign,
        passphrase=passphrase,
        always_trust=always_trust,
        extra_args=extra_args or []
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
    cipher_algo: str = "AES256"
) -> str | bytes | None:
    """
    Encrypt `plaintext` symmetrically using `passphrase`.
    
    No recipient public key is needed.  The ciphertext can be decrypted by
    anyone who knows the passphrase.
    
    Parameters
    ----------
    cipher_algo : gpg cipher algorithm name. AES256 is the safe default.
                  Others: CAMELLIA256, TWOFISH, AES192, AES128.
                  
    Returns
    -------
    `str` (armored) or `bytes` (binary) ciphertext, or `None` on failure.
    """
    result = gpg.encrypt(
        plaintext,
        recipients=None,
        symmetric=True,
        passphrase=passphrase,
        armor=armor,
        extra_args=["--cipher-algo", cipher_algo, "--no-symkey-cache"]
    )

    if not check_result(result, label=f"encrypt_symmetric"):
        return None
    
    return result.data.decode("ascii") if armor else result.data


def decrypt_data(
    gpg,
    ciphertext: str | bytes,
    *,
    passphrase: str | None = None,
    always_trust: bool = True
) -> bytes | None:
    """
    Decrypt `ciphertext` and return the plaintext bytes.
    
    Works for both asymmetric (private key in keyring) and symmetric
    (passphrase-only) ciphertext - gpg detects the type automatically.
    
    Parameters
    ----------
    ciphertext   : Armored string or raw bytes ciphertext.
    passphrase   : Passphrase for the decrypting private key or for symmetric
                  decryption. If the key has no passphrase, pass `None`.
    always_trust : Skip trust checks during decryption (matches encrypt call).
    
    Returns
    -------
    `bytes` plaintext, or `None` on failure.
    
    Notes
    -----
    `result.data`  -> bytes plaintext
    `result.ok`    -> bool
    `result.status` -> status string from gpg
    `result.stderr` -> raw gpg stderr (useful for debugging trust issues)
    `result.username` -> UID of the signing key (if the data was signed)
    `result.key_id``  -> key ID used or decryption
    `result.signature_id` -> signature ID if signed
    """
    result = gpg.decrypt(
        ciphertext,
        passphrase=passphrase,
        always_trust=always_trust
    )

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
    always_trust: bool = True
) -> Path | None:
    src = Path(input_path)
    if not src.exists():
        print(f"[ERR] encrypt_file: {src} not found.")
        return None
    
    dst = Path(output_path) if output_path else src.with_suffix(src.suffix + (".asc" if armor else ".gpg"))

    with open(src, "rb") as file:
        result = gpg.encrypt_file(
            file,
            recipients=recipients,
            armor=armor,
            sign=sign,
            passphrase=passphrase,
            always_trust=always_trust,
            output=str(dst),
        )
    
    if not check_result(result, label=f"decrypt_file({src.name})"):
        return None
    
    print(f"\toutput: {dst}")
    return dst


def decrypt_file(
    gpg,
    input_path: Path | str,
    *,
    output_path: Path | str | None = None,
    passphrase: str | None = None,
    always_trust: bool = True
) -> Path | None:
    src = Path(input_path)
    if not src.exists():
        print(f"[ERR]: decrypt_file: {src} not found.")
        return None
    
    if output_path:
        dst = Path(output_path)
    else:
        dst = src.with_suffix("")

    with open(src, "rb") as file:
        result = gpg.decrypt_file(
            file,
            passphrase=passphrase,
            always_trust=always_trust,
            output=str(dst)
        )

    if not check_result(result, label=f"decrypt_file({src.name})"):
        return None

    print(f"\toutput: {dst}")
    return dst


def print_decrypt_signature_info(result) -> None:
    sig_id = getattr(result, "signature_id", None)
    key_id = getattr(result, "key_id", None)
    uid = getattr(result, "username", None)
    trust = getattr(result, "trust_text", None)

    if sig_id or key_id:
        print("\n [Signature embedded in ciphertext]")
        print(f"\tsigner UID : {uid or '<unknown>'}")
        print(f"\tkey ID : {key_id or '<unknown>'}")
        print(f"\ttrust : {trust or '<unknown>'}")
    else:
        print("\n\t [No embedded signature detected]")


if __name__ == "__main__":
    print("=== encrypt_decrypt.py demo ===")

    from key_management import generate_key, list_keys_verbose

    gpg = build_gpg()

    print("--- Setup: generating test keys ---")
    # fp_alice = generate_key(gpg, "Alice Demo", "alice_enc@example.com", algorithm="ecc", expire="1y")
    # fp_bob = generate_key(gpg, "Bob Demo", "bob_enc@example.com", algorithm="ecc", expire="1y")
    fp_alice = generate_key(
        gpg,
        "Alice Demo",
        "alice_enc@example.com",
        expire="1y",
        algorithm="ecc",
        comment="test key",
        passphrase="onefullsend23"
    )
    fp_bob = generate_key(
        gpg,
        "Bob Demo",
        "bob_enc@example.com",
        expire="1y",
        algorithm="ecc",
        comment="test key",
        passphrase="onefullsend23"
    )

    if not fp_alice or not fp_bob:
        print("Key generation failed - aborting demo")
        sys.exit(1)
    
    MESSAGE = b"Hello, Bob! This is a secret message from Alice."

    print("\n--- 1. Asymmetric encryption (Alice -> Bob) ---")
    ciphertext = encrypt_to_recipients(gpg, MESSAGE, [fp_bob], armor=True)
    if ciphertext:
        print(f"Ciphertext (first 80 chars):\n{ciphertext[:80]}...")

    print("\n--- 2. Decrypt ---")
    if ciphertext:
        plaintext = decrypt_data(gpg, ciphertext, passphrase="onefullsend23")
        print(f"Decrypted: '{plaintext}'")
        assert plaintext == MESSAGE, "Round trip mimatch!"
        print("[PASS] Round-trip successful.")

    print("\n--- 3. Encrypt-and-sign ---")
    ct_signed = encrypt_to_recipients(
        gpg,
        MESSAGE,
        [fp_bob],
        armor=True,
        sign=fp_alice,
        passphrase="onefullsend23"
    )
    if ct_signed:
        raw_result = gpg.decrypt(ct_signed, passphrase="onefullsend23", always_trust=True)
        print(f"Decrypted (signed): {raw_result.data}")
        print_decrypt_signature_info(raw_result)

    print("\n--- 4. Symmetric encryption ---")
    PASSPHRASE = "onefullsend23"
    sym_ct = encrypt_symmetric(gpg, MESSAGE, PASSPHRASE, armor=True)
    if sym_ct:
        print(f"Symmetric ciphertext (first 80 chars):\n{sym_ct[:80]}...")
        sym_pt = decrypt_data(gpg, sym_ct, passphrase=PASSPHRASE)
        print(f"Decrypted: {sym_pt}")
        assert sym_pt == MESSAGE
        print("[PASS] Symmetric round-trip successful.")
    
    print("\n--- 5. Binary (non-armored) round-trip ---")
    binary_ct = encrypt_to_recipients(gpg, MESSAGE, [fp_bob], armor=False)
    if binary_ct:
        print(f"Binary ciphertext length: {len(binary_ct)} bytes")
        binary_pt = decrypt_data(gpg, binary_ct, passphrase="onefullsend23")
        assert binary_pt == MESSAGE
        print("[PASS] Binary round-trip successful.")
    
    print("\n--- 6. File encrypt/decrypt ---")
    tmp_dir = Path(__file__).parent / "test_files"
    tmp_dir.mkdir(exist_ok=True)

    plain_file = tmp_dir / "message.txt"
    plain_file.write_bytes(MESSAGE)

    enc_path = encrypt_file(gpg, plain_file, [fp_bob], armor=True)
    if enc_path:
        dec_path = decrypt_file(gpg, enc_path, output_path=tmp_dir / "message_decrypted.txt", passphrase="onefullsend23")
        if dec_path:
            recovered = dec_path.read_bytes()
            assert recovered == MESSAGE
            print("[PASS] File round-trip succeeded.")

    print("\n[DONE]")