#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import click

import config as config_module
import reminders as reminders_module
from bot import Bot, BotContext, BotFeature
from meshcore_client import MeshcoreClient
from periodic import PeriodicJobs
from printer_worker import PrintJob, PrinterWorker
from reminders import ReminderFeature
from schedule_sync import ScheduleSyncJob


@click.group()
def cli() -> None:
    """Print incoming Meshcore messages on an EPSON thermal printer."""


@cli.command()
@click.option(
    "--config",
    "-c",
    "config_path",
    default="config.yaml",
    show_default=True,
    type=click.Path(),
)
@click.option("--force", "-f", is_flag=True, help="Overwrite an existing config file.")
def init(config_path: str, force: bool) -> None:
    """Generate a default config.yaml."""
    path = Path(config_path)
    if path.exists() and not force:
        raise click.ClickException(f"{config_path} already exists; use --force to overwrite")
    path.write_text(config_module.DEFAULT_CONFIG_YAML)
    click.echo(f"Wrote {config_path}")

    example_csv_path = path.parent / "presentations.csv.example"
    if not example_csv_path.exists():
        example_csv_path.write_text(reminders_module.EXAMPLE_CSV)
        click.echo(f"Wrote {example_csv_path}")


@cli.command()
@click.option(
    "--config",
    "-c",
    "config_path",
    default="config.yaml",
    show_default=True,
    type=click.Path(exists=True),
)
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
def run(config_path: str, verbose: bool) -> None:
    """Run the Meshcore-to-printer bridge."""
    cfg = config_module.load_config(config_path)
    level = logging.DEBUG if verbose else getattr(logging, cfg.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        asyncio.run(async_main(cfg))
    except KeyboardInterrupt:
        click.echo("\nStopped.")


async def async_main(cfg: config_module.Config) -> None:
    queue: "asyncio.Queue[PrintJob]" = asyncio.Queue()

    printer_worker = PrinterWorker(cfg.printer, cfg.banner, cfg.formatting, queue)
    meshcore_client = MeshcoreClient(cfg.meshcore, cfg.filters, queue)
    periodic = PeriodicJobs(cfg.periodic, queue)
    schedule_sync = ScheduleSyncJob(cfg.schedule_sync, cfg.reminders.csv_path)

    features: list[BotFeature] = [ReminderFeature(cfg.reminders)]
    bot = Bot(BotContext(meshcore_client, cfg), features)

    await asyncio.gather(
        printer_worker.run(),
        meshcore_client.run(),
        periodic.run(),
        schedule_sync.run(),
        bot.run(),
    )


if __name__ == "__main__":
    cli()
