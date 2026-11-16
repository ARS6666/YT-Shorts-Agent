import asyncio
import sys
import threading
from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

MAX_HISTORY = 300
MAX_QUEUE = 500


class LiveTerminal:
    def __init__(self):
        self.history = deque(maxlen=MAX_HISTORY)
        self.clients = set()
        self.loop = None
        self.lock = threading.Lock()
        self.original_stdout = None
        self.original_stderr = None
        self.patched_handlers = []

    def publish(self, message: str):
        message = str(message).rstrip("\r\n")
        if not message:
            return

        with self.lock:
            self.history.append(message)

        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(
                self._broadcast, message
            )

    def _broadcast(self, message):
        for queue in list(self.clients):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                pass

    def install(self):
        self.loop = asyncio.get_running_loop()

        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        sys.stdout = TerminalStream(self.original_stdout, self)
        sys.stderr = TerminalStream(self.original_stderr, self)

        # Existing logging handlers may hold the old stderr object.
        # Redirect their streams too, without adding duplicate handlers.
        import logging

        loggers = [
            logging.getLogger(),
            logging.getLogger("uvicorn"),
            logging.getLogger("uvicorn.error"),
            logging.getLogger("uvicorn.access"),
            logging.getLogger("fastapi"),
        ]

        seen = set()

        for logger in loggers:
            for handler in logger.handlers:
                if id(handler) in seen:
                    continue

                seen.add(id(handler))

                if getattr(handler, "stream", None) is self.original_stderr:
                    self.patched_handlers.append(
                        (handler, handler.stream)
                    )
                    handler.stream = sys.stderr

    def restore(self):
        import sys

        for handler, original_stream in self.patched_handlers:
            handler.stream = original_stream

        self.patched_handlers.clear()

        if self.original_stdout:
            sys.stdout = self.original_stdout

        if self.original_stderr:
            sys.stderr = self.original_stderr

        self.loop = None


    async def connect(self, websocket: WebSocket):
        await websocket.accept()

        queue = asyncio.Queue(maxsize=MAX_QUEUE)
        self.clients.add(queue)

        try:
            # Send previous logs safely
            with self.lock:
                previous_logs = list(self.history)

            for message in previous_logs:
                await websocket.send_text(message)

            # Listen for new logs
            while True:
                message = await queue.get()
                await websocket.send_text(message)

        except (WebSocketDisconnect, RuntimeError):
            pass

        except Exception as exc:
            import logging
            logging.getLogger(__name__).debug(
                "Terminal WebSocket disconnected: %s", exc
            )

        finally:
            self.clients.discard(queue)

class TerminalStream:
    def __init__(self, original_stream, terminal):
        self.original_stream = original_stream
        self.terminal = terminal
        self.buffer = ""
        self.lock = threading.Lock()

    def write(self, text):
        if not isinstance(text, str):
            text = str(text)

        # Keep normal PowerShell output working.
        self.original_stream.write(text)

        with self.lock:
            self.buffer += text

            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                self.terminal.publish(line.rstrip("\r"))

        return len(text)

    def flush(self):
        self.original_stream.flush()

        with self.lock:
            if self.buffer.strip():
                self.terminal.publish(self.buffer)
                self.buffer = ""

    def isatty(self):
        return self.original_stream.isatty()

    def fileno(self):
        return self.original_stream.fileno()

    @property
    def encoding(self):
        return self.original_stream.encoding

    @property
    def errors(self):
        return self.original_stream.errors


terminal = LiveTerminal()


@router.websocket("/ws/logs")
async def live_logs(websocket: WebSocket):
    await terminal.connect(websocket)