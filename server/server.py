#!/usr/bin/env python3
"""
Merlin — WebSocket server
Receives streams from the phone client and feeds processed context to the AI session.
Broadcasts responses to all connected clients (phone + optional PC dashboard).
Supports stdin REPL for querying from the PC keyboard.
"""

import asyncio
import json
import logging
import os
import sys

import websockets
from websockets.server import WebSocketServerProtocol

from .stream_processor import StreamProcessor
from ai.session import MerlinSession
from ai.tools import set_phone_sender, resolve_phone_file, set_latest_gps

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("merlin.server")

HOST = os.environ.get("MERLIN_HOST", "0.0.0.0")
PORT = int(os.environ.get("MERLIN_PORT", "8765"))

# ── Multi-client tracking ─────────────────────────────────────────────────────

_connected_clients: set[WebSocketServerProtocol] = set()


async def broadcast(msg: dict):
    """Send a JSON message to all connected clients."""
    disconnected = set()
    for ws in _connected_clients:
        try:
            await ws.send(json.dumps(msg))
        except Exception as e:
            log.warning("broadcast to %s failed: %s", ws.remote_address, e)
            disconnected.add(ws)
    for ws in disconnected:
        _connected_clients.discard(ws)


# ── Client handler ─────────────────────────────────────────────────────────────

class ClientHandler:
    def __init__(self, ws: WebSocketServerProtocol, session: MerlinSession):
        self.ws = ws
        self.session = session
        self.processor = StreamProcessor(session, broadcast)
        _connected_clients.add(ws)
        # Register the broadcast function as the phone sender for agent tools
        set_phone_sender(broadcast)

    async def run(self):
        log.info("client connected: %s", self.ws.remote_address)
        # Announce server capabilities
        await broadcast({
            "type": "status",
            "connected": True,
            "model": self.session.model(),
        })
        try:
            async for message in self.ws:
                if isinstance(message, bytes):
                    await self._handle_binary(message)
                else:
                    await self._handle_json(message)
        except websockets.exceptions.ConnectionClosedOK:
            pass
        except Exception as e:
            log.error("client error: %s", e)
        finally:
            _connected_clients.discard(self.ws)
            log.info("client disconnected: %s", self.ws.remote_address)
            await self.processor.flush()

    async def _handle_json(self, raw: str):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("bad JSON from phone")
            return

        mtype = msg.get("type")
        if mtype == "imu":
            await self.processor.on_imu(msg)
        elif mtype == "gps":
            await self.processor.on_gps(msg)
            # Share latest GPS with tools module
            set_latest_gps(msg)
        elif mtype == "query":
            await self.processor.on_query(msg)
        elif mtype == "observe":
            await self.processor.on_observe(msg)
        elif mtype == "mode_change":
            await self.processor.on_mode_change(msg)
        elif mtype == "file_list":
            await self.processor.on_file_list(msg)
        elif mtype == "file_content":
            resolve_phone_file(msg.get("path", ""), msg.get("content", ""))
        elif mtype == "pose":
            await self.processor.on_pose(msg)
        elif mtype == "wake_command":
            await self.processor.on_wake_command(msg)
        elif mtype == "transcription":
            # Real-time transcription from phone — broadcast to all clients for HUD subtitles
            await broadcast(msg)
            # Also translate if in LISTEN mode (fire-and-forget)
            if msg.get("is_final") and self.session:
                asyncio.create_task(self._translate_and_broadcast(msg))
        else:
            log.debug("unknown json type: %s", mtype)

    async def _handle_binary(self, data: bytes):
        nl = data.find(b"\n")
        if nl == -1:
            log.warning("binary message missing header")
            return
        try:
            header = json.loads(data[:nl].decode())
        except Exception:
            log.warning("binary header parse error")
            return

        payload = data[nl + 1:]
        mtype = header.get("type")

        if mtype == "frame":
            await self.processor.on_frame(header, payload)
        elif mtype == "audio":
            await self.processor.on_audio(header, payload)
        else:
            log.debug("unknown binary type: %s", mtype)

    async def _translate_and_broadcast(self, msg: dict):
        """Translate a transcription and send as translation message to all clients."""
        text = msg.get("text", "").strip()
        if not text or len(text) < 3:
            return
        try:
            from server.translate import translate_text
            target = "it"  # default; could be configurable via user_pref
            translated = await translate_text(text, target, backend=self.session._backend)
            if translated and translated != text:
                await broadcast({
                    "type": "translation",
                    "original": text,
                    "translated": translated,
                    "source_lang": "auto",
                    "target_lang": target,
                })
        except Exception as e:
            log.debug("auto-translate skipped: %s", e)


# ── Stdin REPL ────────────────────────────────────────────────────────────────

async def stdin_repl(session: MerlinSession):
    """
    Read queries from stdin (PC keyboard) and pass them to the agent.
    Responses are printed locally and broadcast to all clients.
    """
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    transport, _ = await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    print("\n[Merlin] stdin REPL ready. Type a query and press Enter.\n", flush=True)

    try:
        while True:
            line_bytes = await reader.readline()
            if not line_bytes:
                break
            text = line_bytes.decode("utf-8", errors="replace").strip()
            if not text:
                continue

            log.info("PC query: %s", text)
            try:
                response = await session.query(text, mode="QUERY")
                print(f"\n[Merlin] {response}\n", flush=True)
                await broadcast({"type": "response", "text": response, "mode": "QUERY"})
            except Exception as e:
                log.error("query error: %s", e)
                print(f"[Merlin] Error: {e}\n", flush=True)
    finally:
        transport.close()


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    session = MerlinSession()
    await session.start()

    async def handler(ws):
        client = ClientHandler(ws, session)
        await client.run()

    log.info("Merlin server listening on ws://%s:%d", HOST, PORT)

    async with websockets.serve(handler, HOST, PORT):
        repl_task = asyncio.create_task(stdin_repl(session))
        try:
            await asyncio.Future()  # run forever
        finally:
            repl_task.cancel()
            await asyncio.gather(repl_task, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
