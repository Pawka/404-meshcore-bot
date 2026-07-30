#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum, auto

from escpos import exceptions as escpos_exceptions
from escpos.printer import Usb

import text_format
from config import BannerConfig, FormattingConfig, PrinterConfig

logger = logging.getLogger(__name__)


class PrintJobKind(Enum):
    LOGO = auto()
    ANNOUNCEMENT = auto()
    ERROR = auto()
    MESSAGE = auto()
    FUN_TEXT = auto()


@dataclass
class PrintJob:
    kind: PrintJobKind
    text: str = ""


class PrinterWorker:
    def __init__(
        self,
        printer_cfg: PrinterConfig,
        banner_cfg: BannerConfig,
        fmt_cfg: FormattingConfig,
        queue: "asyncio.Queue[PrintJob]",
    ) -> None:
        self.printer_cfg = printer_cfg
        self.banner_cfg = banner_cfg
        self.fmt_cfg = fmt_cfg
        self.queue = queue
        self._startup_banner_done = False

    async def run(self) -> None:
        while True:
            printer = await self._connect_with_retry()

            try:
                if not self._startup_banner_done:
                    await asyncio.to_thread(
                        text_format.print_banner, printer, self.banner_cfg, self.fmt_cfg
                    )
                    self._startup_banner_done = True

                await self._consume_queue(printer)
            except (escpos_exceptions.Error, OSError) as e:
                logger.error("Printer lost mid-job: %s", e)
                await asyncio.to_thread(self._safe_close, printer)

    async def _consume_queue(self, printer) -> None:
        while True:
            job = await self.queue.get()
            logger.info("Print job: %s", job.kind.name)
            await asyncio.to_thread(self._handle_job, printer, job)

    async def _connect_with_retry(self) -> Usb:
        while True:
            printer = Usb(
                self.printer_cfg.vendor_id,
                self.printer_cfg.product_id,
                profile=self.printer_cfg.profile,
            )
            try:
                # Usb() only stores the vendor/product IDs - the actual USB
                # connection is opened lazily on first use, so without this
                # explicit open() the retry loop below never detects that the
                # printer is missing (construction always "succeeds").
                await asyncio.to_thread(printer.open)
                return printer
            except escpos_exceptions.DeviceNotFoundError as e:
                logger.warning(
                    "Printer not found, retrying in %ss: %s",
                    self.printer_cfg.retry_interval_seconds,
                    e,
                )
                await asyncio.sleep(self.printer_cfg.retry_interval_seconds)

    def _handle_job(self, printer, job: PrintJob) -> None:
        if job.kind is PrintJobKind.LOGO:
            text_format.print_banner(printer, self.banner_cfg, self.fmt_cfg)
        elif job.kind is PrintJobKind.ANNOUNCEMENT:
            text_format.print_announcement(printer, self.fmt_cfg, job.text)
        elif job.kind is PrintJobKind.ERROR:
            text_format.print_error(printer, self.fmt_cfg, job.text)
        elif job.kind is PrintJobKind.MESSAGE:
            text_format.print_message(printer, self.fmt_cfg, job.text)
        elif job.kind is PrintJobKind.FUN_TEXT:
            text_format.print_fun_text(printer, self.fmt_cfg, job.text)

    def _safe_close(self, printer) -> None:
        try:
            printer.close()
        except Exception:
            pass
