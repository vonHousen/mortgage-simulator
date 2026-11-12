"""Optional local workbook access for development regression checks."""

from pathlib import Path

from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook


def load_reference_workbook(path: Path) -> Workbook:
    """Load cached values from a local Excel reference artifact.

    Args:
        path: Filesystem path to the ignored workbook.

    Returns:
        A read-only workbook exposing cached formula results.
    """
    return load_workbook(path, read_only=True, data_only=True)
