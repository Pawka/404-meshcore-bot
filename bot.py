#!/usr/bin/env python3
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from config import Config
    from meshcore_client import MeshcoreClient


@dataclass
class BotContext:
    meshcore_client: "MeshcoreClient"
    config: "Config"


class BotFeature(Protocol):
    async def run(self, ctx: BotContext) -> None:
        """Run forever (or return immediately if disabled). Must not raise -
        exceptions should be caught internally so one feature failing can't
        take down the others."""
        ...


class Bot:
    def __init__(self, ctx: BotContext, features: list[BotFeature]) -> None:
        self.ctx = ctx
        self.features = features

    async def run(self) -> None:
        await asyncio.gather(*(f.run(self.ctx) for f in self.features))
