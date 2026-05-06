import asyncio
import logging
import subprocess
import shlex

log = logging.getLogger("merlin.sudo")


class SudoContext:
    """Manages a single per-command sudo password prompt.

    Password is NEVER logged, stored, or sent to the agent.
    Held only in the TUI's masked input widget, piped once to sudo -S.
    """

    def __init__(self):
        self._password: str | None = None
        self._cache_expiry: float = 0

    def set_password(self, pw: str):
        self._password = pw

    def clear(self):
        self._password = None

    @property
    def has_password(self) -> bool:
        return self._password is not None

    async def run(self, cmd: str, timeout: int = 60) -> tuple[str, str, int]:
        """Run a command with sudo via -S (stdin password pipe)."""
        if not self._password:
            return "", "sudo password needed", 1

        full_cmd = f"sudo -S {cmd}"
        try:
            proc = await asyncio.create_subprocess_shell(
                full_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=(self._password + "\n").encode()),
                timeout=timeout,
            )
            out = stdout.decode("utf-8", errors="replace").strip()
            err = stderr.decode("utf-8", errors="replace").strip()
            rc = proc.returncode or 0

            if rc != 0 and "incorrect password" in err.lower():
                self.clear()

            return out, err, rc
        except asyncio.TimeoutError:
            return "", "command timed out", 124
        except FileNotFoundError:
            return "", "sudo not found", 127
        except Exception as e:
            return "", str(e), 1

    async def check_needs_password(self, cmd: str) -> bool:
        """Try sudo -n (non-interactive). If it fails, password is needed."""
        try:
            proc = await asyncio.create_subprocess_shell(
                f"sudo -n {cmd}",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            rc = await proc.wait()
            return rc != 0
        except FileNotFoundError:
            return True
        except Exception:
            return True


sudo_ctx = SudoContext()
