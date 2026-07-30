#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field

import yaml

DEFAULT_CONFIG_YAML = """\
# 404-meshcore-printer configuration

printer:
  vendor_id: 0x04b8
  product_id: 0x0e15
  profile: "TM-T20II"      # python-escpos profile; drives divider width via profile.get_columns()
  retry_interval_seconds: 5

meshcore:
  port: null                     # explicit port to skip auto-detect, e.g. "/dev/serial/by-id/usb-..."
  baud: 115200
  probe_timeout_seconds: 3       # per-candidate handshake timeout while scanning
  retry_interval_seconds: 5      # delay between rescans when nothing found / after a loss
  candidate_globs:
    - "/dev/serial/by-id/*"
    - "/dev/ttyACM*"
    - "/dev/ttyUSB*"

filters:
  # Empty include = allow all. Exclude always wins, checked after include.
  channels:
    include: []
    exclude: []
  users:
    include: []
    exclude: []

periodic:
  logo:
    enabled: true
    interval_minutes: 360
  fun_files:
    enabled: false
    directory: "fun_texts"
    interval_minutes: 180
    mode: "random"          # "random" or "sequential"

banner:
  title: "404"
  subtitle: "No Trolls Allowed"
  show_date: true

formatting:
  blank_lines_before: 4
  blank_lines_after: 2
  message_feed_lines: 1     # feed between consecutive meshcore messages, no cut

reminders:
  enabled: false                    # flip on once presentations.csv is populated
  csv_path: "presentations.csv"     # no header row: date,time,title,presenter per line
  channel: "general"                # channel name reminders are posted to
  offset_minutes: 10                # how long before the presentation to remind
  poll_interval_seconds: 30         # how often to check the CSV for changes / send due reminders

schedule_sync:
  enabled: true                             # download presentations.csv on a timer
  url: "https://404.notrollsallowed.com/schedule.csv"
  interval_minutes: 60                      # how often to (re)download
  timeout_seconds: 10                       # per-attempt network timeout; failures are logged and skipped

log_level: "INFO"
"""


@dataclass
class PrinterConfig:
    vendor_id: int = 0x04B8
    product_id: int = 0x0E15
    profile: str = "TM-T20II"
    retry_interval_seconds: float = 5.0


@dataclass
class MeshcoreConfig:
    port: str | None = None
    baud: int = 115200
    probe_timeout_seconds: float = 3.0
    retry_interval_seconds: float = 5.0
    candidate_globs: list[str] = field(
        default_factory=lambda: [
            "/dev/serial/by-id/*",
            "/dev/ttyACM*",
            "/dev/ttyUSB*",
        ]
    )


@dataclass
class NameFilter:
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)


@dataclass
class FiltersConfig:
    channels: NameFilter = field(default_factory=NameFilter)
    users: NameFilter = field(default_factory=NameFilter)


@dataclass
class LogoConfig:
    enabled: bool = True
    interval_minutes: int = 60


@dataclass
class FunFilesConfig:
    enabled: bool = False
    directory: str = "fun_texts"
    interval_minutes: int = 180
    mode: str = "random"  # "random" | "sequential"


@dataclass
class PeriodicConfig:
    logo: LogoConfig = field(default_factory=LogoConfig)
    fun_files: FunFilesConfig = field(default_factory=FunFilesConfig)


@dataclass
class BannerConfig:
    title: str = "404"
    subtitle: str = "No Trolls Allowed"
    show_date: bool = True


@dataclass
class FormattingConfig:
    blank_lines_before: int = 4
    blank_lines_after: int = 2
    message_feed_lines: int = 1


@dataclass
class RemindersConfig:
    enabled: bool = False
    csv_path: str = "presentations.csv"
    channel: str = "general"
    offset_minutes: int = 10
    poll_interval_seconds: int = 30


@dataclass
class ScheduleSyncConfig:
    enabled: bool = True
    url: str = "https://404.notrollsallowed.com/schedule.csv"
    interval_minutes: int = 60
    timeout_seconds: int = 10


@dataclass
class Config:
    printer: PrinterConfig = field(default_factory=PrinterConfig)
    meshcore: MeshcoreConfig = field(default_factory=MeshcoreConfig)
    filters: FiltersConfig = field(default_factory=FiltersConfig)
    periodic: PeriodicConfig = field(default_factory=PeriodicConfig)
    banner: BannerConfig = field(default_factory=BannerConfig)
    formatting: FormattingConfig = field(default_factory=FormattingConfig)
    reminders: RemindersConfig = field(default_factory=RemindersConfig)
    schedule_sync: ScheduleSyncConfig = field(default_factory=ScheduleSyncConfig)
    log_level: str = "INFO"


def _name_filter(d: dict) -> NameFilter:
    return NameFilter(
        include=list(d.get("include", [])),
        exclude=list(d.get("exclude", [])),
    )


def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    printer_raw = raw.get("printer", {}) or {}
    printer = PrinterConfig(
        vendor_id=printer_raw.get("vendor_id", PrinterConfig.vendor_id),
        product_id=printer_raw.get("product_id", PrinterConfig.product_id),
        profile=printer_raw.get("profile", PrinterConfig.profile),
        retry_interval_seconds=printer_raw.get(
            "retry_interval_seconds", PrinterConfig.retry_interval_seconds
        ),
    )

    meshcore_raw = raw.get("meshcore", {}) or {}
    default_meshcore = MeshcoreConfig()
    meshcore = MeshcoreConfig(
        port=meshcore_raw.get("port", default_meshcore.port),
        baud=meshcore_raw.get("baud", default_meshcore.baud),
        probe_timeout_seconds=meshcore_raw.get(
            "probe_timeout_seconds", default_meshcore.probe_timeout_seconds
        ),
        retry_interval_seconds=meshcore_raw.get(
            "retry_interval_seconds", default_meshcore.retry_interval_seconds
        ),
        candidate_globs=list(
            meshcore_raw.get("candidate_globs", default_meshcore.candidate_globs)
        ),
    )

    filters_raw = raw.get("filters", {}) or {}
    filters = FiltersConfig(
        channels=_name_filter(filters_raw.get("channels", {}) or {}),
        users=_name_filter(filters_raw.get("users", {}) or {}),
    )

    periodic_raw = raw.get("periodic", {}) or {}
    logo_raw = periodic_raw.get("logo", {}) or {}
    fun_files_raw = periodic_raw.get("fun_files", {}) or {}
    periodic = PeriodicConfig(
        logo=LogoConfig(
            enabled=logo_raw.get("enabled", LogoConfig.enabled),
            interval_minutes=logo_raw.get(
                "interval_minutes", LogoConfig.interval_minutes
            ),
        ),
        fun_files=FunFilesConfig(
            enabled=fun_files_raw.get("enabled", FunFilesConfig.enabled),
            directory=fun_files_raw.get("directory", FunFilesConfig.directory),
            interval_minutes=fun_files_raw.get(
                "interval_minutes", FunFilesConfig.interval_minutes
            ),
            mode=fun_files_raw.get("mode", FunFilesConfig.mode),
        ),
    )

    banner_raw = raw.get("banner", {}) or {}
    banner = BannerConfig(
        title=banner_raw.get("title", BannerConfig.title),
        subtitle=banner_raw.get("subtitle", BannerConfig.subtitle),
        show_date=banner_raw.get("show_date", BannerConfig.show_date),
    )

    formatting_raw = raw.get("formatting", {}) or {}
    formatting = FormattingConfig(
        blank_lines_before=formatting_raw.get(
            "blank_lines_before", FormattingConfig.blank_lines_before
        ),
        blank_lines_after=formatting_raw.get(
            "blank_lines_after", FormattingConfig.blank_lines_after
        ),
        message_feed_lines=formatting_raw.get(
            "message_feed_lines", FormattingConfig.message_feed_lines
        ),
    )

    reminders_raw = raw.get("reminders", {}) or {}
    reminders = RemindersConfig(
        enabled=reminders_raw.get("enabled", RemindersConfig.enabled),
        csv_path=reminders_raw.get("csv_path", RemindersConfig.csv_path),
        channel=reminders_raw.get("channel", RemindersConfig.channel),
        offset_minutes=reminders_raw.get(
            "offset_minutes", RemindersConfig.offset_minutes
        ),
        poll_interval_seconds=reminders_raw.get(
            "poll_interval_seconds", RemindersConfig.poll_interval_seconds
        ),
    )

    schedule_sync_raw = raw.get("schedule_sync", {}) or {}
    schedule_sync = ScheduleSyncConfig(
        enabled=schedule_sync_raw.get("enabled", ScheduleSyncConfig.enabled),
        url=schedule_sync_raw.get("url", ScheduleSyncConfig.url),
        interval_minutes=schedule_sync_raw.get(
            "interval_minutes", ScheduleSyncConfig.interval_minutes
        ),
        timeout_seconds=schedule_sync_raw.get(
            "timeout_seconds", ScheduleSyncConfig.timeout_seconds
        ),
    )

    return Config(
        printer=printer,
        meshcore=meshcore,
        filters=filters,
        periodic=periodic,
        banner=banner,
        formatting=formatting,
        reminders=reminders,
        schedule_sync=schedule_sync,
        log_level=raw.get("log_level", "INFO"),
    )
