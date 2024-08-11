"""RAG manager for Par Llama."""

from __future__ import annotations

import os

import simplejson as json

from parllama.models.rag import StoreBase
from parllama.par_event_system import ParEventSystemBase
from parllama.par_ollama_embeddings import ParOllamaEmbeddings
from parllama.settings_manager import settings


class RagManager(ParEventSystemBase):
    """RAG manager for Par Llama."""

    stores: list[StoreBase]
    _id_to_store: dict[str, StoreBase] = {}

    def __init__(self):
        """Initialize the data manager."""
        super().__init__(id="rag_manager")
        self._config_file = os.path.join(settings.data_dir, "rag_config.json")
        self.stores = []
        self._id_to_store = {}
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
            self._id_to_store[store.id] = store

    def save(self) -> None:
        """Save the RAG configuration."""
        config = {"stores": self.stores}
        with open(self._config_file, "wt", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, default=str)

    def add_store(self, store: StoreBase) -> None:
        """Add store"""
        self.stores.append(store)
        self._id_to_store[store.id] = store
        self.save()


rag_manager: RagManager = RagManager()

if __name__ == "__main__":
    if len(rag_manager.stores) == 0:
        ollama_emb = ParOllamaEmbeddings(
            model="nomic-embed-text",
            # model="mxbai-embed-large",
        )
        print(ollama_emb.get_dimension())
        ollama_emb = ParOllamaEmbeddings(
            # model="nomic-embed-text",
            model="mxbai-embed-large",
        )
        print(ollama_emb.get_dimension())
        # print(
        #     len(
        #         settings.ollama_client.embed("nomic-embed-text", ["test"])[
        #             "embeddings"
        #         ][0]
        #     )
        # )

        # new_store = VectorStoreMilvus(name="Milvus")
        # new_collection = VectorCollection(dimension=768, name="remember")
        # new_store.add_collection(new_collection)
        # rag_manager.add_store(new_store)
