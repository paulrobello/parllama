from __future__ import annotations

import hashlib
import os
import tempfile
import zipfile

import requests

from parllama.chat_manager import chat_manager
from parllama.chat_message import OllamaMessage
from parllama.chat_prompt import ChatPrompt


class ImportFabric:
    """Import Fabric prompts from fabric repo."""

    def __init__(self) -> None:
        """Initialize the object with default values."""
        self.repo_zip_url = (
            "https://github.com/danielmiessler/fabric/archive/refs/heads/main.zip"
        )
        # self.config_directory = os.path.expanduser("~/.config/fabric")
        # self.pattern_directory = os.path.join(
        #     self.config_directory, "patterns")
        # os.makedirs(self.pattern_directory, exist_ok=True)
        # print("Updating patterns...")
        self.import_patterns()  # Start the update process immediately

    def import_patterns(self) -> None:
        """Update the patterns by downloading the zip from GitHub and extracting it."""
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "repo.zip")
            self.download_zip(self.repo_zip_url, zip_path)
            extracted_folder_path = self.extract_zip(zip_path, temp_dir)
            # The patterns folder will be inside "fabric-main" after extraction
            patterns_source_path = os.path.join(
                extracted_folder_path, "fabric-main", "patterns"
            )
            if not os.path.exists(patterns_source_path):
                raise FileNotFoundError(
                    "Patterns folder not found in the downloaded zip."
                )
            # list all folder in patterns_source_path
            pattern_folder_list = os.listdir(patterns_source_path)
            for pattern_name in pattern_folder_list:
                src_prompt_path = os.path.join(
                    patterns_source_path, pattern_name, "system.md"
                )
                if not os.path.exists(src_prompt_path):
                    continue
                with open(src_prompt_path, "rt", encoding="utf-8") as f:
                    prompt_content = f.read()
                    description = self.get_description(prompt_content)
                    prompt = ChatPrompt(
                        id=hashlib.md5(prompt_content.encode()).hexdigest(),
                        name=pattern_name,
                        description=description,
                        messages=[OllamaMessage(role="system", content=prompt_content)],
                    )
                    chat_manager.add_prompt(prompt)

    @staticmethod
    def get_description(prompt_data: str) -> str:
        """Extract description from prompt data."""
        started = False
        for line in prompt_data.split("\n"):
            line = line.strip()
            if line.startswith("# IDENTITY and PURPOSE"):
                started = True
                continue
            if not started or not line:
                continue
            return line
        return ""

    @staticmethod
    def download_zip(url: str, save_path: str) -> None:
        """Download the zip file from the specified URL."""
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Check if the download was successful
        with open(save_path, "wb") as f:
            f.write(response.content)

    @staticmethod
    def extract_zip(zip_path: str, extract_to: str) -> str:
        """Extract the zip file to the specified directory."""
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_to)
        print("Extracted zip file successfully.")
        return extract_to  # Return the path to the extracted contents
