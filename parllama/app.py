"""The main application class."""
from __future__ import annotations

import asyncio
from collections.abc import Iterator
from queue import Empty
from queue import Queue
from typing import Any

import ollama
import pyperclip  # type: ignore
from rich.columns import Columns
from rich.console import RenderableType
from rich.progress_bar import ProgressBar
from rich.style import Style
from rich.text import Text
from textual import on
from textual import work
from textual.app import App
from textual.binding import Binding
from textual.color import Color
from textual.message import Message
from textual.notifications import SeverityLevel
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Input
from textual.widgets import Select
from textual.widgets import TextArea

from parllama import __application_title__
from parllama.chat_manager import chat_manager
from parllama.chat_manager import ChatManager
from parllama.data_manager import dm
from parllama.dialogs.help_dialog import HelpDialog
from parllama.messages.main import AppRequest
from parllama.messages.main import ChangeTab
from parllama.messages.main import CreateModelFromExistingRequested
from parllama.messages.main import DeleteSession
from parllama.messages.main import LocalModelCopied
from parllama.messages.main import LocalModelCopyRequested
from parllama.messages.main import LocalModelDelete
from parllama.messages.main import LocalModelDeleted
from parllama.messages.main import LocalModelListLoaded
from parllama.messages.main import LocalModelListRefreshRequested
from parllama.messages.main import ModelCreated
from parllama.messages.main import ModelCreateRequested
from parllama.messages.main import ModelInteractRequested
from parllama.messages.main import ModelPulled
from parllama.messages.main import ModelPullRequested
from parllama.messages.main import ModelPushed
from parllama.messages.main import ModelPushRequested
from parllama.messages.main import NotifyErrorMessage
from parllama.messages.main import NotifyInfoMessage
from parllama.messages.main import PsMessage
from parllama.messages.main import SendToClipboard
from parllama.messages.main import SessionListChanged
from parllama.messages.main import SessionSelected
from parllama.messages.main import SetModelNameLoading
from parllama.messages.main import SiteModelsLoaded
from parllama.messages.main import SiteModelsRefreshRequested
from parllama.messages.main import StatusMessage
from parllama.messages.main import UnRegisterForUpdates
from parllama.models.jobs import CopyModelJob
from parllama.models.jobs import CreateModelJob
from parllama.models.jobs import PullModelJob
from parllama.models.jobs import PushModelJob
from parllama.models.jobs import QueueJob
from parllama.models.settings_data import settings
from parllama.screens.main_screen import MainScreen
from parllama.theme_manager import theme_manager


class ParLlamaApp(App[None]):
    """Main application class"""

    TITLE = __application_title__
    BINDINGS = [
        Binding(key="f1", action="help", description="Help", show=True, priority=True),
        Binding(key="ctrl+q", action="app.quit", description="Quit", show=True),
        Binding(
            key="f10",
            action="toggle_dark",
            description="Toggle Dark Mode",
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

    # DEFAULT_CSS = """
    # """

    notify_subs: dict[str, set[Widget]]
    main_screen: MainScreen
    job_queue: Queue[QueueJob]
    is_busy: bool = False
    last_status: RenderableType = ""
    chat_manager: ChatManager
    job_timer: Timer | None
    ps_timer: Timer | None

    def __init__(self) -> None:
        """Initialize the application."""
        super().__init__()
        self.notify_subs = {"*": set[Widget]()}
        chat_manager.set_app(self)

        self.job_timer = None
        self.ps_timer = None
        self.title = __application_title__
        self.dark = settings.theme_mode != "light"
        self.design = theme_manager.get_theme(settings.theme_name)  # type: ignore
        self.job_queue = Queue[QueueJob]()
        self.is_busy = False
        self.is_refreshing = False
        self.last_status = ""
        self.main_screen = MainScreen()

    def _watch_dark(self, value: bool) -> None:
        """Watch the dark property and save pref to file."""
        settings.theme_mode = "dark" if value else "light"
        settings.save_settings_to_file()

    def get_css_variables(self) -> dict[str, str]:
        """Get a mapping of variables used to pre-populate CSS.

        May be implemented in a subclass to add new CSS variables.

        Returns:
            A mapping of variable name to value.
        """
        return theme_manager.get_color_system_for_theme_mode(
            settings.theme_name, self.dark
        ).generate()

    @on(NotifyInfoMessage)
    def notify_info(self, event: NotifyInfoMessage) -> None:
        """Show info toast message for 3 seconds"""
        self.notify(event.message, timeout=event.timeout)

    @on(NotifyErrorMessage)
    def notify_error(self, event: NotifyErrorMessage) -> None:
        """Show error toast message for 6 seconds"""
        self.notify(event.message, severity="error", timeout=event.timeout)

    async def on_mount(self) -> None:
        """Display the main or locked screen."""
        await self.push_screen(self.main_screen)
        self.main_screen.post_message(
            StatusMessage(f"Data folder: {settings.data_dir}")
        )
        self.main_screen.post_message(
            StatusMessage(f"Chat folder: {settings.chat_dir}")
        )
        self.main_screen.post_message(
            StatusMessage(f"Using Ollama server url: {settings.ollama_host}")
        )
        if settings.ollama_ps_poll_interval:
            self.main_screen.post_message(
                StatusMessage(
                    f"Polling Ollama ps every: {settings.ollama_ps_poll_interval} seconds"
                )
            )
        else:
            self.main_screen.post_message(StatusMessage("Polling Ollama ps disabled"))

        self.main_screen.post_message(
            StatusMessage(
                f"""Theme: "{settings.theme_name}" in {settings.theme_mode} mode"""
            )
        )
        self.main_screen.post_message(
            StatusMessage(f"Last screen: {settings.last_screen}")
        )
        self.main_screen.post_message(
            StatusMessage(f"Last chat model: {settings.last_chat_model}")
        )
        self.main_screen.post_message(
            StatusMessage(f"Last model temp: {settings.last_chat_temperature}")
        )
        self.main_screen.post_message(
            StatusMessage(f"Last session name: {settings.last_chat_session_name}")
        )

        self.job_timer = self.set_timer(1, self.do_jobs)
        if settings.ollama_ps_poll_interval > 0:
            self.ps_timer = self.set_timer(1, self.update_ps)

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

        if isinstance(f, (Input, Select)):
            self.app.post_message(
                SendToClipboard(
                    str(f.value) if f.value and f.value != Select.BLANK else ""
                )
            )

        if isinstance(f, TextArea):
            self.app.post_message(SendToClipboard(f.selected_text or f.text))

    def action_cut_to_clipboard(self) -> None:
        """Cut focused widget value to clipboard"""
        f: Widget | None = self.screen.focused
        if not f:
            return
        if isinstance(f, Input):
            pyperclip.copy(f.value)
            f.value = ""
        if isinstance(f, Select):
            self.app.post_message(
                SendToClipboard(
                    str(f.value) if f.value and f.value != Select.BLANK else ""
                )
            )
        if isinstance(f, TextArea):
            pyperclip.copy(f.selected_text or f.text)
            f.text = ""

    @on(SendToClipboard)
    def send_to_clipboard(self, event: SendToClipboard) -> None:
        """Send string to clipboard"""
        # works for remote ssh sessions
        self.copy_to_clipboard(event.message)
        # works for local sessions
        pyperclip.copy(event.message)
        if event.notify:
            self.post_message(NotifyInfoMessage("Copied to clipboard"))

    @on(ModelPushRequested)
    def on_model_push_requested(self, event: ModelPushRequested) -> None:
        """Push requested model event"""
        self.job_queue.put(PushModelJob(modelName=event.model_name))
        self.main_screen.local_view.post_message(
            SetModelNameLoading(event.model_name, True)
        )
        # self.notify(f"Model push {msg.model_name} requested")

    @on(ModelCreateRequested)
    def on_model_create_requested(self, event: ModelCreateRequested) -> None:
        """Create model requested event"""
        self.job_queue.put(
            CreateModelJob(
                modelName=event.model_name,
                modelCode=event.model_code,
                quantizationLevel=event.quantization_level,
            )
        )

    @on(LocalModelDelete)
    def on_local_model_delete(self, event: LocalModelDelete) -> None:
        """Delete local model event"""
        if not dm.delete_model(event.model_name):
            self.main_screen.local_view.post_message(
                SetModelNameLoading(event.model_name, False)
            )
            self.status_notify(
                f"Error deleting model {event.model_name}.", severity="error"
            )
            return
        self.post_message_all(LocalModelDeleted(event.model_name))

    @on(LocalModelDeleted)
    def on_model_deleted(self, event: LocalModelDeleted) -> None:
        """Local model deleted event"""
        self.status_notify(f"Model {event.model_name} deleted.")

    @on(ModelPullRequested)
    def on_model_pull_requested(self, event: ModelPullRequested) -> None:
        """Pull requested model event"""
        self.job_queue.put(PullModelJob(modelName=event.model_name))
        self.post_message_all(SetModelNameLoading(event.model_name, True))

    @on(LocalModelCopyRequested)
    def on_local_model_copy_requested(self, event: LocalModelCopyRequested) -> None:
        """Local model copy request event"""
        self.job_queue.put(
            CopyModelJob(
                modelName=event.src_model_name, dstModelName=event.dst_model_name
            )
        )

    async def do_copy_local_model(self, event: CopyModelJob) -> None:
        """Copy local model"""
        ret = dm.copy_model(event.modelName, event.dstModelName)
        self.main_screen.local_view.post_message(
            LocalModelCopied(
                src_model_name=event.modelName,
                dst_model_name=event.dstModelName,
                success=ret["status"] == "success",
            )
        )

    @on(LocalModelCopied)
    def on_local_model_copied(self, event: LocalModelCopied) -> None:
        """Local model copied event"""
        if event.success:
            self.status_notify(
                f"Model {event.src_model_name} copied to {event.dst_model_name}"
            )
        else:
            self.status_notify(
                f"Copying model {event.src_model_name} to {event.dst_model_name} failed",
                severity="error",
            )

    async def do_progress(self, job: QueueJob, res: Iterator[dict[str, Any]]) -> str:
        """Update progress bar embedded in status bar"""
        try:
            last_status = ""
            for msg in res:
                last_status = msg["status"]
                pb: ProgressBar | None = None
                if "total" in msg and "completed" in msg:
                    msg["percent"] = (
                        str(int(msg["completed"] / msg["total"] * 100)) + "%"
                    )
                    primary_style = Style(
                        color=theme_manager.get_color_system_for_theme_mode(
                            settings.theme_name, self.dark
                        ).primary.rich_color
                    )
                    background_style = Style(
                        color=(
                            theme_manager.get_color_system_for_theme_mode(
                                settings.theme_name, self.dark
                            ).surface
                            or Color.parse("#111")
                        ).rich_color
                    )
                    pb = ProgressBar(
                        total=msg["total"],
                        completed=msg["completed"],
                        width=25,
                        style=background_style,
                        complete_style=primary_style,
                        finished_style=primary_style,
                    )
                else:
                    msg["percent"] = ""
                if msg["percent"] and msg["status"] == "success":
                    msg["percent"] = "100%"
                parts: list[RenderableType] = [
                    Text.assemble(
                        job.modelName,
                        " ",
                        msg["status"],
                        " ",
                        msg["percent"],
                        " ",
                    )
                ]
                if pb:
                    parts.append(pb)

                self.main_screen.post_message(
                    StatusMessage(Columns(parts), log_it=False)
                )
            return last_status
        except ollama.ResponseError as e:
            self.main_screen.post_message(
                StatusMessage(Text.assemble(("error:" + str(e), "red")))
            )
            raise e

    async def do_pull(self, job: PullModelJob) -> None:
        """Pull a model from ollama.com"""
        try:
            res = dm.pull_model(job.modelName)
            last_status = await self.do_progress(job, res)

            self.post_message_all(
                ModelPulled(model_name=job.modelName, success=last_status == "success")
            )
        except ollama.ResponseError:
            self.post_message_all(ModelPulled(model_name=job.modelName, success=False))

    async def do_push(self, job: PushModelJob) -> None:
        """Push a model to ollama.com"""
        try:
            res = dm.push_model(job.modelName)
            last_status = await self.do_progress(job, res)

            self.post_message_all(
                ModelPushed(model_name=job.modelName, success=last_status == "success")
            )
        except ollama.ResponseError:
            self.post_message_all(ModelPushed(model_name=job.modelName, success=False))

    async def do_create_model(self, job: CreateModelJob) -> None:
        """Create a new local model"""
        try:
            self.main_screen.log_view.richlog.write(job.modelCode)
            res = dm.create_model(job.modelName, job.modelCode, job.quantizationLevel)
            last_status = await self.do_progress(job, res)

            self.main_screen.local_view.post_message(
                ModelCreated(
                    model_name=job.modelName,
                    model_code=job.modelCode,
                    quantization_level=job.quantizationLevel,
                    success=last_status == "success",
                )
            )
        except ollama.ResponseError:
            self.main_screen.local_view.post_message(
                ModelCreated(
                    model_name=job.modelName,
                    model_code=job.modelCode,
                    quantization_level=job.quantizationLevel,
                    success=False,
                )
            )

    @work(group="do_jobs", thread=True)
    async def do_jobs(self) -> None:
        """poll for queued jobs"""
        while True:
            try:
                job: QueueJob = self.job_queue.get(block=True, timeout=1)
                if self._exit:
                    return
                if not job:
                    continue
                self.is_busy = True
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
            except Empty:
                if self._exit:
                    return
                if self.is_busy:
                    self.post_message(LocalModelListRefreshRequested(widget=None))
                    self.is_busy = False
                continue

    @on(ModelPulled)
    def on_model_pulled(self, event: ModelPulled) -> None:
        """Model pulled event"""
        if event.success:
            self.status_notify(
                f"Model {event.model_name} pulled.",
            )
        else:
            self.status_notify(
                f"Model {event.model_name} failed to pull.",
                severity="error",
            )

    @on(ModelCreated)
    def on_model_created(self, event: ModelCreated) -> None:
        """Model created event"""
        if event.success:
            self.status_notify(
                f"Model {event.model_name} created.",
            )
            self.set_timer(1, self.action_refresh_models)
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
        """Unregister for updates event"""
        if not event.widget:
            return
        for _, s in self.notify_subs.items():
            s.discard(event.widget)

    @on(AppRequest)
    def on_app_request(self, event: AppRequest) -> None:
        """Add any widget that requests an action to notify_subs"""
        if not event.widget:
            return
        self.notify_subs["*"].add(event.widget)
        if event.__class__.__name__ not in self.notify_subs:
            self.notify_subs[event.__class__.__name__] = set()
        self.notify_subs[event.__class__.__name__].add(event.widget)

    @on(LocalModelListRefreshRequested)
    def on_model_list_refresh_requested(self) -> None:
        """Model refresh request event"""
        if self.is_refreshing:
            self.status_notify("A model refresh is already in progress. Please wait.")
            return
        self.refresh_models()

    @work(group="refresh_models", thread=True)
    async def refresh_models(self):
        """Refresh the models."""
        self.is_refreshing = True
        try:
            self.main_screen.post_message(
                StatusMessage("Local model list refreshing...")
            )
            dm.refresh_models()
            self.main_screen.post_message(StatusMessage("Local model list refreshed"))
            self.main_screen.local_view.post_message(LocalModelListLoaded())
            self.main_screen.chat_view.post_message(LocalModelListLoaded())
        finally:
            self.is_refreshing = False

    @on(LocalModelListLoaded)
    def on_model_data_loaded(self) -> None:
        """Refresh model completed"""
        self.main_screen.post_message(StatusMessage("Local model list refreshed"))
        # self.notify("Local models refreshed.")

    @on(SiteModelsRefreshRequested)
    def on_site_models_refresh_requested(self, msg: SiteModelsRefreshRequested) -> None:
        """Site model refresh request event"""
        if self.is_refreshing:
            self.status_notify("A model refresh is already in progress. Please wait.")
            return
        self.refresh_site_models(msg)

    @on(SiteModelsLoaded)
    def on_site_models_loaded(self) -> None:
        """Site model refresh completed"""
        self.status_notify("Site models refreshed")

    @work(group="refresh_site_model", thread=True)
    async def refresh_site_models(self, msg: SiteModelsRefreshRequested):
        """Refresh the site model."""
        self.is_refreshing = True
        try:
            self.main_screen.post_message(
                StatusMessage(
                    f"Site models for {msg.ollama_namespace or 'models'} refreshing... force={msg.force}"
                )
            )
            dm.refresh_site_models(msg.ollama_namespace, None, msg.force)
            self.main_screen.site_view.post_message(
                SiteModelsLoaded(ollama_namespace=msg.ollama_namespace)
            )
            self.main_screen.post_message(
                StatusMessage(
                    f"Site models for {msg.ollama_namespace or 'models'} loaded. force={msg.force}"
                )
            )

        finally:
            self.is_refreshing = False

    @work(group="update_ps", thread=True)
    async def update_ps(self) -> None:
        """Update ps status bar msg"""
        if not dm.ollama_bin:
            self.notify(
                "Ollama binary not found. PS output not available.",
                severity="error",
                timeout=6,
            )
            return
        was_blank = False
        while self.is_running:
            if settings.ollama_ps_poll_interval < 1:
                self.main_screen.post_message(PsMessage(msg=""))
                break
            await asyncio.sleep(settings.ollama_ps_poll_interval)
            ret = dm.model_ps()
            if not ret:
                if not was_blank:
                    self.main_screen.post_message(PsMessage(msg=""))
                was_blank = True
                continue
            was_blank = False
            info = ret[0]  # only take first one since ps status bar is a single line
            self.main_screen.post_message(
                PsMessage(
                    msg=Text.assemble(
                        "Name: ",
                        info["name"],
                        " Size: ",
                        info["size"],
                        " Processor: ",
                        info["processor"],
                        " Until: ",
                        info["until"],
                    )
                )
            )

    def status_notify(self, msg: str, severity: SeverityLevel = "information") -> None:
        """Show notification and update status bar"""
        self.notify(msg, severity=severity)
        self.main_screen.post_message(StatusMessage(msg))

    def post_message_all(self, msg: Message, sub_name: str = "*") -> None:
        """Post a message to all screens"""
        if isinstance(msg, StatusMessage):
            self.log(msg.msg)
            self.last_status = msg.msg
        if sub_name in self.notify_subs:
            for w in list(self.notify_subs[sub_name]):
                w.post_message(msg)
        if self.main_screen:
            self.main_screen.post_message(msg)

    @on(ChangeTab)
    def on_change_tab(self, event: ChangeTab) -> None:
        """Change tab event"""
        event.stop()
        self.main_screen.change_tab(event.tab)

    @on(CreateModelFromExistingRequested)
    def on_create_model_from_existing_requested(
        self, msg: CreateModelFromExistingRequested
    ) -> None:
        """Create model from existing event"""
        self.main_screen.create_view.name_input.value = f"my-{msg.model_name}:latest"
        self.main_screen.create_view.text_area.text = msg.model_code
        self.main_screen.create_view.quantize_input.value = msg.quantization_level or ""
        self.main_screen.change_tab("Create")
        self.main_screen.create_view.name_input.focus()

    @on(ModelInteractRequested)
    async def on_model_interact_requested(self, event: ModelInteractRequested) -> None:
        """Model interact requested event"""
        self.main_screen.change_tab("Chat")
        self.main_screen.chat_view.active_tab.model_select.value = event.model_name
        await self.main_screen.chat_view.active_tab.action_new_session()
        self.main_screen.chat_view.user_input.focus()

    @on(SessionListChanged)
    def on_session_list_changed(self) -> None:
        """Session list changed event"""
        self.main_screen.chat_view.session_list.post_message(SessionListChanged())

    @on(SessionSelected)
    def on_session_selected(self, event: SessionSelected) -> None:
        """Session selected event"""
        self.main_screen.chat_view.post_message(
            SessionSelected(session_id=event.session_id, new_tab=event.new_tab)
        )

    @on(DeleteSession)
    def on_delete_session(self, event: DeleteSession) -> None:
        """Delete session event"""
        self.main_screen.chat_view.post_message(
            DeleteSession(session_id=event.session_id)
        )
