"""Data manager for Par Llama."""

from __future__ import annotations

import functools
import os.path
import re
import shutil
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import docker.errors  # type: ignore
import docker.types  # type: ignore
import httpx
import ollama
import orjson as json
import requests
from bs4 import BeautifulSoup
from docker.models.containers import Container  # type: ignore
from docker.types import CancellableStream
from httpx import Response
from ollama import ProgressResponse, StatusResponse
from par_ai_core.utils import run_cmd

from parllama.docker_utils import start_docker_container
from parllama.models.ollama_data import FullModel, ModelInfo, ModelShowPayload, SiteModel, SiteModelData
from parllama.models.ollama_ps import OllamaPsResponse
from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings
from parllama.widgets.local_model_list_item import LocalModelListItem
from parllama.widgets.site_model_list_item import SiteModelListItem

ps_pattern = re.compile(
    r"(?P<NAME>\S+)\s+(?P<ID>\S+)\s+(?P<SIZE>\d+\.\d+\s+\S+)\s+(?P<PROCESSOR>\d+%(?:/\d+%)?\s+\S+)\s+(?P<UNTIL>.+)"
)


def api_model_ps() -> OllamaPsResponse:
    """Get model ps."""
    # fetch data from self.ollama_host as json

    try:
        res: Response = httpx.get(f"{settings.ollama_host}/api/ps", timeout=5)
        if res.status_code != 200:
            return OllamaPsResponse()

        ret = OllamaPsResponse(**res.json())
        return ret
    except Exception:  # pylint: disable=broad-exception-caught
        # print(f"Error: {e}")
        # if res:
        #     print(res.text)
        return OllamaPsResponse()


class OllamaDataManager(ParEventSystemBase):
    """Data manager for Par Llama."""

    ollama_site_categories: list[str] = ["popular", "featured", "newest"]
    models: list[LocalModelListItem]
    site_models: list[SiteModelListItem]
    ollama_bin: str | None

    def __init__(self):
        """Initialize the data manager."""
        super().__init__(id="data_manager")

        self.models = []
        self.site_models = []
        # get location of ollama binary in path
        ollama_bin = shutil.which("ollama") or shutil.which("ollama.exe")
        # if not ollama_bin:
        #     raise FileNotFoundError("Could not find ollama binary in path")

        self.ollama_bin = str(ollama_bin) if ollama_bin is not None else None

    def model_ps(self) -> OllamaPsResponse:
        """Get model ps."""
        api_ret = api_model_ps()
        if not self.ollama_bin:
            return api_ret
        ret: str | None = run_cmd([self.ollama_bin, "ps"])

        if not ret:
            return api_ret
        matches = list(ps_pattern.finditer(ret))

        if len(matches) > 0:
            api_ret.processor = matches[0].group("PROCESSOR")
        return api_ret

    def get_model_by_name(self, name: str) -> FullModel | None:
        """Get a model by name."""
        for model in self.models:
            if model.model.name == name:
                return model.model
        return None

    def enrich_model_details(self, model: FullModel) -> None:
        """Enrich model details."""
        pattern = r"^(# Modelfile .*)\n(# To build.*)\n# (FROM .*\n)\n(FROM .*)\n(.*)$"
        replacement = r"\3\5"
        mfn = re.sub(r"[^\w_]", "", model.name)
        cache_file = Path(settings.ollama_cache_dir) / f"model_details-{mfn}.json"

        model_data: Mapping[str, Any] | None = None
        if cache_file.exists():
            try:
                model_data = json.loads(cache_file.read_bytes())
                if not isinstance(model_data, dict):
                    raise ValueError("Bad data")
                ModelShowPayload(**model_data)
            except Exception as _:
                cache_file.unlink()
                model_data = None
        if not model_data:
            model_data = ollama.Client(host=settings.ollama_host).show(model.name).model_dump()
            cache_file.write_bytes(json.dumps(model_data, str, json.OPT_INDENT_2))
        if "modelinfo" in model_data:
            model_data["modelinfo"] = ModelInfo(**model_data["modelinfo"])
        msp = ModelShowPayload(**model_data)
        msp.modelfile = re.sub(pattern, replacement, msp.modelfile, flags=re.MULTILINE | re.IGNORECASE)
        model.parameters = msp.parameters
        model.template = msp.template
        model.modelfile = msp.modelfile
        model.modelinfo = msp.modelinfo
        model.license = msp.license

    @staticmethod
    def _get_all_model_data() -> list[LocalModelListItem]:
        """Get all model data."""
        all_models: list[LocalModelListItem] = []
        res = ollama.Client(host=settings.ollama_host).list()

        for model in res.models:
            if not model.model:
                continue
            res3 = FullModel(**model.model_dump(), name=model.model)
            all_models.append(LocalModelListItem(res3))
            # break
        return all_models

    def refresh_models(self) -> list[LocalModelListItem]:
        """Refresh all local model data."""
        self.models = self._get_all_model_data()
        return self.models

    def get_model_select_options(self) -> list[tuple[str, str]]:
        """Get select options."""
        return [(model.model.name, model.model.name) for model in self.models]

    def get_model_names(self) -> list[str]:
        """Return list of model names"""
        return [model.model.name for model in self.models]

    @staticmethod
    def pull_model(model_name: str) -> Iterator[ProgressResponse]:
        """Pull a model."""
        return ollama.Client(host=settings.ollama_host).pull(model_name, stream=True)  # type: ignore

    @staticmethod
    def push_model(model_name: str) -> Iterator[ProgressResponse]:
        """Push a model."""
        return ollama.Client(host=settings.ollama_host).push(model_name, stream=True)  # type: ignore

    def delete_model(self, model_name: str) -> bool:
        """Delete a model."""
        ret = ollama.Client(host=settings.ollama_host).delete(model_name).status or False
        # ret = True
        if not ret:
            return False

        for model in self.models:
            if model.model.name == model_name:
                # model.remove()
                self.models.remove(model)
                return True

        return False

    @staticmethod
    def list_site_cache_files() -> list[str]:
        """List cache files."""
        if not os.path.exists(settings.ollama_cache_dir):
            return []

        return [
            f.split("-")[1].split(".")[0]
            for f in os.listdir(settings.ollama_cache_dir)
            if os.path.isfile(os.path.join(settings.ollama_cache_dir, f))
            and f.lower().endswith(".json")
            and f.lower().startswith("site_models-")
        ]

    # pylint: disable=too-many-branches
    def refresh_site_models(
        self,
        namespace: str,
        category: Literal["popular", "featured", "newest"] | None = None,
        force: bool = True,
    ) -> list[SiteModelListItem]:
        """Get list of all available models from Ollama.com."""

        settings.ensure_cache_folder()

        if not namespace:
            namespace = "library"
        namespace = os.path.basename(namespace)

        file_name = Path(settings.ollama_cache_dir) / f"site_models-{namespace}.json"

        if not force and file_name.exists():
            try:
                ret: SiteModelData = SiteModelData(**json.loads(file_name.read_bytes()))
                if ret.last_update and ret.last_update.timestamp() > (ret.last_update.timestamp() - 60 * 60 * 24):
                    self.site_models = [SiteModelListItem(m) for m in ret.models]
                    return self.site_models
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Error: {e}")

        url_base: str = f"https://ollama.com/{namespace}"
        models: list[SiteModel] = []

        for cat in self.ollama_site_categories:
            if category and category != cat:
                continue
            url = url_base
            if namespace == "models":
                url += f"?sort={cat}"
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(response.content.decode("utf-8"), "html.parser")
            for card in soup.find_all("li", class_="items-baseline"):
                meta_data = {
                    "name": card.find("h2").text.strip(),
                    "description": card.find("p").text.strip(),
                    "model_url": card.find("a")["href"],
                    "url": f'{url}{card.find("a")["href"]}',
                    "num_pulls": "",
                    "num_tags": "",
                    "updated": "",
                }

                pres = card.find_all("span", class_=["flex", "items-center"], recursive=True)
                pres = [p.text.strip() for p in pres]
                pres = [p for p in pres if p]

                for p in pres:
                    if "Pulls" in p:
                        meta_data["num_pulls"] = p.split("\n")[0].strip()
                    if "Tags" in p:
                        meta_data["num_tags"] = p.split("\xa0")[0].strip()
                    if "Updated" in p:
                        meta_data["updated"] = p.split("\xa0")[-1].strip()
                # tags = []
                tags = card.find_all("span", class_=["text-blue-600"], recursive=True)
                tags = [p.text.strip() for p in tags]
                tags = [p for p in tags if p]
                meta_data["tags"] = tags

                model = SiteModel(**meta_data)
                # print(model.model_dump_json(indent=4))
                found = False
                for m in models:
                    if m.name == model.name:
                        found = True
                        break
                if not found:
                    models.append(model)

            if namespace != "models":
                break

        if len(models) > 0 and not settings.no_save:
            file_name.write_bytes(
                json.dumps(
                    SiteModelData(models=models, last_update=datetime.now(UTC)).model_dump(),
                    str,
                    json.OPT_INDENT_2,
                )
            )
        self.site_models = [SiteModelListItem(m) for m in models]
        return self.site_models

    @staticmethod
    def create_model(
        model_name: str,
        model_code: str,
        quantize_level: str | None = None,
    ) -> Iterator[ProgressResponse]:
        """Create a new model."""
        return ollama.Client(host=settings.ollama_host).create(
            model=model_name,
            modelfile=model_code,
            quantize=quantize_level,
            stream=True,
        )  # type: ignore

    @staticmethod
    def copy_model(src_name: str, dst_name: str) -> StatusResponse:
        """Copy local model to new name"""
        return ollama.Client(host=settings.ollama_host).copy(source=src_name, destination=dst_name)

    @staticmethod
    def quantize_model(model_name: str, quantize_level: str = "q4_0") -> str | Container | CancellableStream:
        """
        Quantize a model

        Args:
            model_name (str): The name of the model to quantize
            quantize_level (str): The quantization level to use. Defaults to "q4_0"

        Returns:
            bool: True if successful, False otherwise
        """
        model_name = os.path.basename(model_name)
        model_folder = os.path.join(settings.data_dir, "quantize_workspace", model_name)
        if not os.path.exists(model_folder):
            raise FileNotFoundError(f"Model folder does not exist: {model_folder}")
        quantized_model_file = os.path.join(model_folder, f"{quantize_level}.bin")
        if os.path.exists(quantized_model_file):
            os.unlink(quantized_model_file)

        # docker run --rm -v .:/model ollama/quantize -q q4_0 /model
        ret = start_docker_container(
            image="ollama/quantize",
            container_name="parllamaQtz",
            command=f"-q {quantize_level} /model",
            network_name="parllama-network",
            mounts=[
                docker.types.Mount(
                    target="/model",
                    source=model_folder,
                    type="bind",
                )
            ],
            background=False,
        )
        if isinstance(ret, Exception):
            raise ret

        if not os.path.exists(quantized_model_file):
            raise FileNotFoundError(f"Quantized model does not exist: {quantized_model_file}")
        if isinstance(ret, str):
            return ret

        return ret.logs(stream=True)

    @functools.cached_property
    def ollama_client(self) -> ollama.Client:
        """Get the ollama client."""
        return ollama.Client(host=settings.ollama_host)

    @functools.cached_property
    def ollama_aclient(self) -> ollama.AsyncClient:
        """Get the async ollama client."""
        return ollama.AsyncClient(host=settings.ollama_host)

    def get_model_context_length(self, model_name: str) -> int:
        """Get the context length of a model."""
        model: FullModel | None = self.get_model_by_name(model_name)
        if not model:
            self.log_it("Model not found: " + model_name)
            return 2048
        if not model.modelinfo:
            self.log_it("Model info not loaded: " + model_name)
            self.enrich_model_details(model)
            if not model.modelinfo:
                self.log_it("Model load failed: " + model_name)
                return 2048
        return model.num_ctx()


ollama_dm: OllamaDataManager = OllamaDataManager()
