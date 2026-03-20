"""
fics.py — FICS (Free Internet Chess Server) TCP connection manager.

Handles the raw TCP connection to freechess.org:5000, strips telnet
control sequences, auto-completes the login handshake, then relays
data bidirectionally between FICS and a FastAPI WebSocket.
"""
import asyncio
import re

FICS_HOST = "freechess.org"
FICS_PORT = 5000
CONNECT_TIMEOUT = 15   # seconds to establish TCP connection
READ_TIMEOUT    = 30   # seconds to wait for login prompts


# ── Telnet stripping ──────────────────────────────────────────────────────────

def strip_telnet(data: bytes) -> str:
    """Remove IAC telnet control sequences and decode to str."""
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0xFF:                          # IAC
            i += 1
            if i < len(data):
                cmd = data[i]
                if cmd in (0xFB, 0xFC, 0xFD, 0xFE):   # WILL/WONT/DO/DONT + option
                    i += 2
                elif cmd == 0xFF:              # escaped 0xFF — literal byte
                    out.append(0xFF)
                    i += 1
                else:
                    i += 1
        else:
            out.append(b)
            i += 1
    text = out.decode("latin-1", errors="replace")
    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


# ── Login handshake ───────────────────────────────────────────────────────────

async def _read_until(reader: asyncio.StreamReader, *targets: str, timeout: float = READ_TIMEOUT) -> str:
    """Read from FICS until any of the target strings appears, with timeout."""
    buf = ""
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise asyncio.TimeoutError(f"Timed out waiting for: {targets}")
        try:
            chunk = await asyncio.wait_for(reader.read(1024), timeout=min(remaining, 2.0))
        except asyncio.TimeoutError:
            continue
        if not chunk:
            raise ConnectionResetError("FICS closed the connection")
        buf += strip_telnet(chunk)
        for target in targets:
            if target in buf:
                return buf


async def login(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    fics_user: str,
    fics_pass: str,
) -> str:
    """
    Drive the FICS login handshake.  Returns all text seen during login
    so the caller can relay it to the browser.
    """
    transcript = ""

    # ── Wait for the login prompt ──────────────────────────────────────────
    text = await _read_until(reader, "login:")
    transcript += text

    # Send username
    writer.write((fics_user.strip() + "\n").encode("latin-1"))
    await writer.drain()

    # ── Guest or registered user? ─────────────────────────────────────────
    text = await _read_until(reader, "password:", "Press return", "login:")
    transcript += text

    if "password:" in text.lower():
        writer.write(((fics_pass or "") + "\n").encode("latin-1"))
        await writer.drain()
        # Read until the prompt that signals we are in
        text = await _read_until(reader, "fics%", "**** Starting", "Invalid", "login:")
        transcript += text
    elif "Press return" in text:
        # Guest login — just press Enter
        writer.write(b"\n")
        await writer.drain()
        text = await _read_until(reader, "fics%", "**** Starting", "login:")
        transcript += text

    # ── Set interface variables for clean output ──────────────────────────
    # style=12 makes FICS send structured "Style 12" board updates
    for cmd in ["set interface ajaxchess.com", "set style 12", ""]:
        writer.write((cmd + "\n").encode("latin-1"))
        await writer.drain()

    return transcript


# ── Session ───────────────────────────────────────────────────────────────────

class FICSSession:
    """Manages one TCP connection to FICS on behalf of a browser WebSocket."""

    def __init__(self):
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    async def connect(self, fics_user: str, fics_pass: str):
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(FICS_HOST, FICS_PORT),
            timeout=CONNECT_TIMEOUT,
        )
        transcript = await login(self.reader, self.writer, fics_user, fics_pass)
        return transcript

    async def send(self, text: str):
        if self.writer:
            self.writer.write((text + "\n").encode("latin-1"))
            await self.writer.drain()

    async def read(self) -> str | None:
        """Read one chunk from FICS.  Returns None on EOF."""
        if not self.reader:
            return None
        try:
            chunk = await self.reader.read(4096)
        except Exception:
            return None
        if not chunk:
            return None
        return strip_telnet(chunk)

    def close(self):
        if self.writer:
            try:
                self.writer.close()
            except Exception:
                pass
        self.reader = None
        self.writer = None
