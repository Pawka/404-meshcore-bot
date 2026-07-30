#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import random
from pathlib import Path

from config import PeriodicConfig
from printer_worker import PrintJob, PrintJobKind


class FunFileRotator:
    def __init__(self, directory: str, mode: str) -> None:
        self.directory = Path(directory)
        self.mode = mode
        self._idx = 0

    def _list_files(self) -> list[Path]:
        return sorted(self.directory.glob("*.txt")) if self.directory.is_dir() else []

    def next(self) -> str | None:
        files = self._list_files()
        if not files:
            return None
        if self.mode == "random":
            path = random.choice(files)
        else:
            path = files[self._idx % len(files)]
            self._idx += 1
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None


class PeriodicJobs:
    def __init__(self, cfg: PeriodicConfig, queue: "asyncio.Queue[PrintJob]") -> None:
        self.cfg = cfg
        self.queue = queue

    async def run(self) -> None:
        await asyncio.gather(self._logo_loop(), self._fun_files_loop())

    async def _logo_loop(self) -> None:
        if not self.cfg.logo.enabled:
            return
        while True:
            await asyncio.sleep(self.cfg.logo.interval_minutes * 60)
            self.queue.put_nowait(PrintJob(kind=PrintJobKind.LOGO))

    async def _fun_files_loop(self) -> None:
        if not self.cfg.fun_files.enabled:
            return
        rotator = FunFileRotator(self.cfg.fun_files.directory, self.cfg.fun_files.mode)
        while True:
            await asyncio.sleep(self.cfg.fun_files.interval_minutes * 60)
            body = rotator.next()
            if body is not None:
                self.queue.put_nowait(PrintJob(kind=PrintJobKind.FUN_TEXT, text=body))
