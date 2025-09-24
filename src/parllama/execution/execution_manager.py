"""Execution manager for handling templates and execution operations."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from pathlib import Path

import rich.repr
from textual.app import App

from parllama.execution.execution_result import ExecutionResult
from parllama.execution.execution_template import ExecutionTemplate
from parllama.execution.import_result import ImportResult
from parllama.secure_file_ops import SecureFileOperations, SecureFileOpsError


@rich.repr.auto
class ExecutionManager:
    """Manages execution templates and execution history."""

    def __init__(self, app: App) -> None:
        """Initialize the execution manager."""
        self.app = app
        self._templates: dict[str, ExecutionTemplate] = {}
        self._execution_history: list[ExecutionResult] = []
        self._templates_loaded = False
        self._history_loaded = False

        # Will be set when settings are available
        self.templates_file: Path | None = None
        self.history_file: Path | None = None
        self.secure_ops: SecureFileOperations | None = None

    def initialize_from_settings(self, settings) -> None:
        """Initialize file paths and secure operations from settings."""
        from parllama.settings_manager import settings as app_settings

        self.templates_file = app_settings.execution_templates_file
        self.history_file = app_settings.execution_history_file
        self.secure_ops = SecureFileOperations(
            max_file_size_mb=app_settings.max_json_size_mb,
            allowed_extensions=app_settings.allowed_json_extensions,
            validate_content=app_settings.validate_file_content,
            sanitize_filenames=app_settings.sanitize_filenames,
        )

    async def load_templates(self) -> None:
        """Load execution templates from storage."""
        if self._templates_loaded or not self.templates_file or not self.secure_ops:
            return

        try:
            if not self.templates_file.exists():
                # Create default templates on first run
                await self._create_default_templates()
                return

            templates_data = self.secure_ops.read_json_file(self.templates_file)
            self._templates.clear()

            for template_dict in templates_data.get("templates", []):
                try:
                    template = ExecutionTemplate.from_dict(template_dict)
                    self._templates[template.id] = template
                except Exception as e:  # pylint: disable=broad-exception-caught
                    # Log error but continue loading other templates
                    print(f"Error loading template: {e}")

            self._templates_loaded = True

        except SecureFileOpsError as e:
            print(f"Error loading execution templates: {e}")
            # Create default templates as fallback
            await self._create_default_templates()

    async def save_templates(self) -> None:
        """Save execution templates to storage."""
        if not self.templates_file or not self.secure_ops:
            return

        try:
            templates_data = {
                "templates": [template.to_dict() for template in self._templates.values()],
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
            }

            self.secure_ops.write_json_file(self.templates_file, templates_data, atomic=True)

        except SecureFileOpsError as e:
            print(f"Error saving execution templates: {e}")

    async def load_execution_history(self) -> None:
        """Load execution history from storage."""
        if self._history_loaded or not self.history_file or not self.secure_ops:
            return

        try:
            if not self.history_file.exists():
                self._execution_history = []
                self._history_loaded = True
                return

            history_data = self.secure_ops.read_json_file(self.history_file)
            self._execution_history.clear()

            for result_dict in history_data.get("history", [])[:100]:  # Keep last 100 executions
                try:
                    result = ExecutionResult.from_dict(result_dict)
                    self._execution_history.append(result)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    print(f"Error loading execution result: {e}")

            self._history_loaded = True

        except SecureFileOpsError as e:
            print(f"Error loading execution history: {e}")
            self._execution_history = []
            self._history_loaded = True

    async def save_execution_history(self) -> None:
        """Save execution history to storage."""
        if not self.history_file or not self.secure_ops:
            return

        try:
            # Keep only the last 100 executions
            recent_history = self._execution_history[-100:]

            history_data = {
                "history": [result.to_dict() for result in recent_history],
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
            }

            self.secure_ops.write_json_file(self.history_file, history_data, atomic=True)

            # Update internal history to match saved data
            self._execution_history = recent_history

        except SecureFileOpsError as e:
            print(f"Error saving execution history: {e}")

    async def _create_default_templates(self) -> None:
        """Create default execution templates."""
        default_templates = [
            ExecutionTemplate(
                name="Python Script",
                description="Execute Python code directly",
                command_template="python3 -c '{content}'",
                file_extensions=[".py"],
                timeout=30,
            ),
            ExecutionTemplate(
                name="Python File",
                description="Execute Python code from temporary file",
                command_template="python3 {{TEMP_FILE}}",
                file_extensions=[".py"],
                timeout=60,
            ),
            ExecutionTemplate(
                name="Node.js Script",
                description="Execute JavaScript/Node.js code directly",
                command_template="node -e '{content}'",
                file_extensions=[".js"],
                timeout=30,
            ),
            ExecutionTemplate(
                name="Node.js File",
                description="Execute JavaScript/Node.js code from file",
                command_template="node {{TEMP_FILE}}",
                file_extensions=[".js"],
                timeout=60,
            ),
            ExecutionTemplate(
                name="Bash Command",
                description="Execute shell commands",
                command_template="{content}",
                file_extensions=[".sh", ".bash"],
                timeout=30,
            ),
            ExecutionTemplate(
                name="Shell Script",
                description="Execute shell script from file",
                command_template="bash {{TEMP_FILE}}",
                file_extensions=[".sh", ".bash"],
                timeout=60,
            ),
        ]

        for template in default_templates:
            self._templates[template.id] = template

        await self.save_templates()
        self._templates_loaded = True

    # Template management methods
    def add_template(self, template: ExecutionTemplate) -> None:
        """Add a new execution template."""
        self._templates[template.id] = template
        # Save asynchronously without blocking
        asyncio.create_task(self.save_templates())

    def update_template(self, template: ExecutionTemplate) -> None:
        """Update an existing execution template."""
        if template.id in self._templates:
            template.last_updated = datetime.now()
            self._templates[template.id] = template
            asyncio.create_task(self.save_templates())

    def delete_template(self, template_id: str) -> bool:
        """Delete an execution template."""
        if template_id in self._templates:
            del self._templates[template_id]
            asyncio.create_task(self.save_templates())
            return True
        return False

    def get_template(self, template_id: str) -> ExecutionTemplate | None:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def get_all_templates(self) -> list[ExecutionTemplate]:
        """Get all execution templates."""
        return list(self._templates.values())

    def get_enabled_templates(self) -> list[ExecutionTemplate]:
        """Get all enabled execution templates."""
        return [template for template in self._templates.values() if template.enabled]

    def find_matching_templates(self, content: str, file_type: str | None = None) -> list[ExecutionTemplate]:
        """Find templates that match the given content."""
        matching = []
        for template in self.get_enabled_templates():
            if template.matches_content(content, file_type):
                matching.append(template)
        return matching

    # Execution history methods
    def add_execution_result(self, result: ExecutionResult) -> None:
        """Add an execution result to history."""
        self._execution_history.append(result)
        # Save asynchronously without blocking
        asyncio.create_task(self.save_execution_history())

    def get_execution_history(self, limit: int = 50) -> list[ExecutionResult]:
        """Get execution history with optional limit."""
        return self._execution_history[-limit:]

    def get_template_execution_history(self, template_id: str, limit: int = 20) -> list[ExecutionResult]:
        """Get execution history for a specific template."""
        template_history = [result for result in self._execution_history if result.template_id == template_id]
        return template_history[-limit:]

    def clear_execution_history(self) -> None:
        """Clear all execution history."""
        self._execution_history.clear()
        asyncio.create_task(self.save_execution_history())

    # Statistics and utility methods
    def get_template_stats(self) -> dict:
        """Get statistics about templates and executions."""
        total_templates = len(self._templates)
        enabled_templates = len(self.get_enabled_templates())
        total_executions = len(self._execution_history)
        successful_executions = len([r for r in self._execution_history if r.success])

        return {
            "total_templates": total_templates,
            "enabled_templates": enabled_templates,
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "success_rate": successful_executions / max(total_executions, 1) * 100,
        }

    def export_templates(self) -> dict:
        """Export all templates for sharing."""
        return {
            "templates": [template.to_dict() for template in self._templates.values()],
            "exported_at": datetime.now().isoformat(),
            "version": "1.0",
        }

    def import_templates(self, templates_data: dict, replace: bool = False) -> int:
        """Import templates from exported data."""
        if replace:
            self._templates.clear()

        imported_count = 0
        for template_dict in templates_data.get("templates", []):
            try:
                template = ExecutionTemplate.from_dict(template_dict)
                # Generate new ID if template already exists and not replacing
                if not replace and template.id in self._templates:
                    template.id = str(uuid.uuid4())

                self._templates[template.id] = template
                imported_count += 1
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Error importing template: {e}")

        if imported_count > 0:
            asyncio.create_task(self.save_templates())

        return imported_count

    async def import_templates_from_file(self, file_path: Path, replace: bool = False) -> ImportResult:
        """Import templates from a JSON file with comprehensive validation and conflict resolution."""
        if not self.secure_ops:
            return ImportResult(
                total_templates=0,
                imported_count=0,
                skipped_count=0,
                errors=["Secure operations not initialized"],
                warnings=[],
                success=False,
            )

        try:
            # Load and validate file
            templates_data = self.secure_ops.read_json_file(file_path)

            # Validate structure
            if not isinstance(templates_data, dict):
                return ImportResult(
                    total_templates=0,
                    imported_count=0,
                    skipped_count=0,
                    errors=["Invalid file format: expected JSON object"],
                    warnings=[],
                    success=False,
                )

            if "templates" not in templates_data:
                return ImportResult(
                    total_templates=0,
                    imported_count=0,
                    skipped_count=0,
                    errors=["Invalid file format: missing 'templates' key"],
                    warnings=[],
                    success=False,
                )

            templates_list = templates_data.get("templates", [])
            if not isinstance(templates_list, list):
                return ImportResult(
                    total_templates=0,
                    imported_count=0,
                    skipped_count=0,
                    errors=["Invalid file format: 'templates' must be an array"],
                    warnings=[],
                    success=False,
                )

            # Log import start
            if self.app and hasattr(self.app, "log"):
                self.app.log(f"Importing templates from: {file_path}")

            # Process templates
            return await self._process_template_import(templates_list, replace)

        except SecureFileOpsError as e:
            return ImportResult(
                total_templates=0,
                imported_count=0,
                skipped_count=0,
                errors=[f"File error: {e}"],
                warnings=[],
                success=False,
            )
        except Exception as e:
            return ImportResult(
                total_templates=0,
                imported_count=0,
                skipped_count=0,
                errors=[f"Unexpected error: {e}"],
                warnings=[],
                success=False,
            )

    async def _process_template_import(self, templates_list: list, replace: bool) -> ImportResult:
        """Process the actual template import with conflict resolution."""
        total_templates = len(templates_list)
        imported_count = 0
        skipped_count = 0
        errors = []
        warnings = []

        if replace:
            self._templates.clear()
            if self.app and hasattr(self.app, "log"):
                self.app.log("Cleared all existing templates for replacement")

        for i, template_dict in enumerate(templates_list):
            try:
                template = ExecutionTemplate.from_dict(template_dict)
                original_name = template.name

                # Handle ID conflicts
                if not replace and template.id in self._templates:
                    template.id = str(uuid.uuid4())
                    warnings.append(f"Template '{original_name}' assigned new ID due to conflict")

                # Handle name conflicts
                if self._is_name_taken(template.name):
                    new_name = self._generate_unique_template_name(template.name)
                    warnings.append(f"Template '{original_name}' renamed to '{new_name}' due to name conflict")
                    template.name = new_name

                self._templates[template.id] = template
                imported_count += 1

                # Log successful import
                if self.app and hasattr(self.app, "log"):
                    if template.name != original_name:
                        self.app.log(f"Template '{original_name}' imported as '{template.name}'")
                    else:
                        self.app.log(f"Template '{template.name}' imported successfully")

            except Exception as e:
                errors.append(f"Template {i + 1}: {e}")
                skipped_count += 1

        # Save templates if any were imported
        if imported_count > 0:
            try:
                await self.save_templates()
            except Exception as e:
                errors.append(f"Failed to save templates: {e}")

        # Log import completion
        if self.app and hasattr(self.app, "log"):
            self.app.log(f"Import completed: {imported_count} imported, {skipped_count} skipped, {len(errors)} errors")

        return ImportResult(
            total_templates=total_templates,
            imported_count=imported_count,
            skipped_count=skipped_count,
            errors=errors,
            warnings=warnings,
            success=len(errors) == 0 and imported_count > 0,
        )

    def _is_name_taken(self, name: str) -> bool:
        """Check if a template name is already in use."""
        return any(template.name == name for template in self._templates.values())

    def _generate_unique_template_name(self, desired_name: str) -> str:
        """Generate a unique template name if conflicts exist."""
        if not self._is_name_taken(desired_name):
            return desired_name

        counter = 2
        while True:
            candidate_name = f"{desired_name} ({counter})"
            if not self._is_name_taken(candidate_name):
                return candidate_name
            counter += 1

    def __len__(self) -> int:
        """Return number of templates."""
        return len(self._templates)

    def __contains__(self, template_id: str) -> bool:
        """Check if template exists."""
        return template_id in self._templates

    def __iter__(self):
        """Iterate over templates."""
        return iter(self._templates.values())


# Global execution manager instance - will be initialized by the app
execution_manager: ExecutionManager | None = None


def get_execution_manager() -> ExecutionManager:
    """Get the global execution manager instance."""
    if execution_manager is None:
        raise RuntimeError("Execution manager not initialized")
    return execution_manager
