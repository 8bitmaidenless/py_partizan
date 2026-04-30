import base64
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gpg_context import build_gpg, check_result


_ARMOR_HEADER_RE = re.compile(
    r"^-----BEGIN PGP (MESSAGE|PUBLIC KEY BLOCK|PRIVATE KEY BLOCK|"
    r"SIGNED MESSAGE|SIGNATURE|ARMORED FILE)-----",
    re.MULTILINE
)

_ARMOR_TYPES = {
    "MESSAGE": "encrypted or inline-signed message",
    "PUBLIC KEY BLOCK": "public key export",
    "PRIVATE KEY BLOCK": "private key export",
    "SIGNED MESSAGE": "clearsigned message",
    "SIGNATURE": "detached signature",
    "ARMORED FILE": "generic armored file (enarmor output)",
}


def is_armored(data: str | bytes) -> bool:
    if isinstance(data, bytes):
        try:
            data = data.decode("ascii", errors="ignore")
        except Exception:
            return False
    return bool(_ARMOR_HEADER_RE.search(data))


def detect_armor_type(data: str | bytes) -> str | None:
    if isinstance(data, bytes):
        try:
            data = data.decode("ascii", errors="ignore")
        except Exception:
            return None
        
    m = _ARMOR_HEADER_RE.search(data)
    if not m:
        return None
    
    block_type = m.group(1)
    return _ARMOR_TYPES.get(block_type, f"unknown PGP block ({block_type})")


def dearmor(armored: str | bytes) -> bytes:
    if isinstance(armored, bytes):
        armored = armored.decode("ascii")

    lines = armored.strip().splitlines()

    header_idx = next(
        (i for i, ln in enumerate(lines) if ln.startswith("-----BEGIN PGP")),
        None
    )
    footer_idx = next(
        (i for i, ln in enumerate(lines) if ln.startswith("-----END PGP")),
        None
    )

    if header_idx is None or footer_idx is None:
        raise ValueError("No PGP armor header/footer found.")
    
    body_start = header_idx + 1
    while body_start < footer_idx and lines[body_start].strip():
        body_start += 1
    body_start += 1

    body_lines = [
        ln for ln in lines[body_start:footer_idx]
        if not ln.startswith("=")
    ]

    b64_payload = "".join(body_lines)
    return base64.b64decode(b64_payload)


def reenarmor(
    gpg,
    binary_data: bytes,
    *,
    header_comment: str | None = None
) -> str | None:
    import subprocess, tempfile, os

    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp:
        tmp.write(binary_data)
        tmp_path = tmp.name

    try:
        cmd = [gpg.gpgbinary, "--homedir", gpg.gnupghome,
               "--batch", "--no-tty", "--enarmor", tmp_path]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            print(f"[ERR] reenarmor: {proc.stderr.decode()}")
            return None
        armored = proc.stdout.decode("ascii")
        print("[OK]  reenarmor")
        return armored
    finally:
        os.unlink(tmp_path)


def read_gpg_file(path: Path | str) -> tuple[bytes, bool]:
    p = Path(path)
    raw = p.read_bytes()
    armored = is_armored(raw)
    return raw, armored


def write_gpg_file(
    data: str | bytes,
    path: Path | str,
    *,
    mode: str | None = None
) -> Path:
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
    print("=== armor_binary.py: demo ===")

    from key_management import generate_key, export_public_key
    from encrypt_decrypt import encrypt_to_recipients

    gpg = build_gpg()

    fp = generate_key(
        gpg,
        "Armor Test",
        "armor@example.com",
        algorithm="ecc",
        expire="1y",
        comment="armor test",
        passphrase="armorphrase123"
    )
    if not fp:
        sys.exit(1)

    print("\n\n--- 1. Armor type detection ---")
    pub_key_armor = export_public_key(gpg, fp, armor=True)
    print(f"Public key armor type : {detect_armor_type(pub_key_armor)}")

    ct_armor = encrypt_to_recipients(gpg, b"Hello", [fp], armor=True)
    if ct_armor:
        print(f"Ciphertext armor type : {detect_armor_type(ct_armor)}")

    print(f"is_armored(pub_key)     : {is_armored(pub_key_armor)}")
    print(f"is_armored(b'random')   : {is_armored(b'random bytes here')}") 

    print("\n\n--- 2. Armor header parsing ---")
    headers = parse_armor_headers(pub_key_armor)
    for k, v in headers.items():
        print(f"\t{k}: {v}")

    print("\n\n--- 3. Dearmor (pure Python) ---")
    raw_key_bytes = dearmor(pub_key_armor)
    print(f"Armored length : {len(pub_key_armor)} chars")
    print(f"Binary length  : {len(raw_key_bytes)} bytes")
    print(f"First 8 bytes  : {raw_key_bytes[:8].hex()}  (should start with 0x99 for OpenPGP packet)")

    print("\n\n--- 4. Re-armor ---")
    rearmored = reenarmor(gpg, raw_key_bytes)
    if rearmored:
        retype = detect_armor_type(rearmored)
        print(f"Re-armored block type  : {retype}")
        print(f"Re-armored length      : {len(rearmored)} chars")

    print("\n\n--- 5. Multi-block stream split ---")
    fp2 = generate_key(
        gpg,
        "Armor Test2",
        "armor2@example.com",
        algorithm="ecc",
        expire="1y",
        comment="armor test #2",
        passphrase="armorpass123"
    )
    if fp2:
        pub2 = export_public_key(gpg, fp2, armor=True)
        combined = pub_key_armor + "\n" + pub2
        blocks = split_armored_stream(combined)
        print(f"Blocks found in combined stream: {len(blocks)}")
        for i, blk in enumerate(blocks):
            print(f"\tBlock {i+1}: {detect_armor_type(blk)}")

    print("\n\n--- 6. File I/O ---")
    out_dir = Path(__file__).parent / "test_files"
    out_dir.mkdir(exist_ok=True)

    asc_path = write_gpg_file(pub_key_armor, out_dir / "test_pub.asc")
    raw_data, was_armored = read_gpg_file(asc_path)
    print(f"read_gpg_file: {len(raw_data)} bytes, is_armored={was_armored}")
    print("\n\n[DONE] armor_binary.py demo complete ===")