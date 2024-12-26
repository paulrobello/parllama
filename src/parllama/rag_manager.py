"""RAG manager for Par Llama."""

from __future__ import annotations

import os
import time
import warnings
from typing import Any

import orjson as json
from dotenv import load_dotenv
from langchain.chains.retrieval_qa.base import RetrievalQA
from par_ai_core.llm_config import LlmConfig, LlmMode
from par_ai_core.llm_providers import LlmProvider
from textual.app import App

from parllama.models.rag_datasource import DataSourceFile, LoadSplitConfig
from parllama.models.rag_stores import (
    RagPipelineConfig,
    StoreBase,
    VectorStoreBase,
    VectorStoreChroma,
    VectorStoreConfig,
)
from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings

load_dotenv(os.path.expanduser("~/.parllama/.env"))


class RagManager(ParEventSystemBase):
    """RAG manager for Par Llama."""

    stores: list[StoreBase]
    _id_to_store: dict[str, StoreBase] = {}
    _vector_stores: list[VectorStoreBase] = []

    def __init__(self):
        """Initialize the data manager."""
        super().__init__(id="rag_manager")
        self._config_file = os.path.join(settings.data_dir, "rag_config.json")
        self.stores = []
        self._id_to_store = {}

    @property
    def vector_stores(self) -> list[VectorStoreBase]:
        """Return vector stores"""
        return self._vector_stores

    def set_app(self, app: App[Any] | None) -> None:
        """Set the app and load existing stores"""
        self.app = app  # pylint: disable=attribute-defined-outside-init
        self.load()

    def to_json(self) -> dict:
        """Return dict for use with json"""
        return {
            "id": self.id,
            "stores": [store.to_json() for store in self.stores],
        }

    def load(self) -> None:
        """Load the RAG configuration."""
        if not os.path.exists(self._config_file):
            return
        with open(self._config_file, encoding="utf-8") as fh:
            config = json.loads(fh.read())

        for store_config in config["stores"]:
            store_cls = StoreBase.get_class(store_config["class_name"])
            store = store_cls.from_json(store_config)
            self.add_store(store, False)

    def save(self) -> None:
        """Save the RAG configuration."""
        with open(self._config_file, "wb") as fh:
            fh.write(json.dumps(self.to_json(), str, json.OPT_INDENT_2))

    def add_store(self, store: StoreBase, save: bool = True) -> None:
        """Add store"""
        self.stores.append(store)
        self._id_to_store[store.id] = store
        if isinstance(store, VectorStoreBase):
            self._vector_stores.append(store)
        if save:
            self.save()

    def remove_store(self, store_id: str) -> None:
        """Remove store"""
        store = self._id_to_store.pop(store_id, None)
        if store:
            self.stores.remove(store)
            if isinstance(store, VectorStoreBase):
                self._vector_stores.remove(store)
            self.save()


rag_manager: RagManager = RagManager()

if __name__ == "__main__":
    # embeddings = HuggingFaceEmbeddings(
    #     # model_kwargs={"device": "cuda", "trust_remote_code": True},
    #     model_kwargs={"trust_remote_code": True},
    #     encode_kwargs={"normalize_embeddings": False},
    # )
    rag_manager.load()
    if len(rag_manager.vector_stores) == 0:
        rag_manager.add_store(
            VectorStoreChroma(
                name="Chroma",
                config=VectorStoreConfig(
                    location_type="Local",
                    location="chroma_db",
                    collection_name="remember",
                    embeddings_config=LlmConfig(
                        provider=LlmProvider.OLLAMA,
                        mode=LlmMode.EMBEDDINGS,
                        model_name="snowflake-arctic-embed:latest",
                        temperature=0,
                    ),
                    purge_on_start=True,
                ),
            )
        )

        # new_store = VectorStoreChroma(
        #     name="Chroma",
        #     config=VectorStoreConfig(
        #         location_type="Local",
        #         location="chroma_db",
        #         collection_name="remember",
        #         embeddings_config=LlmConfig(
        #             provider="OpenAI",
        #             mode="Embeddings",
        #             model_name="text-embedding-3-large",
        #         ),
        #         purge_on_start=True,
        #     ),
        # )

    new_store = rag_manager.vector_stores[0]

    new_store.config.purge_on_start = True

    num_documents = new_store.num_documents
    if num_documents == 0:
        print("loading data...")
        ds = DataSourceFile(
            source="../rag_docs/ai_adoption_framework_whitepaper.pdf",
            source_format="auto",
        )
        start_time = time.time()
        new_store.retriever.add_documents(
            ds.load_split(
                LoadSplitConfig(
                    embeddings=new_store.embeddings,
                    chunk_size=500,
                    chunk_overlap=100,
                    mode="token",
                )
            )
        )
        # new_store.retriever.add_documents(
        #     [
        #         Document(
        #             page_content="I like american cheese.", metadata={"source": "test1"}
        #         ),
        #         Document(
        #             page_content="I like hamburgers.", metadata={"source": "test2"}
        #         ),
        #         Document(
        #             page_content="I dont like liver.", metadata={"source": "test22"}
        #         ),
        #         Document(
        #             page_content="Red is my favorite color.",
        #             metadata={"source": "test3"},
        #         ),
        #         Document(
        #             page_content="The sky is blue because reasons.",
        #             metadata={"source": "test4"},
        #         ),
        #         Document(
        #             page_content="Lizards are cold blooded.",
        #             metadata={"source": "test5"},
        #         ),
        #     ]
        # )
        end_time = time.time()
        elapsed_time = end_time - start_time
        num_documents = new_store.num_documents
        print(f"Time taken to load data: {elapsed_time:.2f} seconds {(num_documents / elapsed_time):.2f} dps")

    print(f"Number of chunks: {num_documents}")
    # # llm = ChatOllama(model="llama3.1:8b", temperature=0, base_url=settings.ollama_host)
    # # llm = ChatOpenAI(temperature=0.25)
    # # QUERY = "what are some cold blooded animals"
    # # QUERY = "Summarize the document"
    QUERY = "what is 'Explainable AI'"
    # # docs = new_store.query(query)
    # # docs = new_store.query(query, k=2)
    # # docs = new_store.query_pipeline(
    # #     QUERY,
    # #     requested_retrievers={"LLM", "MMR", "SIM_THRESH"},
    # #     requested_filters={"REDUNDANT", "RERANK"},
    # #     llm=llm,
    # #     k=5,
    # #     rerank_llm=ChatOpenAI(model="gpt-4o", temperature=0.1),
    # # )
    # # print(new_store.retriever.invoke(query))
    #
    # # print(f"query: {QUERY}")
    # # print("---------")
    # # for doc in docs:
    # #     print(doc)
    # #     print("---------")
    #
    llm_config = LlmConfig(
        provider=LlmProvider.OLLAMA,
        mode=LlmMode.CHAT,
        model_name="llama3.1:8b",
        temperature=0,
    )
    chain = RetrievalQA.from_chain_type(
        llm=llm_config.build_chat_model(),
        retriever=rag_manager.vector_stores[0].rag_pipeline(
            RagPipelineConfig(
                requested_retrievers={"LLM", "MMR", "SIM_THRESH"},
                requested_filters={"REDUNDANT"},
                llm_config=llm_config,
            )
        ),
    )

    # # chain = RetrievalQA.from_chain_type(
    # #     llm=LlmConfig(
    # #         provider="OpenAI",
    # #         mode="Chat",
    # #         model_name="gpt-4o",
    # #         temperature=0,
    # #     ).build_chat_model(),
    # #     retriever=new_store.rag_pipeline(
    # #         RagPipelineConfig(
    # #             requested_retrievers={"LLM", "MMR", "SIM_THRESH"},
    # #             requested_filters={"REDUNDANT", "RERANK"},
    # #             llm_config=LlmConfig(
    # #                 provider="OpenAI",
    # #                 mode="Chat",
    # #                 model_name="gpt-4o",
    # #                 temperature=0,
    # #             ),
    # #             rerank_llm_config=LlmConfig(
    # #                 provider="OpenAI",
    # #                 mode="Chat",
    # #                 model_name="gpt-4o",
    # #                 temperature=0,
    # #             ),
    # #         )
    # #     ),
    # # )
    #
    # # chain = RetrievalQA.from_chain_type(
    # #     llm=ChatOpenAI(model="gpt-4o", temperature=0),
    # #     retriever=new_store.rag_pipeline(
    # #         requested_retrievers={"LLM", "MMR", "SIM_THRESH"},
    # #         requested_filters={"REDUNDANT", "RERANK"},
    # #         llm=ChatOpenAI(model="gpt-4o", temperature=0),
    # #         rerank_llm=ChatOpenAI(model="gpt-4o", temperature=0),
    # #     ),
    # # )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = chain.invoke({"query": QUERY})
    print("--------- RESULT -------------")
    print(result["result"])
