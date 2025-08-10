from __future__ import annotations

import os
import signal
import subprocess
import time
from typing import List, Tuple, Optional, Callable


def _kill_process_tree(process: subprocess.Popen) -> None:
    """Best-effort kill of a process and its children across platforms."""
    pid = getattr(process, "pid", None)
    if pid is None:
        try:
            process.kill()
        except Exception:
            pass
        return
    if os.name == "nt":
        # On Windows, use taskkill to terminate the entire tree
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           check=False)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
    else:
        # POSIX: send signals to the whole process group
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            time.sleep(0.5)
            if process.poll() is None:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass


def run_shell(
    command: str,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None,
    stdin: Optional[str] = None,
) -> Tuple[int, str, str]:
    # Force UTF-8 decoding with replacement to avoid Windows cp1252 decode crashes
    popen_kwargs = dict(
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if stdin is not None:
        popen_kwargs["stdin"] = subprocess.PIPE
    # Start in a separate process group/session so we can kill the whole tree on timeout
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        popen_kwargs["preexec_fn"] = os.setsid  # type: ignore[assignment]

    process = subprocess.Popen(command, **popen_kwargs)
    try:
        if stdin is not None:
            stdout, stderr = process.communicate(input=stdin, timeout=timeout)
        else:
            stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_tree(process)
        stdout, stderr = process.communicate()
        stderr = (stderr or "") + "\n[KILLED AFTER TIMEOUT]"
    return process.returncode, stdout, stderr


def run_shell_stream(
    command: str,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None,
    on_line: Optional[Callable[[str], None]] = None,
) -> Tuple[int, str]:
    """Run a shell command and stream combined stdout/stderr line by line.
    Returns (exit_code, combined_output).
    Note: timeout applies to the entire process; if exceeded, process is killed.
    """
    # Force UTF-8 decoding with replacement to avoid Windows cp1252 decode crashes
    popen_kwargs = dict(
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    # Start in a separate process group/session so we can kill the whole tree on timeout
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        popen_kwargs["preexec_fn"] = os.setsid  # type: ignore[assignment]

    process = subprocess.Popen(command, **popen_kwargs)
    combined: List[str] = []
    start = time.time()
    try:
        if process.stdout is not None:
            while True:
                # Read a single line with a small timeout window by checking process state
                line = process.stdout.readline()
                if line:
                    combined.append(line)
                    if on_line:
                        try:
                            on_line(line.rstrip("\n"))
                        except Exception:
                            pass
                else:
                    # EOF or no more data
                    if process.poll() is not None:
                        break
                    time.sleep(0.05)
                if timeout is not None and (time.time() - start) > timeout:
                    _kill_process_tree(process)
                    combined.append("\n[KILLED AFTER TIMEOUT]\n")
                    break
    finally:
        code = process.wait()
    return code, "".join(combined)

