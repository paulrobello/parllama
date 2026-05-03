"""Execution coordinator extracted from ParLlamaApp.

Handles template matching, command execution, and result injection into chat
sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from parllama.execution.command_executor import CommandExecutor
from parllama.execution.execution_manager import ExecutionManager
from parllama.execution.template_matcher import TemplateMatcher
from parllama.messages.messages import (
    ChatMessage,
    ExecuteMessageRequested,
    ExecutionCompleted,
    ExecutionFailed,
)
from parllama.secure_file_ops import SecureFileOpsError
from parllama.settings_manager import settings

if TYPE_CHECKING:
    from parllama.app import ParLlamaApp


class ExecutionCoordinator:
    """Coordinates code execution requests: template matching, execution, and
    result delivery.

    This class was extracted from ParLlamaApp to decompose the God Object.
    The App retains the thin ``@on()`` handlers that Textual requires on the
    application class; those handlers delegate here.
    """

    def __init__(self, app: ParLlamaApp) -> None:
        """Initialize the coordinator.

        Args:
            app: Reference to the Textual application for message posting,
                 notifications, and logging.
        """
        self._app = app
        self.command_executor: CommandExecutor | None = None
        self.template_matcher: TemplateMatcher | None = None

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the execution system (command executor, template matcher,
        and global execution manager).

        Must be called once during application mount.
        """
        from parllama.execution import execution_manager as execution_manager_module

        # Create and initialize the global execution manager
        em = ExecutionManager(self._app)
        em.initialize_from_settings(settings)

        # Publish to the module-level global so other code that imports
        # ``execution_manager.execution_manager`` sees the instance.
        execution_manager_module.execution_manager = em

        # Initialize command executor and template matcher
        self.command_executor = CommandExecutor(settings)
        self.template_matcher = TemplateMatcher(settings)

        # Load templates and history
        await em.load_templates()
        await em.load_execution_history()

    # ------------------------------------------------------------------
    # Execution request handling
    # ------------------------------------------------------------------

    async def handle_execute_message_requested(self, event: ExecuteMessageRequested) -> None:
        """Process an execution request event.

        Finds matching templates, extracts executable content, and runs the
        command through the ``CommandExecutor``.

        Args:
            event: The execution request event containing content and metadata.
        """
        if not settings.execution_enabled:
            self._app.notify("Code execution is disabled", severity="warning")
            return

        try:
            # Find matching templates
            em = self._get_execution_manager()
            if em is None:
                self._app.notify("Execution system not initialized", severity="error")
                return

            assert self.template_matcher is not None  # initialized in initialize()
            assert self.command_executor is not None  # initialized in initialize()

            templates = em.get_enabled_templates()
            matching_templates = self.template_matcher.find_matching_templates(event.content, templates)

            if not matching_templates:
                self._app.notify("No execution templates match this content", severity="warning")
                return

            # Use the best matching template
            best_match = matching_templates[0]
            template = best_match["template"]

            # Extract the specific code to execute from applicable blocks
            content_to_execute = self._extract_executable_content(event, best_match)

            # Check if confirmation is required
            requires_confirmation, warnings = self.template_matcher.should_require_confirmation(
                content_to_execute, template
            )

            if requires_confirmation and settings.execution_require_confirmation:
                # For now, just show warnings and proceed - full confirmation dialog would be added later
                if warnings:
                    warning_text = "; ".join(warnings)
                    self._app.notify(f"Executing with warnings: {warning_text}", severity="warning")

            # Execute the template with the extracted code content
            result = await self.command_executor.execute_template(
                template=template,
                content=content_to_execute,
                message_id=event.message_id,
            )

            # Add to execution history
            if em:
                em.add_execution_result(result)

            # Post completion message
            self._app.post_message(
                ExecutionCompleted(message_id=event.message_id, result=result.to_dict(), add_to_chat=True)
            )

            # Notify success/failure
            if result.success:
                self._app.notify(f"Executed successfully: {template.name}", severity="information")
            else:
                self._app.notify(f"Execution failed: {result.error_message or 'Unknown error'}", severity="error")

        except (ValueError, SecureFileOpsError, OSError, RuntimeError) as e:
            import traceback

            error_details = f"{str(e)} - {traceback.format_exc()}"
            self._app.notify(f"Execution error: {str(e)}", severity="error")
            self._app.post_message(
                ExecutionFailed(message_id=event.message_id, template_id=event.template_id or "", error=error_details)
            )
        except Exception as e:
            import traceback

            error_details = f"{str(e)} - {traceback.format_exc()}"
            self._app.log_it(f"Unexpected execution error: {type(e).__name__}: {error_details}")
            self._app.notify(f"Execution error: {str(e)}", severity="error")
            self._app.post_message(
                ExecutionFailed(message_id=event.message_id, template_id=event.template_id or "", error=error_details)
            )

    # ------------------------------------------------------------------
    # Execution completion handling
    # ------------------------------------------------------------------

    def handle_execution_completed(self, event: ExecutionCompleted) -> None:
        """Add execution result to the current chat session.

        Args:
            event: The execution completed event containing the result.
        """
        if not event.add_to_chat:
            return

        try:
            from parllama.chat_message import ParllamaChatMessage
            from parllama.execution.execution_result import ExecutionResult

            result = ExecutionResult.from_dict(event.result)

            # Create a new assistant message with the execution result
            formatted_output = result.get_formatted_output()

            # Get the current session from the chat view
            chat_view = self._app.main_screen.chat_view
            if hasattr(chat_view, "session") and chat_view.session:
                execution_message = ParllamaChatMessage(role="assistant", content=formatted_output)

                chat_view.session.add_message(execution_message)
                self._app.post_message(
                    ChatMessage(parent_id=chat_view.session.id, message_id=execution_message.id, is_final=True)
                )
                chat_view.session.save()
                self._app.log_it(f"Execution result added to chat session: {chat_view.session.name}")

        except (ValueError, KeyError, AttributeError, OSError) as e:
            self._app.notify(f"Error adding execution result to chat: {str(e)}", severity="error")
        except Exception as e:
            self._app.log_it(f"Unexpected error adding execution result to chat: {type(e).__name__}: {e}")
            self._app.notify(f"Error adding execution result to chat: {str(e)}", severity="error")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_execution_manager(self) -> ExecutionManager | None:
        """Return the global execution manager, or None if not initialized."""
        from parllama.execution.execution_manager import execution_manager as em

        return em

    def _extract_executable_content(self, event: ExecuteMessageRequested, best_match: dict) -> str:
        """Extract the content to execute from the best matching template result.

        Args:
            event: The original execution request event.
            best_match: The best template match dictionary from
                ``TemplateMatcher.find_matching_templates``.

        Returns:
            The content string to pass to the command executor.
        """
        assert self.template_matcher is not None  # initialized in initialize()

        applicable_blocks = best_match.get("applicable_blocks", [])
        if applicable_blocks:
            # Use the first applicable code block
            code_block = applicable_blocks[0]
            self._app.notify(f"Executing {code_block['language']} code block", severity="information")
            return code_block["code"]

        # Fallback: use get_executable_content to extract code
        executable_parts = self.template_matcher.get_executable_content(event.content)
        if executable_parts:
            self._app.notify(f"Executing {executable_parts[0]['language']} code", severity="information")
            return executable_parts[0]["content"]

        self._app.notify("No code blocks found, executing entire content", severity="warning")
        return event.content
