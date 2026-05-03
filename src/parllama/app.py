"""The main application class."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from queue import Empty

import clipman as clipboard
import humanize
from httpx import ConnectError
from ollama import ProgressResponse
from par_ai_core.llm_providers import LlmProvider
from rich.console import ConsoleRenderable, RenderableType, RichCast
from rich.text import Text
from textual import on, work
from textual.app import App
from textual.binding import Binding
from textual.message import Message
from textual.notifications import SeverityLevel
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Input, Select, TextArea

from parllama import __application_title__
from parllama.chat_manager import ChatManager, chat_manager
from parllama.coordinators.execution_coordinator import ExecutionCoordinator
from parllama.coordinators.model_job_processor import ModelJobProcessor
from parllama.dialogs.help_dialog import HelpDialog
from parllama.dialogs.information import InformationDialog
from parllama.dialogs.theme_dialog import ThemeDialog
from parllama.event_bus import EventBus
from parllama.messages.messages import (
    ChangeTab,
    ChatGenerationAborted,
    ChatMessage,
    ChatMessageDeleted,
    ClearChatInputHistory,
    DeletePrompt,
    DeleteSession,
    ExecuteMessageRequested,
    ExecutionCompleted,
    ExecutionFailed,
    LocalCreateModelFromExistingRequested,
    LocalModelCopied,
    LocalModelCopyRequested,
    LocalModelCreated,
    LocalModelCreateRequested,
    LocalModelDelete,
    LocalModelDeleted,
    LocalModelListLoaded,
    LocalModelListRefreshRequested,
    LocalModelPulled,
    LocalModelPullRequested,
    LocalModelPushed,
    LocalModelPushRequested,
    LogIt,
    ModelInteractRequested,
    PromptListChanged,
    PromptListLoaded,
    PromptSelected,
    PromptUpdated,
    ProviderModelsChanged,
    PsMessage,
    RefreshProviderModelsRequested,
    RegisterForUpdates,
    SendToClipboard,
    SessionAutoNameRequested,
    SessionListChanged,
    SessionSelected,
    SessionToPrompt,
    SessionUpdated,
    SetModelNameLoading,
    SiteModelsLoaded,
    SiteModelsRefreshRequested,
    StatusMessage,
    UnRegisterForUpdates,
)
from parllama.models.jobs import CopyModelJob, CreateModelJob, PullModelJob, PushModelJob, QueueJob
from parllama.ollama_data_manager import ollama_dm
from parllama.prompt_utils.import_fabric import import_fabric_manager
from parllama.provider_manager import provider_manager
from parllama.screens.main_screen import MainScreen
from parllama.secrets_manager import secrets_manager
from parllama.settings_manager import settings
from parllama.state_manager import initialize_state_manager
from parllama.theme_manager import theme_manager
from parllama.update_manager import update_manager


class ParLlamaApp(App[None]):
    """Main application class"""

    TITLE = __application_title__
    COMMAND_PALETTE_BINDING = "ctrl+underscore"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding(key="f1", action="help", description="Help", show=True, priority=True),
        Binding(key="ctrl+q", action="app.shutdown", description="Quit", show=True),
        Binding(
            key="f10",
            action="change_theme",
            description="Change Theme",
            show=True,
            priority=True,
        ),
        Binding(key="ctrl+c", action="noop", show=False),
    ]

    commands: list[dict[str, str]] = [
        {
            "action": "action_quit",
            "cmd": "Quit Application",
            "help": "Quit the application as soon as possible",
        }
    ]
    CSS_PATH = "app.tcss"

    event_bus: EventBus
    main_screen: MainScreen
    last_status: RenderableType = ""
    chat_manager: ChatManager
    job_timer: Timer | None
    ps_timer: Timer | None
    model_job_processor: ModelJobProcessor
    execution_coordinator: ExecutionCoordinator

    def __init__(self) -> None:
        """Initialize the application."""
        super().__init__()
        self.event_bus = EventBus()

        # Initialize state manager with logging capability
        self.state_manager = initialize_state_manager(self.log_it)

        # Initialize coordinators (delegated from God Object decomposition)
        self.model_job_processor = ModelJobProcessor(self)
        self.execution_coordinator = ExecutionCoordinator(self)

        theme_manager.set_app(self)
        provider_manager.set_app(self)
        secrets_manager.set_app(self)
        ollama_dm.set_app(self)
        chat_manager.set_app(self)
        update_manager.set_app(self)
        import_fabric_manager.set_app(self)

        # Initialize memory manager
        from parllama.memory_manager import memory_manager

        memory_manager._app = self

        self.job_timer = None
        self.ps_timer = None
        self.title = __application_title__

        self.last_status = ""
        if settings.theme_name not in theme_manager.list_themes():
            settings.theme_name = f"{settings.theme_name}_{settings.theme_mode}"
            if settings.theme_name not in theme_manager.list_themes():
                settings.theme_name = settings.theme_fallback_name

        theme_manager.change_theme(settings.theme_name)

    def add_job_to_queue(self, job: QueueJob) -> bool:
        """Add a job to the queue with error handling.

        Returns:
            bool: True if job was added successfully, False if queue is full
        """
        return self.model_job_processor.add_job_to_queue(job)

    async def on_mount(self) -> None:
        """Display the screen."""
        self.main_screen = MainScreen()

        # Initialize execution system
        await self.execution_coordinator.initialize()

        await self.push_screen(self.main_screen)
        if settings.check_for_updates:
            await update_manager.check_for_updates()

        self.app.post_message(
            RegisterForUpdates(
                widget=self,
                event_names=[
                    LocalModelPulled,
                    LocalModelPushed,
                    LocalModelCreated,
                    LocalModelDeleted,
                    LocalModelCopied,
                ],
            )
        )
        self.job_timer = self.set_timer(settings.job_timer_interval, self.do_jobs)
        if settings.ollama_ps_poll_interval > 0:
            self.ps_timer = self.set_timer(settings.ps_timer_interval, self.update_ps)

        if settings.show_first_run:
            settings.show_first_run = False
            settings.save()
            self.set_timer(settings.notification_timeout_info, self.show_first_run)

    async def show_first_run(self) -> None:
        """Show first run screen"""
        await self.app.push_screen(
            InformationDialog(
                title="Welcome",
                message="""
Thank your for trying ParLlama!
Please take a moment to familiarize yourself with the the various options.
New options are being added all the time! Check out What's New on the repo.
[link]https://github.com/paulrobello/parllama?tab=readme-ov-file#whats-new[/link]
By default ParLlama makes no attempt to connect to the internet and collects no data from you.
If you would like to auto check for updates, you can enable it in the Startup section of Options.
If you want to use other providers, you can set them up in the Providers section of the Options tab.
Some functions are only available via slash / commands on that chat tab. You can use /help to see what commands are available.
                """,
            )
        )

    def action_noop(self) -> None:
        """Do nothing"""

    def action_help(self) -> None:
        """Show help screen"""
        self.app.push_screen(HelpDialog())

    def action_clear_field(self) -> None:
        """Clear focused widget value"""
        f: Widget | None = self.screen.focused
        if not f:
            return
        if isinstance(f, Input):
            f.value = ""
        if isinstance(f, TextArea):
            f.text = ""
        if isinstance(f, Select):
            f.value = Select.BLANK

    def action_copy_to_clipboard(self) -> None:
        """Copy focused widget value to clipboard"""
        f: Widget | None = self.screen.focused
        if not f:
            return

        if isinstance(f, Input | Select):
            self.app.post_message(SendToClipboard(str(f.value) if f.value and f.value != Select.BLANK else ""))

        if isinstance(f, TextArea):
            self.app.post_message(SendToClipboard(f.selected_text or f.text))

    def action_cut_to_clipboard(self) -> None:
        """Cut focused widget value to clipboard"""
        try:
            f: Widget | None = self.screen.focused
            if not f:
                return
            if isinstance(f, Input):
                clipboard.copy(f.value)
                f.value = ""
            if isinstance(f, Select):
                self.app.post_message(SendToClipboard(str(f.value) if f.value and f.value != Select.BLANK else ""))
            if isinstance(f, TextArea):
                clipboard.copy(f.selected_text or f.text)
                f.text = ""
        except (OSError, AttributeError) as _:
            self.notify("Error with clipboard", severity="error")

    @on(SendToClipboard)
    def send_to_clipboard(self, event: SendToClipboard) -> None:
        """Send string to clipboard"""
        # works for remote ssh sessions
        self.copy_to_clipboard(event.message)
        # works for local sessions
        try:
            clipboard.copy(event.message)
            if event.notify:
                self.notify("Copied to clipboard")
        except (OSError, AttributeError) as _:
            self.notify("Error with clipboard", severity="error")

    @on(LocalModelPushRequested)
    def on_model_push_requested(self, event: LocalModelPushRequested) -> None:
        """Push requested model event"""
        if self.add_job_to_queue(PushModelJob(modelName=event.model_name)):
            self.main_screen.local_view.post_message(SetModelNameLoading(event.model_name, True))
        # self.notify(f"Model push {msg.model_name} requested")

    @on(LocalModelCreateRequested)
    def on_model_create_requested(self, event: LocalModelCreateRequested) -> None:
        """Create model requested event"""
        self.add_job_to_queue(
            CreateModelJob(
                modelName=event.model_name,
                modelFrom=event.model_from,
                systemPrompt=event.system_prompt,
                modelTemplate=event.model_template,
                model_license=event.mode_license,
                quantizationLevel=event.quantization_level,
            )
        )

    @on(LocalModelDelete)
    def on_local_model_delete(self, event: LocalModelDelete) -> None:
        """Delete local model event"""
        if not ollama_dm.delete_model(event.model_name):
            self.main_screen.local_view.post_message(SetModelNameLoading(event.model_name, False))
            self.status_notify(f"Error deleting model {event.model_name}.", severity="error")
            return
        self.post_message_all(LocalModelDeleted(event.model_name))

    @on(LocalModelDeleted)
    def on_model_deleted(self, event: LocalModelDeleted) -> None:
        """Local model has been deleted event"""
        self.post_message_all(ProviderModelsChanged(provider=LlmProvider.OLLAMA))
        self.status_notify(f"Model {event.model_name} deleted.")

    @on(LocalModelPullRequested)
    def on_model_pull_requested(self, event: LocalModelPullRequested) -> None:
        """Pull requested model event"""
        if self.add_job_to_queue(PullModelJob(modelName=event.model_name)):
            if event.notify:
                self.notify(f"Model pull {event.model_name} queued")
            self.post_message_all(SetModelNameLoading(event.model_name, True))

    @on(LocalModelCopyRequested)
    def on_local_model_copy_requested(self, event: LocalModelCopyRequested) -> None:
        """Local model copy request event"""
        self.add_job_to_queue(CopyModelJob(modelName=event.src_model_name, dstModelName=event.dst_model_name))

    async def do_copy_local_model(self, event: CopyModelJob) -> None:
        """Copy local model. Delegates to ModelJobProcessor."""
        await self.model_job_processor.do_copy_local_model(event)

    @on(LocalModelCopied)
    def on_local_model_copied(self, event: LocalModelCopied) -> None:
        """Local model copied event"""
        if event.success:
            self.status_notify(f"Model {event.src_model_name} copied to {event.dst_model_name}")
        else:
            self.status_notify(
                f"Copying model {event.src_model_name} to {event.dst_model_name} failed",
                severity="error",
            )

    async def do_progress(self, job: QueueJob, res: Iterator[ProgressResponse]) -> str:
        """Update progress bar. Delegates to ModelJobProcessor."""
        return await self.model_job_processor.do_progress(job, res)

    async def do_pull(self, job: PullModelJob) -> None:
        """Pull a model from ollama.com. Delegates to ModelJobProcessor."""
        await self.model_job_processor.do_pull(job)

    async def do_push(self, job: PushModelJob) -> None:
        """Push a model to ollama.com. Delegates to ModelJobProcessor."""
        await self.model_job_processor.do_push(job)

    async def do_create_model(self, job: CreateModelJob) -> None:
        """Create a new local model. Delegates to ModelJobProcessor."""
        await self.model_job_processor.do_create_model(job)

    @work(group="do_jobs", thread=True)
    async def do_jobs(self) -> None:
        """Poll for queued jobs."""
        while True:
            try:
                job: QueueJob = self.model_job_processor.job_queue.get(
                    block=True, timeout=settings.job_queue_get_timeout
                )
                if settings.shutting_down:
                    return
                if not job:
                    continue
                await self.model_job_processor.process_job(job)
            except Empty:
                if self._exit:
                    return
                continue

    @on(LocalModelPulled)
    def on_model_pulled(self, event: LocalModelPulled) -> None:
        """Model pulled event"""
        if event.success:
            self.status_notify(
                f"Model {event.model_name} pulled.",
            )
            self.set_timer(settings.model_refresh_timer_interval, self.action_refresh_models)
        else:
            self.status_notify(
                f"Model {event.model_name} failed to pull.",
                severity="error",
            )

    @on(LocalModelCreated)
    def on_model_created(self, event: LocalModelCreated) -> None:
        """Model created event"""
        if event.success:
            self.status_notify(
                f"Model {event.model_name} created.",
            )
            self.set_timer(settings.model_refresh_timer_interval, self.action_refresh_models)
        else:
            self.status_notify(
                f"Model {event.model_name} failed to create.",
                severity="error",
            )

    def action_refresh_models(self) -> None:
        """Refresh models action."""
        self.refresh_models()

    @on(UnRegisterForUpdates)
    def on_unregister_for_updates(self, event: UnRegisterForUpdates) -> None:
        """Unregister widget from all updates"""
        if not event.widget:
            return
        self.event_bus.unsubscribe(event.widget)

    @on(RegisterForUpdates)
    def on_register_for_updates(self, event: RegisterForUpdates) -> None:
        """Register for updates event"""
        self.event_bus.subscribe(event.widget, event.event_names)

    @on(LocalModelListRefreshRequested)
    def on_model_list_refresh_requested(self) -> None:
        """Model refresh request event"""
        can_start, error_msg = self.state_manager.can_start_operation("model refresh")
        if not can_start:
            self.status_notify(error_msg)
            return
        self.refresh_models()

    @work(group="refresh_models", thread=True)
    async def refresh_models(self):
        """Refresh the models."""
        self.state_manager.set_refreshing(True, "local models")
        try:
            self.post_message_all(StatusMessage("Local model list refreshing..."))
            ollama_dm.refresh_models()
            self.post_message_all(StatusMessage("Local model list refreshed"))
            self.post_message_all(LocalModelListLoaded())
            self.post_message_all(ProviderModelsChanged(provider=LlmProvider.OLLAMA))
        except ConnectError as e:
            self.post_message(
                LogIt(
                    f"Failed to refresh local models: {e}",
                    severity="error",
                    notify=True,
                )
            )
        finally:
            self.state_manager.set_refreshing(False, "local models")

    # @on(LocalModelListLoaded)
    # def on_model_data_loaded(self) -> None:
    #     """Refresh model completed"""
    #     self.post_message_all(StatusMessage("Local model list refreshed"))
    #     # self.notify("Local models refreshed.")

    @on(SiteModelsRefreshRequested)
    def on_site_models_refresh_requested(self, msg: SiteModelsRefreshRequested) -> None:
        """Site model refresh request event"""
        can_start, error_msg = self.state_manager.can_start_operation("site model refresh")
        if not can_start:
            self.status_notify(error_msg)
            return
        self.refresh_site_models(msg)

    @on(SiteModelsLoaded)
    def on_site_models_loaded(self) -> None:
        """Site model refresh completed"""
        self.status_notify("Site models refreshed")

    @work(group="refresh_site_model", thread=True)
    async def refresh_site_models(self, msg: SiteModelsRefreshRequested):
        """Refresh the site model."""
        operation = f"site models: {msg.ollama_namespace or 'models'}"
        self.state_manager.set_refreshing(True, operation)
        try:
            self.post_message_all(
                StatusMessage(f"Site models for {msg.ollama_namespace or 'models'} refreshing... force={msg.force}")
            )
            ollama_dm.refresh_site_models(msg.ollama_namespace, None, msg.force)
            self.main_screen.site_view.post_message(SiteModelsLoaded(ollama_namespace=msg.ollama_namespace))
            self.post_message_all(
                StatusMessage(f"Site models for {msg.ollama_namespace or 'models'} loaded. force={msg.force}")
            )

        finally:
            self.state_manager.set_refreshing(False, operation)

    @work(group="update_ps", thread=True)
    async def update_ps(self) -> None:
        """Update ps status bar msg"""
        was_blank = False
        while not settings.shutting_down:
            if settings.ollama_ps_poll_interval < 1:
                self.post_message_all(PsMessage(msg=""))
                break
            await asyncio.sleep(settings.ollama_ps_poll_interval)
            ret = ollama_dm.model_ps()
            if len(ret.models) < 1:
                if not was_blank:
                    self.post_message_all(PsMessage(msg=""))
                was_blank = True
                continue
            was_blank = False
            info = ret.models[0]  # only take first one since ps status bar is a single line
            self.post_message_all(
                PsMessage(
                    msg=Text.assemble(
                        "Name: ",
                        info.name,
                        " Size: ",
                        humanize.naturalsize(info.size_vram),
                        " Processor: ",
                        ret.processor,
                        " Until: ",
                        humanize.naturaltime(info.expires_at),
                    )
                )
            )

    def status_notify(self, msg: str, severity: SeverityLevel = "information") -> None:
        """Show notification and update status bar"""
        timeout = (
            settings.notification_timeout_error if severity != "information" else settings.notification_timeout_info
        )
        if severity == "warning":
            timeout = settings.notification_timeout_warning
        self.notify(msg, severity=severity, timeout=timeout)
        self.main_screen.post_message(StatusMessage(msg))

    def post_message_all(self, event: Message) -> None:
        """Post a message to all screens"""
        if isinstance(event, StatusMessage):
            if event.log_it:
                self.log(event.msg)
            self.last_status = event.msg
            self.main_screen.post_message(event)
            return
        if isinstance(event, PsMessage):
            self.main_screen.post_message(event)
            return
        self.event_bus.broadcast(event)

    @on(ChangeTab)
    def on_change_tab(self, event: ChangeTab) -> None:
        """Change tab event"""
        event.stop()
        self.main_screen.change_tab(event.tab)

    @on(LocalCreateModelFromExistingRequested)
    def on_create_model_from_existing_requested(self, msg: LocalCreateModelFromExistingRequested) -> None:
        """Create model from existing event"""
        self.main_screen.create_view.name_input.value = f"my-{msg.model_name}"
        if not self.main_screen.create_view.name_input.value.endswith(":latest"):
            self.main_screen.create_view.name_input.value += ":latest"
        self.main_screen.create_view.input_from.value = msg.model_name
        self.main_screen.create_view.ta_system_prompt.text = msg.system_prompt or ""
        self.main_screen.create_view.ta_template.text = msg.model_template
        self.main_screen.create_view.ta_license.text = msg.model_license or ""
        self.main_screen.create_view.quantize_input.value = msg.quantization_level or ""
        self.main_screen.change_tab("Create")
        self.main_screen.create_view.name_input.focus()

    @on(ModelInteractRequested)
    async def on_model_interact_requested(self, event: ModelInteractRequested) -> None:
        """Model interact requested event"""
        await self.main_screen.chat_view.action_new_tab()
        self.main_screen.chat_view.active_tab.session_config.provider_model_select.provider_select.value = (
            LlmProvider.OLLAMA
        )
        self.main_screen.chat_view.active_tab.session_config.provider_model_select.model_select.deferred_value = (
            event.model_name
        )
        self.main_screen.change_tab("Chat")
        self.main_screen.chat_view.user_input.focus()

    @on(ClearChatInputHistory)
    def on_clear_chat_history(self, event: ClearChatInputHistory) -> None:
        """Clear chat history event"""
        event.stop()
        self.post_message_all(event)

    @on(SessionListChanged)
    def on_session_list_changed(self, event: SessionListChanged) -> None:
        """Session list changed event"""
        event.stop()
        self.post_message_all(event)

    @on(ChatMessage)
    def on_chat_message(self, event: ChatMessage) -> None:
        """Route chat message events to the chat view."""
        event.stop()
        self.main_screen.chat_view.post_message(
            ChatMessage(parent_id=event.parent_id, message_id=event.message_id, is_final=event.is_final)
        )

    @on(ChatMessageDeleted)
    def on_chat_message_deleted(self, event: ChatMessageDeleted) -> None:
        """Route chat message deletion events to the chat view."""
        event.stop()
        self.main_screen.chat_view.post_message(
            ChatMessageDeleted(parent_id=event.parent_id, message_id=event.message_id)
        )

    @on(ChatGenerationAborted)
    def on_chat_generation_aborted(self, event: ChatGenerationAborted) -> None:
        """Route chat generation abort events to the chat view."""
        event.stop()
        self.main_screen.chat_view.post_message(ChatGenerationAborted(session_id=event.session_id))

    @on(PromptListChanged)
    def on_prompt_list_changed(self, event: PromptListChanged) -> None:
        """Prompt list changed event"""
        event.stop()
        self.post_message_all(event)

    @on(SessionSelected)
    def on_session_selected(self, event: SessionSelected) -> None:
        """Session selected event"""
        event.stop()
        self.post_message_all(event)

    @on(SessionUpdated)
    def on_session_updated(self, event: SessionUpdated) -> None:
        """Session updated event."""
        event.stop()
        chat_manager.maybe_notify_session_updated(event.changed)
        self.post_message_all(event)

    @on(PromptSelected)
    def on_prompt_selected(self, event: PromptSelected) -> None:
        """Session selected event"""
        event.stop()
        self.post_message_all(event)

    @on(DeleteSession)
    def on_delete_session(self, event: DeleteSession) -> None:
        """Delete session event"""
        event.stop()
        chat_manager.delete_session(event.session_id)
        self.post_message_all(event)

    @on(SessionAutoNameRequested)
    def on_session_auto_name_requested(self, event: SessionAutoNameRequested) -> None:
        """Session auto-name requested event."""
        event.stop()
        chat_manager.auto_name_session(event.session_id, event.llm_config, event.context)

    @on(PromptUpdated)
    def on_prompt_updated(self, event: PromptUpdated) -> None:
        """Prompt updated event."""
        event.stop()
        chat_manager.notify_prompts_changed()

    @on(DeletePrompt)
    def on_delete_prompt(self, event: DeletePrompt) -> None:
        """Delete prompt event"""
        event.stop()
        chat_manager.delete_prompt(event.prompt_id)
        self.post_message_all(event)

    @on(SessionToPrompt)
    def on_session_to_prompt(self, event: SessionToPrompt) -> None:
        """Session to prompt event"""
        event.stop()
        chat_manager.session_to_prompt(event.session_id, event.submit_on_load, event.prompt_name)

    @on(PromptListLoaded)
    def on_prompt_list_loaded(self, event: PromptListLoaded) -> None:
        """Prompt list loaded event"""
        event.stop()
        self.post_message_all(event)

    @on(LogIt)
    def on_log_it(self, event: LogIt) -> None:
        """Log an event to the log view"""
        event.stop()
        self.log_it(event.msg)
        if event.notify and isinstance(event.msg, str):
            self.notify(
                event.msg,
                severity=event.severity,
                timeout=event.timeout or int(settings.notification_timeout_info),
            )

    @on(ExecuteMessageRequested)
    async def on_execute_message_requested(self, event: ExecuteMessageRequested) -> None:
        """Handle execution request. Delegates to ExecutionCoordinator."""
        event.stop()
        await self.execution_coordinator.handle_execute_message_requested(event)

    @on(ExecutionCompleted)
    def on_execution_completed(self, event: ExecutionCompleted) -> None:
        """Handle execution completion. Delegates to ExecutionCoordinator."""
        event.stop()
        self.execution_coordinator.handle_execution_completed(event)

    @on(ExecutionFailed)
    def on_execution_failed(self, event: ExecutionFailed) -> None:
        """Handle execution failure."""
        event.stop()
        self.log_it(f"Execution failed for message {event.message_id}: {event.error}")

    def log_it(self, msg: ConsoleRenderable | RichCast | str | object) -> None:
        """Log a message to the log view"""
        self.main_screen.log_view.richlog.write(msg)

    def handle_ollama_error(
        self, operation: str, model_name: str, error: Exception, custom_handling: bool = False
    ) -> str:
        """Handle common Ollama error patterns. Delegates to ModelJobProcessor."""
        return self.model_job_processor.handle_ollama_error(operation, model_name, error, custom_handling)

    async def action_shutdown(self) -> None:
        """Quit the application"""
        settings.shutting_down = True
        self.state_manager.shutdown()
        await self.action_quit()

    @work(exclusive=True, thread=True)
    async def refresh_provider_models(self) -> None:
        """Refresh provider models"""
        provider_manager.refresh_models()

    @on(RefreshProviderModelsRequested)
    def on_refresh_provider_models(self, event: RefreshProviderModelsRequested) -> None:
        """Refresh provider models event"""
        event.stop()
        self.refresh_provider_models()

    @on(ProviderModelsChanged)
    def on_provider_models_refreshed(self, event: ProviderModelsChanged) -> None:
        """Provider models refreshed event"""
        event.stop()
        self.post_message_all(event)

    @work
    async def action_change_theme(self) -> None:
        """An action to change the theme."""
        theme = await self.push_screen_wait(ThemeDialog())
        settings.theme_name = theme
