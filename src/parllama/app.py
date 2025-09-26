"""The main application class."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from queue import Empty, Full, Queue
from weakref import WeakSet

import clipman as clipboard
import humanize
import ollama
from httpx import ConnectError
from ollama import ProgressResponse
from par_ai_core.llm_providers import LlmProvider
from rich.columns import Columns
from rich.console import ConsoleRenderable, RenderableType, RichCast
from rich.progress_bar import ProgressBar
from rich.style import Style
from rich.text import Text
from textual import on, work
from textual.app import App
from textual.binding import Binding
from textual.color import Color
from textual.message import Message
from textual.message_pump import MessagePump
from textual.notifications import SeverityLevel
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Input, Select, TextArea

from parllama import __application_title__
from parllama.chat_manager import ChatManager, chat_manager
from parllama.dialogs.help_dialog import HelpDialog
from parllama.dialogs.information import InformationDialog
from parllama.dialogs.theme_dialog import ThemeDialog
from parllama.execution.command_executor import CommandExecutor

# Execution system imports
from parllama.execution.execution_manager import ExecutionManager, execution_manager as global_execution_manager
from parllama.execution.template_matcher import TemplateMatcher
from parllama.messages.messages import (
    ChangeTab,
    ChatMessage,
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
    ProviderModelsChanged,
    PsMessage,
    RefreshProviderModelsRequested,
    RegisterForUpdates,
    SendToClipboard,
    SessionListChanged,
    SessionSelected,
    SessionToPrompt,
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

    notify_subs: dict[str, WeakSet[MessagePump]]
    main_screen: MainScreen
    job_queue: Queue[QueueJob]
    last_status: RenderableType = ""
    chat_manager: ChatManager
    job_timer: Timer | None
    ps_timer: Timer | None

    def __init__(self) -> None:
        """Initialize the application."""
        super().__init__()
        self.notify_subs = {"*": WeakSet[MessagePump]()}

        # Initialize state manager with logging capability
        self.state_manager = initialize_state_manager(self.log_it)

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

        # Limit job queue to prevent unbounded growth
        self.job_queue = Queue[QueueJob](maxsize=settings.job_queue_max_size)
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
        try:
            self.job_queue.put(job, timeout=settings.job_queue_put_timeout)
            return True
        except Full:
            self.status_notify("Job queue is full. Please wait for current operations to complete.", severity="warning")
            return False

    async def on_mount(self) -> None:
        """Display the screen."""
        self.main_screen = MainScreen()

        # Initialize execution system
        await self._initialize_execution_system()

        await self.push_screen(self.main_screen)
        if settings.check_for_updates:
            await update_manager.check_for_updates()

        self.app.post_message(
            RegisterForUpdates(
                widget=self,
                event_names=[
                    "LocalModelPulled",
                    "LocalModelPushed",
                    "LocalModelCreated",
                    "LocalModelDeleted",
                    "LocalModelCopied",
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

        self.post_message(RefreshProviderModelsRequested(None))

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
        except Exception as _:
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
        except Exception as _:
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
        """Copy local model"""
        try:
            ret = ollama_dm.copy_model(event.modelName, event.dstModelName)
            self.main_screen.local_view.post_message(
                LocalModelCopied(
                    src_model_name=event.modelName,
                    dst_model_name=event.dstModelName,
                    success=ret["status"] == "success",
                )
            )
        except ollama.ResponseError as e:
            self.handle_ollama_error("Model copy", event.modelName, e)
            self.main_screen.local_view.post_message(
                LocalModelCopied(
                    src_model_name=event.modelName,
                    dst_model_name=event.dstModelName,
                    success=False,
                )
            )
        except Exception as e:
            self.handle_ollama_error("Model copy", event.modelName, e)
            self.main_screen.local_view.post_message(
                LocalModelCopied(
                    src_model_name=event.modelName,
                    dst_model_name=event.dstModelName,
                    success=False,
                )
            )

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
        """Update progress bar embedded in status bar"""
        try:
            last_status = ""
            for msg in res:
                if settings.shutting_down:
                    break

                last_status = msg.status or ""
                pb: ProgressBar | None = None
                percent = ""
                if msg.total and msg.completed:
                    percent = str(int(msg.completed / msg.total * 100)) + "%"
                    primary_style = Style(color=Color.parse(self.current_theme.primary).rich_color)
                    background_style = Style(color=Color.parse(self.current_theme.surface or "#111").rich_color)
                    pb = ProgressBar(
                        total=msg.total or 0,
                        completed=msg.completed or 0,
                        width=25,
                        style=background_style,
                        complete_style=primary_style,
                        finished_style=primary_style,
                    )
                else:
                    percent = ""
                if percent and msg.status == "success":
                    percent = "100%"
                parts: list[RenderableType] = [
                    Text.assemble(
                        job.modelName,
                        " ",
                        msg.status or "",
                        " ",
                        percent,
                        " ",
                    )
                ]
                if pb:
                    parts.append(pb)

                self.post_message_all(StatusMessage(Columns(parts), log_it=False))
            return last_status
        except ollama.ResponseError as e:
            self.post_message_all(StatusMessage(Text.assemble(("error:" + str(e), "red"))))
            raise e

    async def do_pull(self, job: PullModelJob) -> None:
        """Pull a model from ollama.com"""
        try:
            res: Iterator[ProgressResponse] = ollama_dm.pull_model(job.modelName)
            last_status = await self.do_progress(job, res)

            self.post_message_all(LocalModelPulled(model_name=job.modelName, success=last_status == "success"))
        except Exception as e:
            self.handle_ollama_error("Model pull", job.modelName, e)
            self.post_message_all(LocalModelPulled(model_name=job.modelName, success=False))

    async def do_push(self, job: PushModelJob) -> None:
        """Push a model to ollama.com"""
        try:
            res: Iterator[ProgressResponse] = ollama_dm.push_model(job.modelName)
            last_status = await self.do_progress(job, res)

            self.post_message_all(LocalModelPushed(model_name=job.modelName, success=last_status == "success"))
        except Exception as e:
            self.handle_ollama_error("Model push", job.modelName, e)
            self.post_message_all(LocalModelPushed(model_name=job.modelName, success=False))

    async def do_create_model(self, job: CreateModelJob) -> None:
        """Create a new local model"""
        try:
            self.main_screen.log_view.richlog.write(f"Creating model {job.modelName} from {job.modelFrom}...")
            res = ollama_dm.create_model(
                model_name=job.modelName,
                model_from=job.modelFrom,
                system_prompt=job.systemPrompt,
                model_template=job.modelTemplate,
                model_license=job.model_license,
                quantize_level=job.quantizationLevel,
            )
            last_status = await self.do_progress(job, res)

            self.main_screen.local_view.post_message(
                LocalModelCreated(
                    model_name=job.modelName,
                    model_from=job.modelFrom,
                    system_prompt=job.systemPrompt,
                    model_template=job.modelTemplate,
                    model_license=job.model_license,
                    quantization_level=job.quantizationLevel,
                    success=last_status == "success",
                )
            )
        except ollama.ResponseError as e:
            error_msg = self.handle_ollama_error("Model creation", job.modelName, e, custom_handling=True)

            # Check for specific quantization errors
            if "quantization is only supported for F16 and F32 models" in error_msg:
                self.status_notify(
                    "Quantization requires F16 or F32 base models. The selected model is already quantized.",
                    severity="error",
                )
            elif "unsupported quantization type" in error_msg:
                self.status_notify(
                    "Invalid quantization level. Please use a supported type like q4_K_M, q5_K_M, etc.",
                    severity="error",
                )
            else:
                self.status_notify(f"Model creation failed: {error_msg}", severity="error")

            self.main_screen.local_view.post_message(
                LocalModelCreated(
                    model_name=job.modelName,
                    model_from=job.modelFrom,
                    system_prompt=job.systemPrompt,
                    model_template=job.modelTemplate,
                    model_license=job.model_license,
                    quantization_level=job.quantizationLevel,
                    success=False,
                )
            )
        except ConnectError as e:
            self.handle_ollama_error("Model creation", job.modelName, e)
            self.main_screen.local_view.post_message(
                LocalModelCreated(
                    model_name=job.modelName,
                    model_from=job.modelFrom,
                    system_prompt=job.systemPrompt,
                    model_template=job.modelTemplate,
                    model_license=job.model_license,
                    quantization_level=job.quantizationLevel,
                    success=False,
                )
            )
        except Exception as e:
            self.handle_ollama_error("Model creation", job.modelName, e)
            self.main_screen.local_view.post_message(
                LocalModelCreated(
                    model_name=job.modelName,
                    model_from=job.modelFrom,
                    system_prompt=job.systemPrompt,
                    model_template=job.modelTemplate,
                    model_license=job.model_license,
                    quantization_level=job.quantizationLevel,
                    success=False,
                )
            )

    @work(group="do_jobs", thread=True)
    async def do_jobs(self) -> None:
        """poll for queued jobs"""
        while True:
            try:
                job: QueueJob = self.job_queue.get(block=True, timeout=settings.job_queue_get_timeout)
                if settings.shutting_down:
                    return
                if not job:
                    continue
                job_type = type(job).__name__
                self.state_manager.set_busy(True, f"processing {job_type}")
                try:
                    if isinstance(job, PullModelJob):
                        await self.do_pull(job)
                    elif isinstance(job, PushModelJob):
                        await self.do_push(job)
                    elif isinstance(job, CopyModelJob):
                        await self.do_copy_local_model(job)
                    elif isinstance(job, CreateModelJob):
                        await self.do_create_model(job)
                    else:
                        self.status_notify(
                            f"Unknown job type {type(job)}",
                            severity="error",
                        )
                finally:
                    self.state_manager.set_busy(False, f"completed {job_type}")
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
        for _, s in self.notify_subs.items():
            s.discard(event.widget)

    @on(RegisterForUpdates)
    def on_register_for_updates(self, event: RegisterForUpdates) -> None:
        """Register for updates event"""
        for event_name in event.event_names:
            if event_name not in self.notify_subs:
                self.notify_subs[event_name] = WeakSet()
            self.notify_subs[event_name].add(event.widget)

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
        sub_name = event.__class__.__name__
        if sub_name in self.notify_subs:
            # Convert to list to avoid RuntimeError if set changes during iteration
            # WeakSet automatically removes dead references
            for w in list(self.notify_subs[sub_name]):
                w.post_message(event)

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

    @on(PromptSelected)
    def on_prompt_selected(self, event: PromptSelected) -> None:
        """Session selected event"""
        event.stop()
        self.post_message_all(event)

    @on(DeleteSession)
    def on_delete_session(self, event: DeleteSession) -> None:
        """Delete session event"""
        event.stop()
        self.post_message_all(event)

    @on(DeletePrompt)
    def on_delete_prompt(self, event: DeletePrompt) -> None:
        """Delete prompt event"""
        event.stop()
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

    async def _initialize_execution_system(self) -> None:
        """Initialize the execution system."""
        from parllama.execution import execution_manager

        global global_execution_manager

        # Initialize the global execution manager
        global_execution_manager = ExecutionManager(self)
        global_execution_manager.initialize_from_settings(settings)

        # Set the global variable in the execution_manager module
        execution_manager.execution_manager = global_execution_manager

        # Initialize command executor and template matcher
        self.command_executor = CommandExecutor(settings)
        self.template_matcher = TemplateMatcher(settings)

        # Load templates and history
        await global_execution_manager.load_templates()
        await global_execution_manager.load_execution_history()

    @on(ExecuteMessageRequested)
    async def on_execute_message_requested(self, event: ExecuteMessageRequested) -> None:
        """Handle execution request."""
        event.stop()

        if not settings.execution_enabled:
            self.notify("Code execution is disabled", severity="warning")
            return

        try:
            # Find matching templates
            if global_execution_manager is None:
                self.notify("Execution system not initialized", severity="error")
                return

            templates = global_execution_manager.get_enabled_templates()
            matching_templates = self.template_matcher.find_matching_templates(event.content, templates)

            if not matching_templates:
                self.notify("No execution templates match this content", severity="warning")
                return

            # Use the best matching template
            best_match = matching_templates[0]
            template = best_match["template"]

            # Extract the specific code to execute from applicable blocks
            applicable_blocks = best_match.get("applicable_blocks", [])
            if applicable_blocks:
                # Use the first applicable code block
                code_block = applicable_blocks[0]
                content_to_execute = code_block["code"]
                self.notify(f"Executing {code_block['language']} code block", severity="information")
            else:
                # Fallback: use get_executable_content to extract code
                executable_parts = self.template_matcher.get_executable_content(event.content)
                if executable_parts:
                    content_to_execute = executable_parts[0]["content"]
                    self.notify(f"Executing {executable_parts[0]['language']} code", severity="information")
                else:
                    content_to_execute = event.content
                    self.notify("No code blocks found, executing entire content", severity="warning")

            # Check if confirmation is required
            requires_confirmation, warnings = self.template_matcher.should_require_confirmation(
                content_to_execute, template
            )

            if requires_confirmation and settings.execution_require_confirmation:
                # For now, just show warnings and proceed - full confirmation dialog would be added later
                if warnings:
                    warning_text = "; ".join(warnings)
                    self.notify(f"Executing with warnings: {warning_text}", severity="warning")

            # Execute the template with the extracted code content
            result = await self.command_executor.execute_template(
                template=template,
                content=content_to_execute,
                message_id=event.message_id,
            )

            # Add to execution history
            if global_execution_manager:
                global_execution_manager.add_execution_result(result)

            # Post completion message
            self.post_message(
                ExecutionCompleted(message_id=event.message_id, result=result.to_dict(), add_to_chat=True)
            )

            # Notify success/failure
            if result.success:
                self.notify(f"Executed successfully: {template.name}", severity="information")
            else:
                self.notify(f"Execution failed: {result.error_message or 'Unknown error'}", severity="error")

        except Exception as e:
            import traceback

            error_details = f"{str(e)} - {traceback.format_exc()}"
            self.notify(f"Execution error: {str(e)}", severity="error")
            self.post_message(
                ExecutionFailed(message_id=event.message_id, template_id=event.template_id or "", error=error_details)
            )

    @on(ExecutionCompleted)
    def on_execution_completed(self, event: ExecutionCompleted) -> None:
        """Handle execution completion."""
        event.stop()

        if event.add_to_chat:
            # Add execution result as a new message to the current chat session
            try:
                from parllama.chat_message import ParllamaChatMessage
                from parllama.execution.execution_result import ExecutionResult

                result = ExecutionResult.from_dict(event.result)

                # Create a new assistant message with the execution result
                formatted_output = result.get_formatted_output()

                # Get the current session from the chat view
                chat_view = self.main_screen.chat_view
                if hasattr(chat_view, "session") and chat_view.session:
                    execution_message = ParllamaChatMessage(role="assistant", content=formatted_output)

                    chat_view.session.add_message(execution_message)
                    # Follow the same notification pattern as send_chat
                    chat_view.session._notify_subs(
                        ChatMessage(parent_id=chat_view.session.id, message_id=execution_message.id, is_final=True)
                    )
                    from parllama.messages.par_chat_messages import ParChatUpdated

                    chat_view.session.post_message(
                        ParChatUpdated(parent_id=chat_view.session.id, message_id=execution_message.id, is_final=True)
                    )
                    chat_view.session.save()
                    self.log_it(f"Execution result added to chat session: {chat_view.session.name}")

            except Exception as e:
                self.notify(f"Error adding execution result to chat: {str(e)}", severity="error")

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
        """Handle common Ollama error patterns.

        Args:
            operation: The operation being performed (e.g., "Model copy", "Model pull")
            model_name: The name of the model involved
            error: The exception that occurred
            custom_handling: If True, only logs but doesn't send notifications (for custom error handling)

        Returns:
            The error message string for custom handling
        """
        if isinstance(error, ollama.ResponseError):
            error_msg = str(error)
            self.log_it(f"{operation} failed (ResponseError): {error_msg}")
            if not custom_handling:
                self.status_notify(f"{operation} failed: {error_msg}", severity="error")
            return error_msg
        elif isinstance(error, ConnectError):
            error_msg = "Cannot connect to Ollama server"
            self.log_it(f"{operation} failed: {error_msg}")
            if not custom_handling:
                self.status_notify("Cannot connect to Ollama server. Is it running?", severity="error")
            return error_msg
        else:
            error_msg = str(error)
            self.log_it(f"{operation} failed (unexpected error): {type(error).__name__}: {error_msg}")
            if not custom_handling:
                self.status_notify(f"{operation} failed: {error_msg}", severity="error")
            return error_msg

    async def action_shutdown(self) -> None:
        """Quit the application"""
        settings.shutting_down = True
        self.state_manager.shutdown()
        await self.action_quit()

    @work(exclusive=True)
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
