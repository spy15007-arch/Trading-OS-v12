"""Run one or all Trading OS v12 NSE momentum scan profiles."""
import argparse
import logging

from scanner.core.downloader import download_all, get_broad_universe
from scanner.core.market import get_market_regime
from scanner.core.report import write_report
from scanner.core.scoring import scan
from scanner.core.utils import configure_logging
from telegram_push import send_scan_alert


VALID_PROFILES = ("strict", "aggressive", "budget")


def run_profiles(profiles):
    configure_logging()

    logger = logging.getLogger("TradingOS")

    regime = get_market_regime()

    logger.info(
        "Market regime: %s",
        regime["regime"],
    )

    data = download_all(
        get_broad_universe(1800),
        period="6mo",
        interval="1d",
    )

    if not data:
        logger.error("No usable stock data was downloaded.")
        return 1

    for profile in profiles:
        results = scan(
            data,
            profile=profile,
            regime=regime["regime"],
        )

        write_report(
            results,
            profile=profile,
            regime=regime["regime"],
        )

        send_scan_alert(
            results,
            profile=profile,
            regime=regime["regime"],
        )

    return 0


def main(default_profile="strict"):
    parser = argparse.ArgumentParser(
        description="Trading OS v12 NSE scanner"
    )

    parser.add_argument(
        "--profile",
        choices=("all",) + VALID_PROFILES,
        default=default_profile,
        help="Scan profile to run.",
    )

    arguments = parser.parse_args()

    profiles = (
        VALID_PROFILES
        if arguments.profile == "all"
        else (arguments.profile,)
    )

    return run_profiles(profiles)


if __name__ == "__main__":
    raise SystemExit(main())
