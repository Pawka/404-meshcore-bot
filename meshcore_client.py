#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import glob
import logging
import os

from meshcore import EventType, MeshCore

import text_format
from config import FiltersConfig, MeshcoreConfig
from printer_worker import PrintJob, PrintJobKind

logger = logging.getLogger(__name__)


class MeshcoreClient:
    def __init__(
        self,
        cfg: MeshcoreConfig,
        filters: FiltersConfig,
        queue: "asyncio.Queue[PrintJob]",
    ) -> None:
        self.cfg = cfg
        self.filters = filters
        self.queue = queue
        self._channel_names: dict[int, str] = {}
        self._ever_connected = False
        self.mc: MeshCore | None = None

    async def run(self) -> None:
        while True:
            mc = await self._connect()
            if mc is None:
                logger.warning(
                    "Meshcore companion not found, retrying in %ss",
                    self.cfg.retry_interval_seconds,
                )
                await asyncio.sleep(self.cfg.retry_interval_seconds)
                continue

            self._channel_names.clear()
            try:
                await mc.commands.get_contacts()
                await self._fetch_channels(mc)
            except Exception as e:
                logger.warning("Failed to fetch contacts/channels: %s", e)

            disconnected = asyncio.Event()
            mc.subscribe(EventType.DISCONNECTED, self._make_disconnect_handler(disconnected))
            mc.subscribe(EventType.CHANNEL_MSG_RECV, self._make_channel_handler())
            mc.subscribe(EventType.CONTACT_MSG_RECV, self._make_direct_handler(mc))
            await mc.start_auto_message_fetching()

            self.mc = mc
            self._announce_connected()
            await disconnected.wait()
            self.mc = None
            self._enqueue_error("Meshcore link lost")

    async def _connect(self) -> MeshCore | None:
        candidates = [self.cfg.port] if self.cfg.port else self._list_candidate_ports()
        for port in candidates:
            try:
                mc = await asyncio.wait_for(
                    MeshCore.create_serial(
                        port,
                        self.cfg.baud,
                        default_timeout=self.cfg.probe_timeout_seconds,
                    ),
                    timeout=self.cfg.probe_timeout_seconds + 2,
                )
            except Exception as e:
                logger.warning("Probe %s failed: %s", port, e)
                continue
            if mc is not None:
                logger.info("Meshcore companion found on %s", port)
                return mc
        return None

    def _list_candidate_ports(self) -> list[str]:
        seen_real: set[str] = set()
        ports: list[str] = []
        for pattern in self.cfg.candidate_globs:
            for path in sorted(glob.glob(pattern)):
                real = os.path.realpath(path)
                if real not in seen_real:
                    seen_real.add(real)
                    ports.append(path)
        return ports

    async def _fetch_channels(self, mc: MeshCore) -> None:
        for idx in range(8):
            result = await mc.commands.get_channel(idx)
            if result.type == EventType.CHANNEL_INFO:
                name = result.payload.get("channel_name", "").strip("\x00")
                if name:
                    self._channel_names[idx] = name

    def _announce_connected(self) -> None:
        text = (
            "Meshcore link established"
            if not self._ever_connected
            else "Meshcore link re-established"
        )
        self._ever_connected = True
        self.queue.put_nowait(PrintJob(kind=PrintJobKind.ANNOUNCEMENT, text=text))

    def _enqueue_error(self, text: str) -> None:
        self.queue.put_nowait(PrintJob(kind=PrintJobKind.ERROR, text=text))

    async def send_channel_message(self, channel_name: str, text: str) -> bool:
        if self.mc is None:
            logger.warning("Cannot send to #%s: Meshcore not connected", channel_name)
            return False

        idx = None
        lname = channel_name.lower()
        for candidate_idx, name in self._channel_names.items():
            if name.lower() == lname:
                idx = candidate_idx
                break
        if idx is None:
            logger.warning("Cannot send to #%s: channel not found", channel_name)
            return False

        try:
            result = await self.mc.commands.send_chan_msg(idx, text)
        except Exception as e:
            logger.warning("Failed to send to #%s: %s", channel_name, e)
            return False

        if result.type != EventType.OK:
            logger.warning("Send to #%s rejected: %s", channel_name, result)
            return False
        return True

    def _make_disconnect_handler(self, disconnected: asyncio.Event):
        def _on_disconnect(event) -> None:
            disconnected.set()

        return _on_disconnect

    def _make_channel_handler(self):
        def _on_channel_msg(event) -> None:
            data = event.payload
            idx = data.get("channel_idx", 0)
            name = self._channel_names.get(idx, f"channel-{idx}")
            if not text_format.is_allowed(
                name, self.filters.channels.include, self.filters.channels.exclude
            ):
                return
            body = text_format.format_channel_message(
                name,
                text_format.format_hops(data.get("path_len", 0)),
                text_format.format_time(data.get("sender_timestamp", 0)),
                data.get("text", ""),
            )
            self.queue.put_nowait(PrintJob(kind=PrintJobKind.MESSAGE, text=body))

        return _on_channel_msg

    def _make_direct_handler(self, mc: MeshCore):
        def _on_direct_msg(event) -> None:
            data = event.payload
            prefix = data.get("pubkey_prefix", "unknown")
            contact = mc.get_contact_by_key_prefix(prefix)
            sender = contact.get("adv_name", prefix) if contact else prefix
            if not text_format.is_allowed(
                sender, self.filters.users.include, self.filters.users.exclude
            ):
                return
            body = text_format.format_direct_message(
                sender,
                text_format.format_hops(data.get("path_len", 0)),
                text_format.format_time(data.get("sender_timestamp", 0)),
                data.get("text", ""),
            )
            self.queue.put_nowait(PrintJob(kind=PrintJobKind.MESSAGE, text=body))

        return _on_direct_msg
