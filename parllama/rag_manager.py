"""RAG manager for Par Llama."""

from __future__ import annotations

import os
import time
import warnings

import simplejson as json
from dotenv import load_dotenv
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain_ollama import ChatOllama

from parllama.llm_config import LlmConfig
from parllama.models.rag import (
    StoreBase,
    VectorStoreChroma,
    DataSourceFile,
    LoadSplitConfig,
    RagPipelineConfig,
    VectorStoreConfig,
)
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
    # if len(rag_manager.stores) == 0:
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

    # embeddings = HuggingFaceEmbeddings(
    #     # model_kwargs={"device": "cuda", "trust_remote_code": True},
    #     model_kwargs={"trust_remote_code": True},
    #     encode_kwargs={"normalize_embeddings": False},
    # )

    # embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    new_store = VectorStoreChroma(
        name="Chroma",
        config=VectorStoreConfig(
            collection_name="remember",
            embeddings_config=LlmConfig(
                provider="Ollama",
                mode="Embeddings",
                model_name="snowflake-arctic-embed:latest",
            ),
            purge_on_start=True,
        ),
    )
    rag_manager.add_store(new_store)
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
        print(
            f"Time taken to load data: {elapsed_time:.2f} seconds {(num_documents / elapsed_time):.2f} dps"
        )

    print(f"Number of chunks: {num_documents}")
    llm = ChatOllama(model="llama3.1:8b", temperature=0, base_url=settings.ollama_host)
    # llm = ChatOpenAI(temperature=0.25)
    # QUERY = "what are some cold blooded animals"
    # QUERY = "Summarize the document"
    QUERY = "what is 'Explainable AI'"
    # docs = new_store.query(query)
    # docs = new_store.query(query, k=2)
    # docs = new_store.query_pipeline(
    #     QUERY,
    #     requested_retrievers={"LLM", "MMR", "SIM_THRESH"},
    #     requested_filters={"REDUNDANT", "RERANK"},
    #     llm=llm,
    #     k=5,
    #     rerank_llm=ChatOpenAI(model="gpt-4o", temperature=0.1),
    # )
    # print(new_store.retriever.invoke(query))

    # print(f"query: {QUERY}")
    # print("---------")
    # for doc in docs:
    #     print(doc)
    #     print("---------")

    chain = RetrievalQA.from_chain_type(
        llm=LlmConfig(
            provider="Ollama",
            mode="Base",
            model_name="llama3.1:8b",
            temperature=0,
        ).build_llm_model(),
        retriever=new_store.rag_pipeline(
            RagPipelineConfig(
                requested_retrievers={"LLM", "MMR", "SIM_THRESH"},
                requested_filters={"REDUNDANT"},
                llm_config=LlmConfig(
                    provider="Ollama",
                    mode="Chat",
                    model_name="llama3.1:8b",
                    temperature=0,
                ),
            )
        ),
    )
    # chain = RetrievalQA.from_chain_type(
    #     llm=ChatOpenAI(model="gpt-4o", temperature=0),
    #     retriever=new_store.rag_pipeline(
    #         requested_retrievers={"LLM", "MMR", "SIM_THRESH"},
    #         requested_filters={"REDUNDANT", "RERANK"},
    #         llm=ChatOpenAI(model="gpt-4o", temperature=0),
    #         rerank_llm=ChatOpenAI(model="gpt-4o", temperature=0),
    #     ),
    # )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = chain.invoke({"query": QUERY})
    print("--------- RESULT -------------")

    print(result["result"])
