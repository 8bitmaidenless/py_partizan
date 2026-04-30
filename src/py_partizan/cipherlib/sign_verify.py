import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gpg_context import build_gpg, check_result


@dataclass
class VerificationResult:
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
        maxlen = 15
        lines = [
            # f"  valid\t : {self.valid}",
            f"  valid{' ' * (15-len('valid'))}: {self.valid}",
            f"  fingerprint{' '* (15-len('fingerprint'))}: {self.fingerprint}",
            f"  key_id{' '*(15-len('key_id'))}: {self.key_id}",
            f"  username{' '*(15-len('username'))}: {self.username}",
            f"  status{' '*(15-len('status'))}: {self.status}",
            f"  timestamp{' '*(15-len('timestamp'))}: {self.timestamp}",
            f"  trust_level{' '*(15-len('trust_level')) }: {self.trust_level}"
        ]
        return "\n".join(lines)
    
    @classmethod
    def from_gnupg(cls, result) -> "VerificationResult":
        sigs = getattr(result, "sig_info", {})

        if sigs:
            fp, info = next(iter(sigs.items()))
            key_id = info.get("keyid", "")
            username = info.get("username", "")
            status = info.get("status", "")
            ts = info.get("timestamp")
            exp_ts = info.get("expire_timestamp")
            trust = info.get("trust_level", "")
        else:
            fp = getattr(result, "fingerprint", "") or ""
            key_id = getattr(result, "key_id", "") or ""
            username = getattr(result, "username", "") or ""
            status = getattr(result, "status", "") or ""
            ts = getattr(result, "timestamp", None)
            exp_ts = None
            trust = getattr(result, "trust_level", "") or ""
        
        valid = bool(getattr(result, "valid", False))

        return cls(
            valid=valid,
            fingerprint=fp,
            key_id=key_id,
            username=username,
            status=status,
            timestamp=int(ts) if ts else None,
            expire_timestamp=int(exp_ts) if exp_ts else None,
            trust_level=trust,
            stderr=getattr(result, "stderr", "") or ""
        )
    

def clearsign(
    gpg,
    message: str | bytes,
    signing_fingerprint: str,
    *,
    passphrase: str | None = None,
    detach: bool = False
) -> str | None:
    """
    Produce a clearsigned message.
    
    The returned string contains both the original message and the ASCII-
    armored signature block. Human-readable without gpg.
    
    """
    result = gpg.sign(
        message,
        keyid=signing_fingerprint,
        passphrase=passphrase,
        clearsign=True
    )

    if not result:
        print(f"[ERR] clearsign failed for {signing_fingerprint[:16]}...")
        print(f"\tstderr: {result.stderr}")
        return None
    
    print(f"[OK]  clearsign({signing_fingerprint[:16]}...)")
    return str(result)


def sign_detached(
    gpg,
    message: str | bytes,
    signing_fingerprint: str,
    *,
    passphrase: str | None = None,
    armor: bool = True
) -> str | bytes | None:
    result = gpg.sign(
        message,
        keyid=signing_fingerprint,
        passphrase=passphrase,
        detach=True,
        clearsign=False
    )

    if not result:
        print(f"[ERR] sign_detached failed for {signing_fingerprint[:16]}...")
        print(f"\tstderr: {result.stderr}")
        return None
    
    sig_data = str(result)
    print(f"[OK]  sign_detached({signing_fingerprint[:16]}..., armor={armor})")

    if armor:
        return sig_data
    
    return sig_data


def sign_inline(
    gpg,
    message: str | None,
    signing_fingerprint: str,
    *,
    passphrase: str | None = None
) -> bytes | None:
    result = gpg.sign(
        message,
        keyid=signing_fingerprint,
        passphrase=passphrase,
        detach=False,
        clearsign=False,
        binary=True
    )

    if not result:
        print(f"[ERR] sign_inline failed for {signing_fingerprint[:16]}...")
        return None
    
    print(f"[OK]  sign_inline({signing_fingerprint[:16]}...)")
    return result.data


def sign_file_detached(
    gpg,
    file_path: Path | str,
    signing_fingerprint: str,
    *,
    passphrase: str | None = None,
    output_path: Path | str | None = None,
    armor: bool = True
) -> Path | None:
    src = Path(file_path)
    if not src.exists():
        print(f"[ERR] sign_file_detached: {src} not found")
        return None
    
    ext = ".asc" if armor else ".sig"
    dst = Path(output_path) if output_path else src.with_suffix(src.suffix + ext)

    with open(src, "rb") as file:
        result = gpg.sign_file(
            file,
            keyid=signing_fingerprint,
            passphrase=passphrase,
            detach=True,
            clearsign=False,
            output=str(dst)
        )

    if not result:
        print(f"[ERR] sign_file_detached({src.name}): {result.stderr}")
        return None
    
    print(f"[OK]  sign_file_detached -> {dst}")
    return dst


def verify_clearsign(
    gpg,
    signed_message: str,
    *,
    always_trust: bool = True
) -> VerificationResult:
    result = gpg.verify(signed_message)
    vr = VerificationResult.from_gnupg(result)
    label = "verify_clearsign"
    if vr.valid:
        print(f"[OK]  {label}")
    else:
        print(f"[ERR]  {label}")
    print(vr)
    return vr


def verify_detached(
    gpg,
    message: str | bytes,
    signature: str | bytes
) -> VerificationResult:
    import tempfile, os

    with tempfile.NamedTemporaryFile(delete=False, suffix=".asc") as tmp:
        if isinstance(signature, str):
            tmp.write(signature.encode())
        else:
            tmp.write(signature)
        tmp_path = tmp.name

    try:
        if isinstance(message, str):
            message = message.encode()
        
        result = gpg.verify_data(tmp_path, message)
    finally:
        os.unlink(tmp_path)
    
    vr = VerificationResult.from_gnupg(result)
    label = "verify_detached"
    if vr.valid:
        print(f"[OK]  {label}")
    else:
        print(f"[ERR]  {label}")
    print(vr)
    return vr


def verify_detached_file(
    gpg,
    file_path: Path | str,
    sig_path: Path | str
) -> VerificationResult:
    src = Path(file_path)
    sig = Path(sig_path)

    message_bytes = src.read_bytes()
    sig_bytes = sig.read_bytes()

    return verify_detached(gpg, message_bytes, sig_bytes)


def verify_inline(
    gpg,
    signed_data: bytes
) -> VerificationResult:
    result = gpg.decrypt(signed_data, always_trust=True)

    vr = VerificationResult.from_gnupg(result)
    label = "verify_inline" 
    if vr.valid:
        print(f"[OK]  {label}")
    else:
        print(f"[WARN]  {label} - no valid signature found (or unsigned data)")
    print(vr)
    return vr


if __name__ == "__main__":
    print("=== sign_verify.py demo ===")

    from key_management import generate_key

    gpg = build_gpg()

    print("--- Setup: generating test keys ---")
    fp_alice = generate_key(
        gpg,
        "Alice Signer",
        "alice_sig@example.com",
        algorithm="ecc",
        expire="1y",
        comment="test signer",
        passphrase="onefullsend23"
    )
    fp_bob = generate_key(
        gpg,
        "Bog Signer",
        "bob_sig@example.com",
        algorithm="ecc",
        expire="1y",
        comment="test signer 2",
        passphrase="onefullsend23"
    )

    if not fp_alice:
        print("Key generation failed - aborting.")
        sys.exit(1)
    
    MESSAGE = "This document certifies that Bob owes Alice one coffee.\n"

    print("\n\n--- 1. Clearsign ---")
    cs = clearsign(gpg, MESSAGE, fp_alice, passphrase="onefullsend23")
    if cs:
        print(f"\nClearsigned block:\n{cs}")

        print("\n--- Verify clearsign ---")
        vr = verify_clearsign(gpg, cs)
        assert vr.valid, "Clearsign verification failed!"
        print("[PASS] Clearsign verified")

    print("\n\n--- 2. Tamper test ---")
    if cs:
        tampered = cs.replace("one coffee", "a million dollars")
        vr_tamper = verify_clearsign(gpg, tampered)
        assert not vr_tamper.valid, "Expected verification failure for tampered message!"
        print("[PASS] Tampered message correctly rejected")

    print("\n\n--- 3. Detached signature ---")
    sig = sign_detached(
        gpg,
        MESSAGE,
        fp_alice,
        armor=True,
        passphrase="onefullsend23"
    )
    if sig:
        print(f"\nDetached signature:\n{sig[:120]}...")

        print("\n--- Verify detached ---")
        vr_det = verify_detached(gpg, MESSAGE, sig)
        assert vr_det.valid, "Detached verification failed!"
        print("[PASS] Detached signature verified.")

    print("\n\n--- 4. File detached signature ---")
    tmp_dir = Path(__file__).parent / "test_files"
    tmp_dir.mkdir(exist_ok=True)
    doc = tmp_dir / "document.txt"
    doc.write_text(MESSAGE)

    sig_file = sign_file_detached(
        gpg,
        doc,
        fp_alice,
        passphrase="onefullsend23"
    )
    if sig_file:
        vr_file = verify_detached_file(gpg, doc, sig_file)
        assert vr_file.valid, "File detached verification failed!"
        print("[PASS] File detached signature verified.")

    print("\n\n--- 5. Inline sign --- ")
    signed_blob = sign_inline(
        gpg,
        MESSAGE.encode(),
        fp_alice,
        passphrase="onefullsend23"
    )
    if signed_blob:
        print(f"Signed blob length: {len(signed_blob)} bytes")
        vr_inline = verify_inline(gpg, signed_blob)

        print(f"Inline valid: {vr_inline.valid}")

    print("\n\n[DONE] sign_verify.py demo complete.")
