"""Data manager for Par Llama."""

import os.path
import re
from datetime import datetime
from os import PathLike
from typing import Any, Dict, Generator, Iterator, List, Mapping, Union

import docker  # type: ignore
import docker.errors  # type: ignore
import docker.types  # type: ignore
import ollama
import requests
import simplejson as json
from bs4 import BeautifulSoup
from docker.models.containers import Container  # type: ignore

from parllama.docker_utils import start_docker_container
from parllama.models.ollama_data import (
    FullModel,
    ModelListPayload,
    ModelShowPayload,
    SiteModel,
    SiteModelData,
)
from parllama.models.settings_data import settings
from parllama.utils import output_to_dicts, run_cmd
from parllama.widgets.local_model_list_item import LocalModelListItem
from parllama.widgets.site_model_list_item import SiteModelListItem


class DataManager:
    """Data manager for Par Llama."""

    models: List[LocalModelListItem]
    site_models: List[SiteModelListItem]

    def __init__(self):
        """ "Initialize the data manager."""
        self.models = []
        self.site_models = []

    @staticmethod
    def _get_all_model_data() -> List[LocalModelListItem]:
        """Get all model data."""
        all_models: List[LocalModelListItem] = []
        res = ModelListPayload(**ollama.list())
        pattern = r"^(# Modelfile .*)\n(# To build.*)\n# (FROM .*\n)\n(FROM .*)\n(.*)$"
        replacement = r"\3\5"
        for model in res.models:
            res2 = ModelShowPayload(**ollama.show(model.name))

            res2.modelfile = re.sub(
                pattern, replacement, res2.modelfile, flags=re.MULTILINE | re.IGNORECASE
            )
            res3 = FullModel(**model.model_dump(), **res2.model_dump())
            all_models.append(LocalModelListItem(res3))
        return all_models

    def refresh_models(self) -> List[LocalModelListItem]:
        """Refresh all local model data."""
        self.models = self._get_all_model_data()
        return self.models

    @staticmethod
    def model_ps() -> List[dict[str, Any]]:
        """Get model ps."""
        ret = run_cmd(["ollama", "ps"])

        if not ret:
            return []
        return output_to_dicts(ret)

    @staticmethod
    def pull_model(model_name: str) -> Iterator[Dict[str, Any]]:
        """Pull a model."""
        return ollama.pull(model_name, stream=True)  # type: ignore

    @staticmethod
    def push_model(model_name: str) -> Iterator[Dict[str, Any]]:
        """Push a model."""
        return ollama.push(model_name, stream=True)  # type: ignore

    def delete_model(self, model_name: str) -> bool:
        """Delete a model."""
        ret = ollama.delete(model_name).get("status", False)
        # ret = True
        if not ret:
            return False

        for model in self.models:
            if model.model.name == model_name:
                # model.remove()
                self.models.remove(model)
                return True

        return False

    def list_cache_files(self) -> List[str]:
        """List cache files."""
        if not os.path.exists(settings.cache_dir):
            return []

        return [
            f.split("-")[1].split(".")[0]
            for f in os.listdir(settings.cache_dir)
            if os.path.isfile(os.path.join(settings.cache_dir, f))
            and f.lower().endswith(".json")
        ]

    def refresh_site_models(
        self, namespace: str, force: bool = True
    ) -> List[SiteModelListItem]:
        """Get list of all available models from Ollama.com."""

        settings.ensure_cache_folder()

        if not namespace:
            namespace = "models"
        namespace = os.path.basename(namespace)

        file_name = os.path.join(settings.cache_dir, f"site_models-{namespace}.json")
        if not force and os.path.exists(file_name):
            try:
                with open(file_name, "r", encoding="utf-8") as f:
                    ret: SiteModelData = SiteModelData(**json.load(f))
                    if ret.last_update and ret.last_update.timestamp() > (
                        ret.last_update.timestamp() - 60 * 60 * 24
                    ):
                        self.site_models = [SiteModelListItem(m) for m in ret.models]
                        return self.site_models
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Error: {e}")

        url: str = f"https://ollama.com/{namespace}"
        if namespace == "models":
            url += "?sort=popular"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(response.content.decode("utf-8"), "html.parser")
        models: List[SiteModel] = []

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
            models.append(model)
        if len(models) > 0 and not settings.no_save:
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(
                    SiteModelData(
                        models=models, last_update=datetime.now()
                    ).model_dump_json(indent=4)
                )
        self.site_models = [SiteModelListItem(m) for m in models]
        return self.site_models

    def create_model(
        self, model_name: str, model_path: str | PathLike
    ) -> Iterator[Dict[str, Any]]:
        """Create a new model."""
        return ollama.create(model=model_name, path=model_path, stream=True)  # type: ignore

    @staticmethod
    def copy_model(src_name: str, dst_name: str) -> Mapping[str, Any]:
        """Copy local model to new name"""
        return ollama.copy(source=src_name, destination=dst_name)

    @staticmethod
    def quantize_model(
        model_name: str, quantize_level: str = "q4_0"
    ) -> Union[str, Container, Generator[bytes, None, None]]:
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
