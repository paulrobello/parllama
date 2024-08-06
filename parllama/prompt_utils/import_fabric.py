from __future__ import annotations

import hashlib
import os
import tempfile
import zipfile

import requests

from parllama.chat_manager import chat_manager
from parllama.chat_message import OllamaMessage
from parllama.chat_prompt import ChatPrompt
from parllama.par_event_system import ParEventSystemBase


class ImportFabricManager(ParEventSystemBase):
    """Import Fabric prompts from fabric repo."""

    def __init__(self) -> None:
        """Initialize the import manager."""
        super().__init__(id="import_fabric_manager")

        self.repo_zip_url = (
            "https://github.com/danielmiessler/fabric/archive/refs/heads/main.zip"
        )

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
                    prompt_content = ""
                    for line in f.readlines():
                        if line.upper().startswith(
                            "# INPUT"
                        ) or line.upper().startswith("INPUT:"):
                            break
                        prompt_content += line + "\n"
                    prompt_content = prompt_content.strip()
                    prompt: ChatPrompt = self.markdown_to_prompt(
                        pattern_name, prompt_content
                    )
                    chat_manager.add_prompt(prompt)
                    prompt.is_dirty = True
                    prompt.save()

    def markdown_to_prompt(self, pattern_name: str, prompt_content: str) -> ChatPrompt:
        """Convert markdown to ChatPrompt."""
        description = self.get_description(prompt_content)
        prompt = ChatPrompt(
            id=hashlib.md5(prompt_content.encode()).hexdigest(),
            name=pattern_name,
            description=description,
            messages=[OllamaMessage(role="system", content=prompt_content)],
            source="fabric",
        )
        return prompt

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

    def test_import(self) -> None:
        """Test importing fabric prompts."""
        with open(
            "d:/repos/parllama/fabric_samples/extract_wisdom/system.md",
            "rt",
            encoding="utf-8",
        ) as f:
            prompt_content = ""
            for line in f.readlines():
                if line.upper().startswith("# INPUT") or line.upper().startswith(
                    "INPUT:"
                ):
                    break
                prompt_content += line + "\n"
            prompt_content = prompt_content.strip()
            prompt: ChatPrompt = self.markdown_to_prompt(
                "extract_wisdom", prompt_content
            )
        chat_manager.add_prompt(prompt)
        prompt.is_dirty = True
        prompt.save()
        self.log_it("Prompt imported: extract_wisdom", notify=True)


import_fabric_manager = ImportFabricManager()
