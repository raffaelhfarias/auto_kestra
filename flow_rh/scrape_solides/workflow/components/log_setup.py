"""
Shared logging utility for scraper scripts.
Redirects stdout to both console and a log file, so that WideLogger's
print()-based output is captured in the log directory.
"""

import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BASE_DIR / "log"
LOG_DIR.mkdir(exist_ok=True)


class TeeWriter:
    """Writes output to both the original stdout and a log file."""

    def __init__(self, log_file, original_stdout):
        self.log_file = log_file
        self.original_stdout = original_stdout

    def write(self, data):
        self.original_stdout.write(data)
        self.log_file.write(data)
        self.log_file.flush()

    def flush(self):
        self.original_stdout.flush()
        self.log_file.flush()


def setup_file_logging(script_name: str):
    """
    Redirect stdout so that all print() calls (including WideLogger)
    are also saved to a timestamped log file.

    Args:
        script_name: Name of the script (e.g. 'scrapeCar'), used in the filename.

    Returns:
        The path to the log file.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"{script_name}_{timestamp}.log"
    log_filepath = LOG_DIR / log_filename

    log_file = open(log_filepath, "w", encoding="utf-8")
    sys.stdout = TeeWriter(log_file, sys.__stdout__)

    print(f"📄 Log file: {log_filepath}")
    return log_filepath
