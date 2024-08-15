"""RAG Pipeline Utils"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Literal
from typing import Optional
from typing import Set


from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers import MergerRetriever
from langchain.retrievers import MultiQueryRetriever
from langchain.retrievers.document_compressors import DocumentCompressorPipeline
from langchain.retrievers.document_compressors import LLMListwiseRerank
from langchain_community.document_transformers import EmbeddingsRedundantFilter
from langchain_community.document_transformers import LongContextReorder
from langchain_core._api import LangChainDeprecationWarning
from langchain_core.documents import BaseDocumentCompressor
from langchain_core.documents import BaseDocumentTransformer
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import PromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore

from parllama.llm_config import LlmConfig
from parllama.passthrough_document_transformer import PassthroughDocumentTransformer

warnings.simplefilter("ignore", category=LangChainDeprecationWarning)

RetrieverType = Literal["LLM", "MMR", "SIM", "SIM_THRESH"]
retriever_types: list[RetrieverType] = ["LLM", "MMR", "SIM", "SIM_THRESH"]

RetrieverFilters = Literal["REDUNDANT", "RERANK", "REORDER"]
retriever_filters: list[RetrieverFilters] = ["REDUNDANT", "RERANK", "REORDER"]


@dataclass()
class RagPipelineConfig:
    """Configuration for RagPipeline."""

    requested_retrievers: Set[RetrieverType]
    """Retrievers to combine documents from. At least one retriever must be requested."""
    requested_filters: Optional[Set[RetrieverFilters]] = None
    """Filters to apply to the retrieved documents. Can be None."""
    max_documents_to_return: int = 5
    """Maximum number of documents to return after merging and filtering."""
    llm_config: Optional[LlmConfig] = None
    """Used by LLM retriever."""
    rerank_llm_config: Optional[LlmConfig] = None
    """Used by RERANK filter."""
    rerank_llm_prompt: Optional[PromptTemplate] = None
    """Used by RERANK filter. Uses a default if not provided."""


def rag_pipeline(
    *,
    vector_store: VectorStore,
    embeddings: Optional[Embeddings] = None,
    config: RagPipelineConfig,
) -> BaseRetriever:
    """Create pipeline to retrieve and filter documents."""

    if len(config.requested_retrievers) == 0:
        raise ValueError("At least one retriever must be requested.")

    prompt = config.rerank_llm_prompt or PromptTemplate(
        input_variables=["question"],
        template="""You are an AI language model assistant.\n
        Your task is to generate 3 different versions of the given user\n
        question to retrieve relevant documents from a vector database.\n
        By generating multiple perspectives on the user question,\n
        your goal is to help the user overcome some of the limitations\n
        of distance-based similarity search. Provide these alternative\n
        questions each on their own line. Do not output blank lines.\n
        Original question: {question}""",
    )

    if config.requested_filters is None:
        config.requested_filters = set()

    retrievers: list[BaseRetriever] = []
    if "LLM" in config.requested_retrievers:
        if not config.llm_config:
            raise ValueError("LLM model config not provided.")
        retriever_from_llm = MultiQueryRetriever.from_llm(
            retriever=vector_store.as_retriever(),
            llm=config.llm_config.build_llm_model(),
            prompt=prompt,
            include_original=True,
        )
        retrievers.append(retriever_from_llm)

    if "SIM" in config.requested_retrievers:
        retriever_sim = vector_store.as_retriever(
            search_kwargs={"k": 5},
        )
        retrievers.append(retriever_sim)

    if "SIM_THRESH" in config.requested_retrievers:
        retriever_sim_thresh = vector_store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"k": 5, "score_threshold": 0.75},
        )
        retrievers.append(retriever_sim_thresh)

    if "MMR" in config.requested_retrievers:
        retriever_mmr = vector_store.as_retriever(
            search_type="mmr", search_kwargs={"k": 5}
        )
        retrievers.append(retriever_mmr)

    merger = MergerRetriever(retrievers=retrievers)

    filters: list[BaseDocumentTransformer | BaseDocumentCompressor] = []
    if "REDUNDANT" in config.requested_filters:
        if not embeddings:
            raise ValueError("REDUNDANT filter requested but embeddings not provided.")
        filter_redundant = EmbeddingsRedundantFilter(
            embeddings=embeddings, similarity_threshold=0.95
        )
        filters.append(filter_redundant)

    if "REORDER" in config.requested_filters:
        reordering = LongContextReorder()
        filters.append(reordering)

    if "RERANK" in config.requested_filters:
        if not config.rerank_llm_config:
            raise ValueError("Reranker LLM config not provided")
        reranker = LLMListwiseRerank.from_llm(
            llm=config.rerank_llm_config.build_chat_model(), top_n=5
        )
        filters.append(reranker)

    filters.append(
        PassthroughDocumentTransformer(max_documents=config.max_documents_to_return)
    )

    pipeline = DocumentCompressorPipeline(transformers=list(filters))
    return ContextualCompressionRetriever(
        base_retriever=merger,
        base_compressor=pipeline,
    )
