"""Account-isolated Jupyter kernels for local development only."""

import atexit
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

from jupyter_client import KernelManager


ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class NotebookPool:
    def __init__(self, root: Path, max_kernels: int = 8, idle_seconds: int = 600):
        self.root = root
        self.max_kernels = max_kernels
        self.idle_seconds = idle_seconds
        self.sessions = {}
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.cleaner = None

    @staticmethod
    def _close(session):
        try:
            session["manager"].shutdown_kernel(now=True)
        finally:
            session["client"].stop_channels()

    def _cleanup_loop(self):
        while not self.stop.wait(30):
            self.close_idle()

    def close_idle(self):
        with self.lock:
            for key, session in list(self.sessions.items()):
                if time.monotonic() - session["last_used"] < self.idle_seconds:
                    continue
                if session["lock"].acquire(blocking=False):
                    try:
                        self.sessions.pop(key)
                        self._close(session)
                    finally:
                        session["lock"].release()

    def _get(self, key):
        self.close_idle()
        with self.lock:
            if key in self.sessions:
                return self.sessions[key]
            if len(self.sessions) >= self.max_kernels:
                raise RuntimeError("Notebook 内核已满，请稍后重试或关闭其他笔记本。")
            folder = self.root / uuid4().hex
            folder.mkdir(parents=True, exist_ok=True)
            manager = KernelManager(kernel_name="python3")
            manager.kernel_spec.argv = [sys.executable, "-X", "utf8", "-m", "ipykernel_launcher", "-f", "{connection_file}"]
            env = {name: value for name, value in os.environ.items() if name.upper() in {
                "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
            }}
            env.update(PYTHONUTF8="1", MPLCONFIGDIR=str(folder / "matplotlib"))
            client = None
            try:
                options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
                manager.start_kernel(cwd=str(folder), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
                client = manager.blocking_client()
                client.start_channels()
                client.wait_for_ready(timeout=20)
                client.execute_interactive("%matplotlib inline", silent=True, store_history=False, timeout=20, output_hook=lambda _: None)
            except Exception:
                try:
                    manager.shutdown_kernel(now=True)
                finally:
                    if client:
                        client.stop_channels()
                raise
            session = {"manager": manager, "client": client, "lock": threading.Lock(), "last_used": time.monotonic()}
            self.sessions[key] = session
            if self.cleaner is None:
                self.cleaner = threading.Thread(target=self._cleanup_loop, daemon=True)
                self.cleaner.start()
            return session

    def restart(self, key):
        with self.lock:
            session = self.sessions.get(key)
        if session:
            with session["lock"]:
                with self.lock:
                    if self.sessions.get(key) is session:
                        self.sessions.pop(key)
                self._close(session)

    def execute(self, key, code: str, stdin: str = "", timeout: int = 10):
        session = self._get(key)
        outputs = []
        size = 0
        inputs = iter(stdin.splitlines())

        def append(output):
            nonlocal size
            size += len(json.dumps(output, ensure_ascii=False))
            if size > 2_000_000:
                raise OverflowError("输出超过 2 MB，内核已停止。请减少输出后重新运行。")
            outputs.append(output)

        def output_hook(message):
            kind, content = message["header"]["msg_type"], message["content"]
            if kind == "stream":
                append({"output_type": "stream", "name": content["name"], "text": ANSI.sub("", content["text"])})
            elif kind == "error":
                append({"output_type": "error", "ename": content["ename"], "evalue": content["evalue"], "traceback": [ANSI.sub("", line) for line in content["traceback"]]})
            elif kind in {"display_data", "execute_result"}:
                data = {mime: value for mime, value in content.get("data", {}).items() if mime in {"text/plain", "image/png", "image/jpeg"}}
                item = {"output_type": kind, "data": data, "metadata": {}}
                if kind == "execute_result":
                    item["execution_count"] = content["execution_count"]
                append(item)
            elif kind == "clear_output":
                outputs.clear()

        def stdin_hook(message):
            value = next(inputs, "\x04")
            session["client"].input(value)
            if value != "\x04":
                append({"output_type": "stream", "name": "stdout", "text": message["content"]["prompt"] + value + "\n"})

        reset = False
        with session["lock"]:
            started = time.perf_counter()
            try:
                reply = session["client"].execute_interactive(code, timeout=timeout, allow_stdin=True, output_hook=output_hook, stdin_hook=stdin_hook)
                content = reply["content"]
                exit_code = 0 if content["status"] == "ok" else 1
                count = content.get("execution_count")
            except (TimeoutError, OverflowError) as error:
                reset = True
                exit_code, count = 124, None
                message = f"运行超过 {timeout} 秒，内核已停止；变量已清空。" if isinstance(error, TimeoutError) else str(error)
                outputs.append({"output_type": "error", "ename": type(error).__name__, "evalue": message, "traceback": [message]})
            except Exception:
                reset = True
                raise
            finally:
                duration = round((time.perf_counter() - started) * 1000)
                session["last_used"] = time.monotonic()
                if reset:
                    with self.lock:
                        if self.sessions.get(key) is session:
                            self.sessions.pop(key)
                    self._close(session)
        return {"outputs": outputs, "execution_count": count, "exit_code": exit_code, "duration_ms": duration, "kernel_reset": reset}

    def close_all(self):
        self.stop.set()
        with self.lock:
            keys = list(self.sessions)
        for key in keys:
            self.restart(key)


notebook_pool = NotebookPool(Path(__file__).resolve().parents[1] / "runtime" / "notebooks")
atexit.register(notebook_pool.close_all)
