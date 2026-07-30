#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import logging
import urllib.request

from config import ScheduleSyncConfig

logger = logging.getLogger(__name__)


class ScheduleSyncJob:
    def __init__(self, cfg: ScheduleSyncConfig, csv_path: str) -> None:
        self.cfg = cfg
        self.csv_path = csv_path

    async def run(self) -> None:
        if not self.cfg.enabled:
            return
        while True:
            await asyncio.to_thread(self._sync_once)
            await asyncio.sleep(self.cfg.interval_minutes * 60)

    def _sync_once(self) -> None:
        # The Pi this runs on is often offline (conference wifi, etc.), so any
        # failure here - DNS, timeout, TLS, HTTP error - is expected and just
        # logged; the previous presentations.csv is left in place untouched.
        try:
            with urllib.request.urlopen(
                self.cfg.url, timeout=self.cfg.timeout_seconds
            ) as resp:
                data = resp.read()
        except Exception as e:
            logger.warning("Schedule download failed, keeping existing %s: %s", self.csv_path, e)
            return

        try:
            with open(self.csv_path, "wb") as f:
                f.write(data)
        except OSError as e:
            logger.warning("Could not write %s: %s", self.csv_path, e)
            return

        logger.info("Downloaded schedule to %s (%d bytes)", self.csv_path, len(data))
