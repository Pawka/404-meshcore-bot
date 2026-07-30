#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import csv
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from bot import BotContext
from config import RemindersConfig
from printer_worker import PrintJob, PrintJobKind

if TYPE_CHECKING:
    from meshcore_client import MeshcoreClient

logger = logging.getLogger(__name__)

# No header row - date,time,title,presenter per line, in that fixed order.
EXAMPLE_CSV = """\
2026-07-17,09:00,Welcome and opening remarks,Alex Chen
2026-07-17,09:30,Deep dive into mesh networking,Jane Doe
2026-07-17,10:15,Thermal printers for fun and profit,Sam Lee
"""


@dataclass(frozen=True)
class Presentation:
    date: str  # "YYYY-MM-DD"
    time: str  # "HH:MM"
    title: str
    presenter: str

    @property
    def when(self) -> datetime:
        return datetime.strptime(f"{self.date} {self.time}", "%Y-%m-%d %H:%M")

    def key(self) -> str:
        return f"{self.date}|{self.time}|{self.title}|{self.presenter}"


def parse_presentations_csv(path: str) -> list["Presentation"]:
    presentations: list[Presentation] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row_num, row in enumerate(reader, start=1):
            if not row or (len(row) == 1 and not row[0].strip()):
                continue  # skip blank lines
            if len(row) != 4:
                raise ValueError(f"row {row_num}: expected 4 columns, got {len(row)}")
            date, time, title, presenter = (v.strip() for v in row)
            p = Presentation(date=date, time=time, title=title, presenter=presenter)
            p.when  # raises ValueError if date/time don't parse
            presentations.append(p)
    return presentations


def format_reminder(p: Presentation) -> str:
    return f"[{p.time}] {p.title} ({p.presenter})"


class ReminderFeature:
    def __init__(self, cfg: RemindersConfig, queue: "asyncio.Queue[PrintJob]") -> None:
        self.cfg = cfg
        self.queue = queue
        self._presentations: list[Presentation] = []
        self._last_good_mtime: float | None = None
        self._sent: dict[str, datetime] = {}  # key -> event datetime, in-memory only
        self._printed: dict[str, datetime] = {}  # key -> event datetime, in-memory only

    async def run(self, ctx: BotContext) -> None:
        if not self.cfg.enabled:
            return
        while True:
            self._maybe_reload()
            await self._send_due(ctx.meshcore_client)
            self._prune_sent()
            await asyncio.sleep(self.cfg.poll_interval_seconds)

    def _maybe_reload(self) -> None:
        try:
            mtime = os.stat(self.cfg.csv_path).st_mtime
        except OSError:
            return  # file missing/not yet created; keep previous list, try again next tick
        if mtime == self._last_good_mtime:
            return
        try:
            new_list = parse_presentations_csv(self.cfg.csv_path)
        except (ValueError, OSError) as e:
            logger.warning("Presentations CSV invalid, keeping previous data: %s", e)
            return
        self._presentations = new_list
        self._last_good_mtime = mtime
        logger.info("Loaded %d presentation(s) from %s", len(new_list), self.cfg.csv_path)

    async def _send_due(self, meshcore_client: "MeshcoreClient") -> None:
        now = datetime.now()
        for p in self._presentations:
            reminder_at = p.when - timedelta(minutes=self.cfg.offset_minutes)
            due = reminder_at <= now < p.when

            if due and p.key() not in self._printed:
                self.queue.put_nowait(
                    PrintJob(kind=PrintJobKind.ANNOUNCEMENT, text=format_reminder(p))
                )
                self._printed[p.key()] = p.when

            if not due or p.key() in self._sent:
                continue
            ok = await meshcore_client.send_channel_message(
                self.cfg.channel, format_reminder(p)
            )
            if ok:
                self._sent[p.key()] = p.when

    def _prune_sent(self) -> None:
        cutoff = datetime.now() - timedelta(days=1)
        self._sent = {k: v for k, v in self._sent.items() if v >= cutoff}
        self._printed = {k: v for k, v in self._printed.items() if v >= cutoff}
