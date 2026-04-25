"""Quant Platform SDK."""
__version__ = "0.4.2"

from quantplatform.sdk import data, run
from quantplatform.sdk.strategy import Strategy

__all__ = ["Strategy", "data", "run", "__version__"]
