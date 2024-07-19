"""Data manager for Par Llama."""
from __future__ import annotations

import os.path
import re
import shutil
from collections.abc import Generator
from collections.abc import Iterator
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from typing import Literal

import docker.errors  # type: ignore
import docker.types  # type: ignore
import httpx
import requests
import simplejson as json
from bs4 import BeautifulSoup
from docker.models.containers import Container  # type: ignore

from parllama.docker_utils import start_docker_container
from parllama.models.ollama_data import FullModel
from parllama.models.ollama_data import ModelListPayload
from parllama.models.ollama_data import ModelShowPayload
from parllama.models.ollama_data import SiteModel
from parllama.models.ollama_data import SiteModelData
from parllama.models.ollama_ps import OllamaPsResponse
from parllama.models.settings_data import settings
from parllama.utils import output_to_dicts
from parllama.utils import run_cmd
from parllama.widgets.local_model_list_item import LocalModelListItem
from parllama.widgets.site_model_list_item import SiteModelListItem


def api_model_ps() -> OllamaPsResponse:
    """Get model ps."""
    # fetch data from self.ollama_host as json
    res = httpx.get(f"{settings.ollama_host}/api/ps")
    if res.status_code != 200:
        return OllamaPsResponse()
    try:
        ret = OllamaPsResponse(**res.json())
        return ret
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error: {e}")
        print(res.text)
        return OllamaPsResponse()


class DataManager:
    """Data manager for Par Llama."""

    ollama_site_categories: list[str] = ["popular", "featured", "newest"]
    models: list[LocalModelListItem]
    site_models: list[SiteModelListItem]
    ollama_bin: str | None

    def __init__(self):
        """ "Initialize the data manager."""
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
        ret = run_cmd([self.ollama_bin, "ps"])

        if not ret:
            return api_ret
        local_ret = output_to_dicts(ret)
        if len(local_ret) > 0:
            api_ret.processor = local_ret[0]["processor"]
        return api_ret

    def get_model_by_name(self, name: str) -> FullModel | None:
        """Get a model by name."""
        for model in self.models:
            if model.model.name == name:
                return model.model
        return None

    @staticmethod
    def enrich_model_details(model: FullModel) -> None:
        """Enrich model details."""
        pattern = r"^(# Modelfile .*)\n(# To build.*)\n# (FROM .*\n)\n(FROM .*)\n(.*)$"
        replacement = r"\3\5"
        model_data = settings.ollama_client.show(model.name)
        msp = ModelShowPayload(**model_data)
        msp.modelfile = re.sub(
            pattern, replacement, msp.modelfile, flags=re.MULTILINE | re.IGNORECASE
        )
        model.parameters = msp.parameters
        model.template = msp.template
        model.modelfile = msp.modelfile
        model.model_info = msp.model_info

    @staticmethod
    def _get_all_model_data() -> list[LocalModelListItem]:
        """Get all model data."""
        all_models: list[LocalModelListItem] = []
        res = ModelListPayload(**settings.ollama_client.list())

        for model in res.models:
            res3 = FullModel(**model.model_dump())
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

    @staticmethod
    def pull_model(model_name: str) -> Iterator[dict[str, Any]]:
        """Pull a model."""
        return settings.ollama_client.pull(model_name, stream=True)  # type: ignore

    @staticmethod
    def push_model(model_name: str) -> Iterator[dict[str, Any]]:
        """Push a model."""
        return settings.ollama_client.push(model_name, stream=True)  # type: ignore

    def delete_model(self, model_name: str) -> bool:
        """Delete a model."""
        ret = settings.ollama_client.delete(model_name).get("status", False)
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
    def list_cache_files() -> list[str]:
        """List cache files."""
        if not os.path.exists(settings.cache_dir):
            return []

        return [
            f.split("-")[1].split(".")[0]
            for f in os.listdir(settings.cache_dir)
            if os.path.isfile(os.path.join(settings.cache_dir, f))
            and f.lower().endswith(".json")
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

        file_name = os.path.join(settings.cache_dir, f"site_models-{namespace}.json")
        if not force and os.path.exists(file_name):
            try:
                with open(file_name, encoding="utf-8") as f:
                    ret: SiteModelData = SiteModelData(**json.load(f))
                    if ret.last_update and ret.last_update.timestamp() > (
                        ret.last_update.timestamp() - 60 * 60 * 24
                    ):
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
            response = requests.get(
                url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10
            )
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

                pres = card.find_all(
                    "span", class_=["flex", "items-center"], recursive=True
                )
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
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(
                    SiteModelData(
                        models=models, last_update=datetime.now()
                    ).model_dump_json(indent=4)
                )
        self.site_models = [SiteModelListItem(m) for m in models]
        return self.site_models

    @staticmethod
    def create_model(
        model_name: str,
        model_code: str,
        quantize_level: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Create a new model."""
        return settings.ollama_client.create(
            model=model_name,
            modelfile=model_code,
            quantize=quantize_level,
            stream=True,
        )  # type: ignore

    @staticmethod
    def copy_model(src_name: str, dst_name: str) -> Mapping[str, Any]:
        """Copy local model to new name"""
        return settings.ollama_client.copy(source=src_name, destination=dst_name)

    @staticmethod
    def quantize_model(
        model_name: str, quantize_level: str = "q4_0"
    ) -> str | Container | Generator[bytes, None, None]:
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
            raise FileNotFoundError(
                f"Quantized model does not exist: {quantized_model_file}"
            )
        if isinstance(ret, str):
            return ret

        return ret.logs(stream=True)


dm: DataManager = DataManager()
