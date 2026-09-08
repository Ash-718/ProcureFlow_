"""
Logger factory.

Everything logs under the `innovategov` root so a single logging config in
`app/main.py` controls verbosity for the whole application, and so library
noise stays separable from ours.
"""
from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Child logger under the `innovategov` root."""
    return logging.getLogger("innovategov." + name)
