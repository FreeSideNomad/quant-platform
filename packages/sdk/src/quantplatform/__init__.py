"""Quant Platform SDK."""
__version__ = "0.1.0"

from quantplatform.sdk import data, run
from quantplatform.sdk.strategy import Strategy

__all__ = ["Strategy", "data", "run", "__version__"]
