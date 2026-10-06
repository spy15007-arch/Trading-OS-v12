from pathlib import Path
import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("TradingOS")


def banner(title):
    return f"# {title}\n\n"


def timestamp():
    ist = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
    return ist.strftime("%d-%b-%Y %H:%M IST")


def ensure_reports_folder():
    folder = Path("reports")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def export_markdown(content, filename):
    path = ensure_reports_folder() / filename
    path.write_text(content, encoding="utf-8")
    logger.info(f"Report saved : {path}")
    return path
