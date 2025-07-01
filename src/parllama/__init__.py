"""PAR LLAMA TUI - A terminal user interface for Ollama and other LLM providers."""

from __future__ import annotations

import os
import warnings

import clipman
from langchain_core._api import LangChainBetaWarning

warnings.simplefilter("ignore", category=LangChainBetaWarning)
warnings.simplefilter("ignore", category=DeprecationWarning)

try:
    clipman.init()
except Exception as _:
    pass

__author__ = "Paul Robello"
__copyright__ = "Copyright 2024, Paul Robello"
__credits__ = ["Paul Robello"]
__maintainer__ = "Paul Robello"
__email__ = "probello@gmail.com"
__version__ = "0.3.26"
__licence__ = "MIT"
__application_title__ = "PAR LLAMA"
__application_binary__ = "parllama"

os.environ["USER_AGENT"] = f"{__application_title__} {__version__}"

__all__: list[str] = [
    "__author__",
    "__copyright__",
    "__credits__",
    "__maintainer__",
    "__email__",
    "__version__",
    "__licence__",
    "__application_title__",
    "__application_binary__",
]
