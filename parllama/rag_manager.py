"""RAG manager for Par Llama."""

from __future__ import annotations

import os

import simplejson as json
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_ollama import ChatOllama

from parllama.models.rag import StoreBase, VectorStoreChroma
from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings

load_dotenv(os.path.expanduser("~/.parllama/.env"))


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
        # self.load()

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
        # ollama_emb = ParOllamaEmbeddings(
        #     model="nomic-embed-text",
        #     # model="mxbai-embed-large",
        # )
        # print(ollama_emb.get_dimension())
        # ollama_emb = ParOllamaEmbeddings(
        #     # model="nomic-embed-text",
        #     model="mxbai-embed-large",
        # )
        # print(ollama_emb.get_dimension())
        # print(
        #     len(
        #         ollama.Client(host=settings.ollama_host).embed("nomic-embed-text", ["test"])[
        #             "embeddings"
        #         ][0]
        #     )
        # )

        new_store = VectorStoreChroma(
            name="Chroma",
            collection_name="remember",
            embeddings_model="mxbai-embed-large",
        )
        rag_manager.add_store(new_store)
        new_store.retriever.add_documents(
            [
                Document(
                    page_content="I like american cheese.", metadata={"source": "test1"}
                ),
                Document(
                    page_content="I like hamburgers.", metadata={"source": "test2"}
                ),
                Document(
                    page_content="I dont like liver.", metadata={"source": "test22"}
                ),
                Document(
                    page_content="Red is my favorite color.",
                    metadata={"source": "test3"},
                ),
                Document(
                    page_content="The sky is blue because reasons.",
                    metadata={"source": "test4"},
                ),
                Document(
                    page_content="Lizards are cold blooded.",
                    metadata={"source": "test5"},
                ),
            ]
        )
        llm = ChatOllama(
            model="mistral:latest", temperature=0.1, base_url=settings.ollama_host
        )
        # llm = ChatOpenAI(temperature=0.25)
        QUERY = "what are some cold blooded animals"
        # docs = new_store.query(query)
        # docs = new_store.query(query, k=2)
        docs = new_store.llm_query(llm, QUERY)
        # print(new_store.retriever.invoke(query))
        print(f"query: {QUERY}")
        for doc in docs:
            print(doc)
