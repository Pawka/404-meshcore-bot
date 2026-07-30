#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime

from config import BannerConfig, FormattingConfig

NORMAL_FONT = "a"
SMALL_FONT = "b"
DIVIDER_WIDTH = 40


def format_hops(path_len: int) -> str:
    if path_len == 255:
        return "direct"
    return f"{path_len} hop{'s' if path_len != 1 else ''}"


def format_time(timestamp: int) -> str:
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def set_normal(printer, align: str = "left", bold: bool = False, font: str = NORMAL_FONT) -> None:
    # custom_size=False is a no-op in escpos (it does not reset a previously
    # set double-width/height mode), so any enlarged text (e.g. the banner
    # title) would otherwise bleed into everything printed after it. Passing
    # custom_size=True with width=height=1 is what actually resets the size.
    printer.set(align=align, font=font, bold=bold, custom_size=True, width=1, height=1)


def divider(printer, fmt_cfg: FormattingConfig) -> str:
    set_normal(printer, align="center", bold=False, font=NORMAL_FONT)
    printer.text("-" * DIVIDER_WIDTH + "\n")
    pad_blank(printer, fmt_cfg.blank_lines_after)


def pad_blank(printer, count: int) -> None:
    if count > 0:
        printer.ln(count)


def print_banner(printer, banner_cfg: BannerConfig, fmt_cfg: FormattingConfig) -> None:
    pad_blank(printer, fmt_cfg.blank_lines_before)

    printer.set(align="center", font=NORMAL_FONT, bold=True, custom_size=True, height=8, width=8)
    printer.text(banner_cfg.title + "\n")

    set_normal(printer, align="center", bold=True, font=NORMAL_FONT)
    printer.text(banner_cfg.subtitle + "\n")

    if banner_cfg.show_date:
        set_normal(printer, align="center", bold=False, font=NORMAL_FONT)
        printer.text(datetime.now().strftime("%Y-%m-%d %H:%M") + "\n")
    divider(printer, fmt_cfg)


def print_announcement(printer, fmt_cfg: FormattingConfig, text: str) -> None:
    pad_blank(printer, fmt_cfg.blank_lines_before)
    set_normal(printer, align="center", bold=True, font=NORMAL_FONT)
    printer.text(f"*** {text} ***\n")
    set_normal(printer, align="left", bold=False, font=NORMAL_FONT)
    pad_blank(printer, fmt_cfg.blank_lines_after)


def print_error(printer, fmt_cfg: FormattingConfig, text: str) -> None:
    pad_blank(printer, fmt_cfg.blank_lines_before)
    set_normal(printer, align="center", bold=True, font=NORMAL_FONT)
    printer.text(f"[ERROR] {text}\n")
    divider(printer, fmt_cfg)


def print_fun_text(printer, fmt_cfg: FormattingConfig, body: str) -> None:
    pad_blank(printer, fmt_cfg.blank_lines_before)
    set_normal(printer, align="left", bold=False, font=NORMAL_FONT)
    printer.text(body)
    if not body.endswith("\n"):
        printer.text("\n")
    pad_blank(printer, fmt_cfg.blank_lines_after)


def format_channel_message(channel_name: str, hops: str, timestamp: str, text: str) -> str:
    return f"[{timestamp}] #{channel_name} ({hops}):\n{text}\n"


def format_direct_message(sender_name: str, hops: str, timestamp: str, text: str) -> str:
    return f"[{timestamp}] @{sender_name} ({hops}):\n{text}\n"


def print_message(printer, fmt_cfg: FormattingConfig, body: str) -> None:
    set_normal(printer, align="left", bold=False, font=NORMAL_FONT)
    printer.text(body)
    printer.ln(fmt_cfg.message_feed_lines)


def is_allowed(name: str, include: list[str], exclude: list[str]) -> bool:
    lname = name.lower()
    if any(lname == x.lower() for x in exclude):
        return False
    if include and not any(lname == x.lower() for x in include):
        return False
    return True
