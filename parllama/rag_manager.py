"""RAG manager for Par Llama."""

from __future__ import annotations

import os
import simplejson as json

from parllama.models.rag import StoreBase
from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings


class RagManager(ParEventSystemBase):
    """RAG manager for Par Llama."""

    stores: list[StoreBase]

    def __init__(self):
        """Initialize the data manager."""
        super().__init__(id="rag_manager")
        self._config_file = os.path.join(settings.data_dir, "rag_config.json")
        self.stores = []
        self.load()

    def load(self) -> None:
        """Load the RAG configuration."""
        if not os.path.exists(self._config_file):
            return
        with open(self._config_file, "rt", encoding="utf-8") as fh:
            config = json.load(fh)

        for store_config in config["stores"]:
            store_cls = StoreBase.get_class(store_config["type"])
            store = store_cls(**store_config)
            self.stores.append(store)

    def save(self) -> None:
        """Save the RAG configuration."""
        config = {"stores": [store.model_dump() for store in self.stores]}
        with open(self._config_file, "wt", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2)


rag_manager: RagManager = RagManager()
