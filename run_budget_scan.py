"""Run the budget (under Rs 500) Trading OS v12 NSE scan."""
from scanner.core.downloader import download_all, get_broad_universe
from scanner.core.market import get_market_regime
from scanner.core.report import write_report
from scanner.core.scoring import scan
from scanner.core.utils import configure_logging


def main():
    configure_logging()

    regime = get_market_regime()

    data = download_all(
        get_broad_universe(1800),
        period="6mo",
        interval="1d",
    )

    results = scan(
        data,
        profile="budget",
        regime=regime["regime"],
    )

    write_report(
        results,
        profile="budget",
        regime=regime["regime"],
    )


if __name__ == "__main__":
    main()
