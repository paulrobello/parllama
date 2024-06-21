"""The main application class."""

import asyncio
import inspect
from queue import Empty, Queue
from typing import Any, Dict, Iterator, List

import ollama
import pyperclip  # type: ignore
from rich.columns import Columns
from rich.console import ConsoleRenderable, RenderableType, RichCast
from rich.progress_bar import ProgressBar
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import LogGroup, LogVerbosity, on, work
from textual.app import App
from textual.binding import Binding
from textual.color import Color
from textual.message import Message
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Input, Select, TextArea

from parllama import __application_title__
from parllama.data_manager import dm
from parllama.dialogs.help_dialog import HelpDialog
from parllama.messages.main import (
    LocalModelCopied,
    LocalModelCopyRequested,
    LocalModelDelete,
    LocalModelDeleted,
    LocalModelListLoaded,
    LocalModelListRefreshRequested,
    ModelPulled,
    ModelPullRequested,
    ModelPushed,
    ModelPushRequested,
    NotifyErrorMessage,
    NotifyInfoMessage,
    PsMessage,
    SendToClipboard,
    SiteModelsLoaded,
    SiteModelsRefreshRequested,
    StatusMessage,
)
from parllama.models.jobs import CopyModelJob, PullModelJob, PushModelJob, QueueJob
from parllama.models.settings_data import settings
from parllama.par_logger import ParLogger
from parllama.screens.local_models_screen import LocalModelsScreen
from parllama.screens.log_screen import LogScreen
from parllama.screens.model_tools_screen import ModelToolsScreen
from parllama.screens.site_models_screen import SiteModelsScreen
from parllama.theme_manager import theme_manager


class ParLlamaApp(App[None]):
    """Main application class"""

    TITLE = __application_title__
    BINDINGS = [
        Binding(key="f1", action="help", description="Help", show=True, priority=True),
        Binding(key="ctrl+q", action="app.quit", description="Quit", show=True),
        Binding(
            key="ctrl+l",
            action="app.switch_mode('local')",
            description="Local",
            show=True,
            priority=True,
        ),
        Binding(
            key="ctrl+s",
            action="app.switch_mode('site')",
            description="Site",
            show=True,
            priority=True,
        ),
        Binding(
            key="ctrl+t",
            action="app.switch_mode('tools')",
            description="Tools",
            show=True,
            priority=True,
        ),
        Binding(
            key="ctrl+d",
            action="app.switch_mode('logs')",
            description="Debug",
            show=True,
            priority=True,
        ),
        Binding(
            key="f10",
            action="toggle_dark",
            description="Toggle Dark Mode",
            show=True,
            priority=True,
        ),
        Binding(key="ctrl+c", action="noop", show=False),
    ]
    SCREENS = {}

    MODES = {"local": "local", "site": "site", "tools": "tools", "logs": "logs"}

    commands: list[dict[str, str]] = [
        {
            "action": "action_quit",
            "cmd": "Quit Application",
            "help": "Quit the application as soon as possible",
        }
    ]
    CSS_PATH = "app.tcss"

    DEFAULT_CSS = """
    """

    local_models_screen: LocalModelsScreen
    site_models_screen: SiteModelsScreen
    model_tools_screen: ModelToolsScreen
    log_screen: LogScreen | None
    job_queue: Queue[QueueJob]
    is_busy: bool = False
    last_status: RenderableType = ""

    def __init__(self) -> None:
        """Initialize the application."""
        super().__init__()
        self._logger = ParLogger(self._log)

        self.title = __application_title__
        self.dark = settings.theme_mode != "light"
        self.design = theme_manager.get_theme(settings.theme_name)  # type: ignore
        self.job_queue = Queue[QueueJob]()
        self.is_busy = False
        self.is_refreshing = False
        self.last_status = ""
        self.log_screen = None

    def _watch_dark(self, value: bool) -> None:
        """Watch the dark property."""
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
    def notify_info(self, msg: NotifyInfoMessage) -> None:
        """Show info toast message for 3 seconds"""
        self.notify(msg.message, timeout=3)

    @on(NotifyErrorMessage)
    def notify_error(self, msg: NotifyErrorMessage) -> None:
        """Show error toast message for 6 seconds"""
        self.notify(msg.message, severity="error", timeout=6)

    async def on_mount(self) -> None:
        """Display the main or locked screen."""
        self.SCREENS["local"] = LocalModelsScreen()
        self.SCREENS["site"] = SiteModelsScreen()
        self.SCREENS["tools"] = ModelToolsScreen()
        self.SCREENS["logs"] = LogScreen()

        self._installed_screens.update(**self.SCREENS)

        self.local_models_screen = self.SCREENS["local"]  # type: ignore
        self.site_models_screen = self.SCREENS["site"]  # type: ignore
        self.model_tools_screen = self.SCREENS["tools"]  # type: ignore
        self.log_screen = self.SCREENS["logs"]  # type: ignore

        await self.switch_mode("local")

        self.set_timer(1, self.do_jobs)
        self.set_timer(1, self.update_ps)

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

    def action_copy_to_clipboard(self) -> None:
        """Copy focused widget value to clipboard"""
        f: Widget | None = self.screen.focused
        if not f:
            return

        if isinstance(f, (Input, Select)):
            self.app.post_message(SendToClipboard(str(f.value) if f.value else ""))

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
        if isinstance(f, TextArea):
            pyperclip.copy(f.selected_text or f.text)
            f.text = ""

    @on(SendToClipboard)
    def send_to_clipboard(self, msg: SendToClipboard) -> None:
        """Send string to clipboard"""
        # works for remote ssh sessions
        self.copy_to_clipboard(msg.message)
        # works for local sessions
        pyperclip.copy(msg.message)
        if msg.notify:
            self.post_message(NotifyInfoMessage("Value copied to clipboard"))

    @on(ModelPushRequested)
    def on_model_push_requested(self, msg: ModelPushRequested) -> None:
        """Push requested model event"""
        self.job_queue.put(PushModelJob(modelName=msg.model_name))
        if self.local_models_screen:
            self.local_models_screen.grid.set_item_loading(msg.model_name, True)
        # self.notify(f"Model push {msg.model_name} requested")

        # primary_style = Style(
        #     color=theme_manager.get_color_system_for_theme_mode(
        #         self.theme, self.dark
        #     ).primary.rich_color
        # )
        # background_style = Style(
        #     color=(
        #             theme_manager.get_color_system_for_theme_mode(
        #                 self.theme, self.dark
        #             ).surface

    @on(LocalModelDelete)
    def on_local_model_delete(self, msg: LocalModelDelete) -> None:
        """Delete model event"""
        if not dm.delete_model(msg.model_name):
            if self.local_models_screen:
                self.local_models_screen.grid.set_item_loading(msg.model_name, False)
            self.notify(f"Error deleting model {msg.model_name}.", severity="error")
            return
        if self.local_models_screen:
            self.local_models_screen.post_message(LocalModelDeleted(msg.model_name))

    @on(LocalModelDeleted)
    def on_model_deleted(self, msg: LocalModelDeleted) -> None:
        """Model deleted event"""
        self.notify(f"Model {msg.model_name} deleted.")

    @on(ModelPullRequested)
    def on_model_pull_requested(self, msg: ModelPullRequested) -> None:
        """Pull requested model event"""
        self.job_queue.put(PullModelJob(modelName=msg.model_name))
        if self.local_models_screen:
            self.local_models_screen.grid.set_item_loading(msg.model_name, True)
        # self.notify(f"Model pull {msg.model_name} requested")

        # primary_style = Style(
        #     color=theme_manager.get_color_system_for_theme_mode(
        #         self.theme, self.dark
        #     ).primary.rich_color
        # )
        # background_style = Style(
        #     color=(
        #             theme_manager.get_color_system_for_theme_mode(
        #                 self.theme, self.dark
        #             ).surface
        #             or Color.parse("#111")
        #     ).rich_color
        # )
        # self.screen.post_message(
        #     StatusMessage(
        #         Columns(
        #             [
        #                 Text.assemble("status", " "),
        #                 ProgressBar(
        #                     total=100,
        #                     completed=50,
        #                     width=40,
        #                     style=background_style,
        #                     complete_style=primary_style,
        #                     finished_style=primary_style,
        #                 ),
        #             ]
        #         )
        #     )
        # )

    @on(LocalModelCopyRequested)
    def on_local_model_copy_requested(self, msg: LocalModelCopyRequested) -> None:
        """Local model copy request event"""
        self.job_queue.put(
            CopyModelJob(modelName=msg.src_model_name, dstModelName=msg.dst_model_name)
        )

    async def do_copy_local_model(self, msg: CopyModelJob) -> None:
        """Copy local model"""
        ret = dm.copy_model(msg.modelName, msg.dstModelName)
        self.local_models_screen.post_message(
            LocalModelCopied(
                src_model_name=msg.modelName,
                dst_model_name=msg.dstModelName,
                success=ret["status"] == "success",
            )
        )

    @on(LocalModelCopied)
    def on_local_model_copied(self, msg: LocalModelCopied) -> None:
        """Local model copied event"""
        if msg.success:
            self.notify(f"Model {msg.src_model_name} copied to {msg.dst_model_name}")
        else:
            self.notify(
                f"Copying model {msg.src_model_name} to {msg.dst_model_name} failed",
                severity="error",
            )

    async def do_progress(self, job: QueueJob, res: Iterator[Dict[str, Any]]) -> str:
        """Update progress bar"""
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
                parts: List[RenderableType] = [
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

                self.post_message_all(StatusMessage(Columns(parts)))
            return last_status
        except ollama.ResponseError as e:
            self.post_message_all(
                StatusMessage(Text.assemble(("error:" + str(e), "red")))
            )
            raise e

    async def do_pull(self, job: PullModelJob) -> None:
        """Pull a model"""
        try:
            res = dm.pull_model(job.modelName)
            last_status = await self.do_progress(job, res)

            self.local_models_screen.post_message(
                ModelPulled(model_name=job.modelName, success=last_status == "success")
            )
        except ollama.ResponseError:
            self.post_message_all(ModelPulled(model_name=job.modelName, success=False))

    async def do_push(self, job: PushModelJob) -> None:
        """Push a model"""
        try:
            res = dm.push_model(job.modelName)
            last_status = await self.do_progress(job, res)

            self.post_message_all(
                ModelPushed(model_name=job.modelName, success=last_status == "success")
            )
        except ollama.ResponseError:
            self.post_message_all(ModelPushed(model_name=job.modelName, success=False))

    @work(group="do_jobs", thread=True)
    async def do_jobs(self) -> None:
        """Pull all requested models in queue"""
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
                else:
                    self.notify(f"Unknown job type {type(job)}", severity="error")
            except Empty:
                if self._exit:
                    return
                if self.is_busy:
                    self.post_message(LocalModelListRefreshRequested())
                    self.is_busy = False
                continue

    @on(ModelPulled)
    def on_model_pulled(self, msg: ModelPulled) -> None:
        """Model pulled event"""
        if msg.success:
            self.notify(f"Model {msg.model_name} pulled.")
        else:
            self.notify(f"Model {msg.model_name} failed to pull.", severity="error")

    def action_refresh_models(self):
        """Refresh models action."""
        self.refresh_models()

    @on(LocalModelListRefreshRequested)
    def on_model_list_refresh_requested(self) -> None:
        """Model refresh request event"""
        if self.is_refreshing:
            self.notify("A model refresh is already in progress. Please wait.")
            return
        self.refresh_models()

    @work(group="refresh_models", thread=True)
    async def refresh_models(self):
        """Refresh the models."""
        self.is_refreshing = True
        try:
            self.post_message_all(StatusMessage("Local model list refreshing..."))
            dm.refresh_models()
            self.screen.post_message(LocalModelListLoaded())
        finally:
            self.is_refreshing = False

    @on(LocalModelListLoaded)
    def on_model_data_loaded(self) -> None:
        """Refresh model completed"""
        self.post_message_all(StatusMessage("Local model list refreshed"))
        # self.notify("Local models refreshed.")

    @on(SiteModelsRefreshRequested)
    def on_site_models_refresh_requested(self, msg: SiteModelsRefreshRequested) -> None:
        """Site model refresh request event"""
        if self.is_refreshing:
            self.notify("A model refresh is already in progress. Please wait.")
            return
        self.refresh_site_models(msg)

    @on(SiteModelsLoaded)
    def on_site_models_loaded(self, msg: SiteModelsLoaded) -> None:
        """Site model refresh completed"""
        self.notify(f"Site models refreshed for {msg.ollama_namespace or 'models'}")

    @work(group="refresh_site_model", thread=True)
    async def refresh_site_models(self, msg: SiteModelsRefreshRequested):
        """Refresh the site model."""
        self.is_refreshing = True
        try:
            self.post_message_all(
                StatusMessage(
                    f"Site models for {msg.ollama_namespace or 'models'} refreshing... force={msg.force}"
                )
            )
            dm.refresh_site_models(msg.ollama_namespace, msg.force)
            self.screen.post_message(
                SiteModelsLoaded(ollama_namespace=msg.ollama_namespace)
            )
            self.post_message_all(
                StatusMessage(
                    f"Site models for {msg.ollama_namespace or 'models'} loaded. force={msg.force}"
                )
            )

        finally:
            self.is_refreshing = False

    @work(group="update_ps", thread=True)
    async def update_ps(self) -> None:
        """Update ps msg"""
        was_blank = False
        while self.is_running:
            await asyncio.sleep(1)
            ret = dm.model_ps()
            if not ret:
                if not was_blank:
                    self.screen.post_message(PsMessage(msg=""))
                was_blank = True
                continue
            was_blank = False
            info = ret[0]
            self.local_models_screen.post_message(
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
        self.post_message_all(StatusMessage(msg="exited..."))

    def post_message_all(self, msg: Message) -> None:
        """Post a message to all screens"""
        if isinstance(msg, StatusMessage):
            self.log(msg.msg)
            self.last_status = msg.msg

        if self.local_models_screen:
            self.local_models_screen.post_message(msg)
        if self.site_models_screen:
            self.site_models_screen.post_message(msg)

    def _log(
        self,
        group: LogGroup,
        verbosity: LogVerbosity,
        _textual_calling_frame: inspect.Traceback,
        *objects: Any,
        **kwargs,
    ) -> None:
        """Write to logs or devtools.

        Positional args are logged. Keyword args will be prefixed with the key.

        Example:
            ```python
            data = [1,2,3]
            self.log("Hello, World", state=data)
            self.log(self.tree)
            self.log(locals())
            ```

        Args:
            verbosity: Verbosity level 0-3.
        """

        if self.log_screen and self.log_screen.richlog:
            if len(objects) == 1:
                types_to_check = [ConsoleRenderable, RichCast, str]
                renderable: RenderableType | None = None
                if isinstance(objects[0], Columns):
                    renderable = objects[0].renderables[0]
                else:
                    # make sure we have a renderable type
                    for ttc in types_to_check:
                        if isinstance(objects[0], ttc):
                            renderable = objects[0]  # type: ignore
                            break
                if renderable:
                    # dont log duplicate messages
                    if len(self.log_screen.richlog.lines) > 0:
                        if (
                            Strip.from_lines(
                                list(
                                    Segment.split_lines(self.console.render(renderable))
                                )
                            )[0].text
                            != self.log_screen.richlog.lines[-1].text
                        ):
                            self.log_screen.richlog.write(renderable)
                            return
                    else:
                        self.log_screen.richlog.write(renderable)
                        return

        super()._log(group, verbosity, _textual_calling_frame, *objects, **kwargs)
