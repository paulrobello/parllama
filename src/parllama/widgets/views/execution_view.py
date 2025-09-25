"""Widget for managing execution templates."""

from __future__ import annotations

from functools import partial
from typing import cast

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.events import Show
from textual.screen import ScreenResultCallbackType
from textual.widgets import Button, Label, ListItem, ListView

from parllama.dialogs.yes_no_dialog import YesNoDialog
from parllama.execution.execution_manager import get_execution_manager
from parllama.execution.execution_template import ExecutionTemplate
from parllama.messages.messages import ExecutionCompleted, RegisterForUpdates


class ExecutionTemplateListItem(ListItem):
    """List item for execution template."""

    def __init__(self, template: ExecutionTemplate, **kwargs) -> None:
        """Initialize template list item."""
        super().__init__(**kwargs)
        self.template = template

    def compose(self) -> ComposeResult:
        """Compose the list item."""
        with Vertical():
            with Horizontal():
                yield Label(f"[bold]{self.template.name}[/bold]")
                if not self.template.enabled:
                    yield Label("[dim](disabled)[/dim]")

            yield Label(f"[dim]{self.template.description}[/dim]")

            command_preview = self.template.command_template
            if len(command_preview) > 60:
                command_preview = command_preview[:57] + "..."
            yield Label(f"[dim]Command: {command_preview}[/dim]")

            if self.template.file_extensions:
                extensions = ", ".join(self.template.file_extensions)
                yield Label(f"[dim]File types: {extensions}[/dim]")

            with Horizontal(classes="button_row"):
                yield Button("Edit", id="edit", variant="primary")
                yield Button("Delete", id="delete", variant="error")

    @on(Button.Pressed, "#edit")
    def edit_template(self) -> None:
        """Edit this template."""
        from parllama.dialogs.edit_execution_template_dialog import EditExecutionTemplateDialog

        self.app.push_screen(
            EditExecutionTemplateDialog(self.template),
            cast(ScreenResultCallbackType[ExecutionTemplate | None], self.on_template_edited),
        )

    def on_template_edited(self, template: ExecutionTemplate | None) -> None:
        """Handle template edit completion."""
        if template:
            try:
                execution_manager = get_execution_manager()
                execution_manager.update_template(template)
                # Find the ExecutionView in the hierarchy and refresh it
                try:
                    execution_view = self.screen.query_one(ExecutionView)
                    execution_view.app.call_later(execution_view.refresh_templates)
                except Exception:
                    pass  # Ignore if we can't find the ExecutionView
                self.notify(f"Template '{template.name}' updated")
            except Exception as e:
                self.notify(f"Error updating template: {e}", severity="error")

    @on(Button.Pressed, "#delete")
    def delete_template(self) -> None:
        """Delete this template."""
        self.app.push_screen(
            YesNoDialog("Confirm Delete", f"Delete execution template '{self.template.name}'?", yes_first=False),
            cast(ScreenResultCallbackType[bool], partial(self.confirm_delete, self.template.id)),
        )

    def confirm_delete(self, template_id: str, confirmed: bool) -> None:
        """Confirm template deletion."""
        if confirmed:
            execution_manager = get_execution_manager()
            execution_manager.delete_template(template_id)
            # Find the ExecutionView in the hierarchy and refresh it
            try:
                execution_view = self.screen.query_one(ExecutionView)
                execution_view.app.call_later(execution_view.refresh_templates)
            except Exception:
                pass  # Ignore if we can't find the ExecutionView
            self.notify("Template deleted")


class ExecutionView(Container):
    """Widget for managing execution templates."""

    DEFAULT_CSS = """
    ExecutionView {
        #toolbar {
            height: 3;
            background: $surface-darken-1;
            padding: 0 0 0 1;
            Button {
                margin-right: 1;
            }
        }

        #template_list {
            height: 1fr;
            border: solid $accent;
        }

        ExecutionTemplateListItem {
            height: auto;
            min-height: 7;
            padding: 1;
            border: solid $accent;
            Vertical {
                height: auto;
                min-height: 4;
                width: 1fr;
                margin: 0;
                Horizontal {
                    height: auto;
                }
            }
            .button_row {
                height: 3;
                width: auto;
                margin: 1 0 0 0;
                dock: right;
                align: right middle;
                Button {
                    margin: 0 1;
                }
            }
            Label {
                height: 1;
                margin: 0;
            }
        }
        #stats {
            height: 3;
            width: 1fr;
            background: $surface;
            padding: 0 0 0 1;
            align: left middle;
            Button {
                dock: right;
                margin-right: 1;
            }
        }
    }
    """

    def __init__(self, **kwargs) -> None:
        """Initialize the execution view."""
        super().__init__(**kwargs)
        self.template_list: ListView = ListView(id="template_list")

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""
        with Vertical():
            with Horizontal(id="toolbar"):
                yield Button("New Template", id="new_template", variant="primary")
                yield Button("Import Templates", id="import_templates")
                yield Button("Export Templates", id="export_templates")
                yield Button("Refresh", id="refresh")

            yield self.template_list

            with Horizontal(id="stats"):
                yield Label("", id="stats_label")
                yield Button("Reset Stats", id="reset_stats", variant="error", classes="small")

    async def on_mount(self) -> None:
        """Set up the view once the DOM is ready."""
        self.app.post_message(
            RegisterForUpdates(
                widget=self,
                event_names=[
                    "ExecutionTemplateAdded",
                    "ExecutionTemplateUpdated",
                    "ExecutionTemplateDeleted",
                    "ExecutionCompleted",
                ],
            )
        )
        await self.refresh_templates()

    def _on_show(self, event: Show) -> None:
        """Handle show event."""
        self.screen.sub_title = "Execution Templates"

    async def refresh_templates(self) -> None:
        """Refresh the template list."""
        try:
            execution_manager = get_execution_manager()
            await execution_manager.load_templates()

            # Clear existing items
            self.template_list.clear()

            # Add template items
            templates = execution_manager.get_all_templates()
            for template in templates:
                list_item = ExecutionTemplateListItem(template)
                self.template_list.append(list_item)

            # Update stats
            await self.update_stats()

        except Exception as e:
            self.notify(f"Error loading templates: {e}", severity="error")

    async def update_stats(self) -> None:
        """Update the statistics display."""
        try:
            execution_manager = get_execution_manager()
            stats = execution_manager.get_template_stats()

            stats_text = (
                f"Templates: {stats['total_templates']} "
                f"(Enabled: {stats['enabled_templates']}) | "
                f"Executions: {stats['total_executions']} "
                f"(Success: {stats['successful_executions']}, "
                f"Rate: {stats['success_rate']:.1f}%)"
            )

            stats_label = self.query_one("#stats_label", Label)
            stats_label.update(stats_text)

        except Exception:
            pass  # Ignore stats update errors

    def update_stats_sync(self) -> None:
        """Synchronous version of update_stats for use in callbacks."""
        try:
            execution_manager = get_execution_manager()
            stats = execution_manager.get_template_stats()

            stats_text = (
                f"Templates: {stats['total_templates']} "
                f"(Enabled: {stats['enabled_templates']}) | "
                f"Executions: {stats['total_executions']} "
                f"(Success: {stats['successful_executions']}, "
                f"Rate: {stats['success_rate']:.1f}%)"
            )

            stats_label = self.query_one("#stats_label", Label)
            stats_label.update(stats_text)

        except Exception:
            pass  # Ignore stats update errors

    @on(Button.Pressed, "#new_template")
    def create_new_template(self) -> None:
        """Create a new execution template."""
        # Create a basic template
        new_template = ExecutionTemplate(
            name="New Template",
            description="New execution template",
            command_template="echo 'Hello World'",
        )

        execution_manager = get_execution_manager()
        execution_manager.add_template(new_template)

        self.notify("New template created")
        # Refresh the list asynchronously
        self.app.call_later(self.refresh_templates)

    @on(Button.Pressed, "#import_templates")
    def import_templates(self) -> None:
        """Import execution templates."""
        self.import_templates_worker()

    @work(exclusive=True)
    async def import_templates_worker(self) -> None:
        """Worker method for importing templates."""
        try:
            from parllama.dialogs.import_options_dialog import ImportOptionsDialog
            from parllama.dialogs.import_results_dialog import ImportResultsDialog
            from parllama.dialogs.import_templates_dialog import ImportTemplatesDialog

            # Step 1: Show import options dialog (merge vs replace)
            replace = await self.app.push_screen_wait(ImportOptionsDialog())
            if replace is None:  # User cancelled
                return

            # Step 2: Show file browser dialog
            import_file = await ImportTemplatesDialog.get_import_file(self.app)
            if not import_file:  # User cancelled
                return

            # Step 3: Perform the import
            execution_manager = get_execution_manager()
            result = await execution_manager.import_templates_from_file(import_file, replace=replace)

            # Step 4: Show detailed results
            await self.app.push_screen_wait(ImportResultsDialog(result))

            # Step 5: Refresh template list and statistics if successful
            if result.success or result.imported_count > 0:
                self.app.call_later(self.refresh_templates)
                self.notify(f"Import completed: {result.summary}", severity="information")
            else:
                self.notify(f"Import failed: {result.summary}", severity="error")

        except Exception as e:
            self.notify(f"Import error: {e}", severity="error")
            if self.app and hasattr(self.app, "log"):
                self.app.log(f"Import error: {e}")

    @on(Button.Pressed, "#export_templates")
    def export_templates(self, event: Button.Pressed) -> None:
        """Export execution templates."""
        event.stop()
        try:
            from datetime import datetime

            from parllama.settings_manager import settings

            execution_manager = get_execution_manager()
            export_data = execution_manager.export_templates()

            # Create export filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_filename = f"parllama_execution_templates_{timestamp}.json"

            # Export to the data directory
            export_path = settings.data_dir / export_filename

            # Write the export file using secure operations
            if execution_manager.secure_ops:
                execution_manager.secure_ops.write_json_file(export_path, export_data, atomic=True)

                # Log the export location to the Logs tab
                from parllama.messages.messages import LogIt

                template_count = len(export_data.get("templates", []))
                self.notify(f"Exported {template_count} templates", severity="information")
                self.notify(f"To: {export_path}", severity="information")
                self.app.post_message(LogIt(f"Execution templates exported to: {export_path}"))
                # Switch to Logs tab so user can see the export path (has weird issue where tab changes back immediately)
                # self.app.post_message(ChangeTab(tab="Logs"))
            else:
                self.notify("Export failed: Secure operations not available", severity="error")

        except Exception as e:
            self.notify(f"Export error: {e}", severity="error")

    @on(Button.Pressed, "#refresh")
    def refresh_button_pressed(self) -> None:
        """Handle refresh button press."""
        self.app.call_later(self.refresh_templates)

    @on(ExecutionCompleted)
    def on_execution_completed(self, event: ExecutionCompleted) -> None:
        """Handle execution completion - refresh stats to show updated execution counts."""
        event.stop()
        self.update_stats_sync()

    @on(Button.Pressed, "#reset_stats")
    def reset_stats_button_pressed(self) -> None:
        """Handle reset stats button press."""
        self.app.push_screen(
            YesNoDialog("Reset Statistics", "Clear all execution history and statistics?", yes_first=False),
            cast(ScreenResultCallbackType[bool], self.confirm_reset_stats),
        )

    def confirm_reset_stats(self, confirmed: bool | None) -> None:
        """Confirm stats reset."""
        if confirmed:
            try:
                execution_manager = get_execution_manager()
                execution_manager.clear_execution_history()
                # Update stats immediately
                self.update_stats_sync()
                self.notify("Execution statistics reset", severity="information")
            except Exception as e:
                self.notify(f"Error resetting stats: {e}", severity="error")
