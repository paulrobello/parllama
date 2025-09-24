"""Template matching logic for execution templates."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from parllama.execution.execution_template import ExecutionTemplate


class TemplateMatcher:
    """Matches content to appropriate execution templates."""

    def __init__(self) -> None:
        """Initialize the template matcher."""
        # Language detection patterns
        self.language_patterns = {
            "python": [
                r"\bdef\s+\w+\s*\(",
                r"\bclass\s+\w+\s*:",
                r"\bimport\s+\w+",
                r"\bfrom\s+\w+\s+import",
                r"\bprint\s*\(",
                r"#.*python",
                r"```python",
                r"```py",
            ],
            "javascript": [
                r"\bfunction\s+\w+\s*\(",
                r"\bconst\s+\w+\s*=",
                r"\blet\s+\w+\s*=",
                r"\bvar\s+\w+\s*=",
                r"\bconsole\.log\s*\(",
                r"//.*javascript",
                r"```javascript",
                r"```js",
            ],
            "bash": [
                r"#!/bin/bash",
                r"#!/bin/sh",
                r"\becho\s+",
                r"\bls\s+",
                r"\bcd\s+",
                r"\bmkdir\s+",
                r"\brm\s+",
                r"#.*bash",
                r"```bash",
                r"```sh",
            ],
            "sql": [
                r"\bSELECT\s+",
                r"\bINSERT\s+INTO\s+",
                r"\bUPDATE\s+",
                r"\bDELETE\s+FROM\s+",
                r"\bCREATE\s+TABLE\s+",
                r"```sql",
            ],
        }

        # Content type patterns
        self.content_patterns = {
            "code_block": r"```(\w+)?\n(.*?)```",
            "inline_code": r"`([^`]+)`",
            "shebang": r"^#!.*",
        }

    def detect_language(self, content: str) -> list[str]:
        """Detect programming languages in the content."""
        detected_languages = []
        content_lower = content.lower()

        for language, patterns in self.language_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content_lower, re.MULTILINE | re.IGNORECASE):
                    if language not in detected_languages:
                        detected_languages.append(language)
                    break

        return detected_languages

    def extract_code_blocks(self, content: str) -> list[dict]:
        """Extract code blocks from markdown content."""
        code_blocks = []

        # Find code blocks with language specifiers
        pattern = r"```(\w+)?\n(.*?)```"
        matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)

        for match in matches:
            language = match.group(1) or "text"
            code = match.group(2).strip()
            if code:  # Only add non-empty code blocks
                code_blocks.append(
                    {
                        "language": language.lower(),
                        "code": code,
                        "start": match.start(),
                        "end": match.end(),
                    }
                )

        return code_blocks

    def find_matching_templates(
        self,
        content: str,
        templates: list[ExecutionTemplate],
        file_type: str | None = None,
    ) -> list[dict]:
        """Find templates that match the given content."""
        matching_templates = []

        # First, try to detect languages and code blocks
        detected_languages = self.detect_language(content)
        code_blocks = self.extract_code_blocks(content)

        # Check each template for matches
        for template in templates:
            if not template.enabled:
                continue

            match_score = 0
            match_reasons = []

            # Check file extension matching
            if file_type and template.file_extensions:
                for ext in template.file_extensions:
                    if file_type.endswith(ext):
                        match_score += 10
                        match_reasons.append(f"File type matches {ext}")

            # Check language detection matching
            for language in detected_languages:
                template_languages = self._get_template_languages(template)
                if language in template_languages:
                    match_score += 8
                    match_reasons.append(f"Language detected: {language}")

            # Check code block language matching
            for block in code_blocks:
                template_languages = self._get_template_languages(template)
                if block["language"] in template_languages:
                    match_score += 6
                    match_reasons.append(f"Code block language: {block['language']}")

            # Check content patterns for template applicability
            if template.matches_content(content, file_type):
                match_score += 5
                match_reasons.append("Template pattern match")

            # Add template if it has any matching criteria
            if match_score > 0:
                matching_templates.append(
                    {
                        "template": template,
                        "score": match_score,
                        "reasons": match_reasons,
                        "applicable_blocks": [
                            block
                            for block in code_blocks
                            if block["language"] in self._get_template_languages(template)
                        ],
                    }
                )

        # Sort by match score (highest first)
        matching_templates.sort(key=lambda x: x["score"], reverse=True)

        return matching_templates

    def _get_template_languages(self, template: ExecutionTemplate) -> list[str]:
        """Get languages that a template can handle."""
        languages = []

        # Map file extensions to languages
        extension_map = {
            ".py": ["python", "py"],
            ".js": ["javascript", "js"],
            ".sh": ["bash", "sh", "shell"],
            ".bash": ["bash", "sh", "shell"],
            ".sql": ["sql"],
        }

        for ext in template.file_extensions or []:
            if ext in extension_map:
                languages.extend(extension_map[ext])

        # Also check template name for language hints
        template_name_lower = template.name.lower()
        for language in ["python", "javascript", "bash", "sql", "node"]:
            if language in template_name_lower:
                languages.append(language)

        return languages

    def get_best_template_for_content(
        self,
        content: str,
        templates: list[ExecutionTemplate],
        file_type: str | None = None,
    ) -> ExecutionTemplate | None:
        """Get the best matching template for the given content."""
        matches = self.find_matching_templates(content, templates, file_type)
        return matches[0]["template"] if matches else None

    def get_executable_content(self, content: str) -> list[dict]:
        """Extract executable content from mixed text/code."""
        executable_parts = []

        # Extract code blocks
        code_blocks = self.extract_code_blocks(content)
        for block in code_blocks:
            if block["language"] != "text":  # Skip plain text blocks
                executable_parts.append(
                    {
                        "type": "code_block",
                        "language": block["language"],
                        "content": block["code"],
                        "start": block["start"],
                        "end": block["end"],
                    }
                )

        # If no code blocks found, treat entire content as potentially executable
        if not executable_parts:
            detected_languages = self.detect_language(content)
            if detected_languages:
                executable_parts.append(
                    {
                        "type": "full_content",
                        "language": detected_languages[0],  # Use first detected language
                        "content": content,
                        "start": 0,
                        "end": len(content),
                    }
                )

        return executable_parts

    def should_require_confirmation(
        self,
        content: str,
        template: ExecutionTemplate,
    ) -> tuple[bool, list[str]]:
        """Determine if execution should require user confirmation."""
        warnings = []

        # Always require confirmation by default
        requires_confirmation = True

        # Check for potentially dangerous patterns
        dangerous_patterns = [
            (r"\brm\s+-rf", "File deletion command"),
            (r"\bdel\s+/", "Windows file deletion"),
            (r"\bformat\s+", "Format command"),
            (r"\bmkfs", "Filesystem creation"),
            (r"\bdd\s+if=", "Direct disk access"),
            (r">\s*/dev/", "Device file access"),
            (r"\bsudo\s+", "Privilege escalation"),
            (r"\bsu\s+", "User switching"),
            (r"__import__\s*\(\s*['\"]os['\"]", "OS module import"),
            (r"\bexec\s*\(", "Dynamic code execution"),
            (r"\beval\s*\(", "Expression evaluation"),
            (r"\bopen\s*\(.*['\"][wr]", "File write operations"),
        ]

        content_lower = content.lower()
        for pattern, description in dangerous_patterns:
            if re.search(pattern, content_lower):
                warnings.append(f"Potentially dangerous: {description}")

        # Check for network operations
        network_patterns = [
            (r"\burllib", "Network requests"),
            (r"\brequests\.", "HTTP requests"),
            (r"\bsocket\.", "Socket operations"),
            (r"\bhttpx\.", "HTTP requests"),
            (r"fetch\s*\(", "Network fetch"),
        ]

        for pattern, description in network_patterns:
            if re.search(pattern, content_lower):
                warnings.append(f"Network operation detected: {description}")

        return requires_confirmation, warnings
