"""PTY manager — opens a pseudo-terminal, spawns a shell, handles async I/O."""

import asyncio
import fcntl
import logging
import os
import pty
import signal
import struct
import termios

log = logging.getLogger("merlin.terminal.pty")


class PtyProcess:
    """Manages a PTY master/slave pair running a shell."""

    def __init__(self, shell: str = "/bin/zsh"):
        self.shell = shell
        self.master_fd: int | None = None
        self.child_pid: int | None = None
        self._reader: asyncio.AbstractEventLoop | None = None
        self.on_output = None  # callback(data: bytes)

    def spawn(self):
        pid, master_fd = pty.fork()
        if pid == 0:
            # Child: set up the slave side and exec the shell
            os.setsid()
            for fd in range(3, 1024):
                try:
                    os.close(fd)
                except OSError:
                    pass
            os.execvp(self.shell, [self.shell, "-i"])
            os._exit(1)

        self.child_pid = pid
        self.master_fd = master_fd
        # Set non-blocking
        fl = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        log.info("spawned shell %s (pid=%d, fd=%d)", self.shell, pid, master_fd)

    async def start_reader(self, loop: asyncio.AbstractEventLoop):
        """Start reading output from the PTY in the background."""
        loop.add_reader(self.master_fd, self._read_callback)

    def _read_callback(self):
        try:
            data = os.read(self.master_fd, 65536)
            if data:
                if self.on_output:
                    self.on_output(data)
            else:
                # EOF — child exited
                self.close()
        except (BlockingIOError, OSError):
            pass

    def write(self, data: bytes):
        """Write data to the PTY (keyboard input)."""
        if self.master_fd is not None:
            try:
                os.write(self.master_fd, data)
            except OSError as e:
                log.warning("pty write error: %s", e)

    def resize(self, rows: int, cols: int):
        """Resize the terminal window."""
        if self.master_fd is not None:
            try:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            except OSError:
                pass

    def close(self):
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        if self.child_pid is not None:
            try:
                os.kill(self.child_pid, signal.SIGTERM)
                os.waitpid(self.child_pid, os.WNOHANG)
            except OSError:
                pass
            self.child_pid = None
        log.info("pty closed")
