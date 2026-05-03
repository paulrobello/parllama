"""Model job processor extracted from ParLlamaApp.

Handles Ollama model operations: pull, push, copy, create, and the job queue.
"""

from __future__ import annotations

from collections.abc import Iterator
from queue import Empty, Full, Queue
from typing import TYPE_CHECKING

import ollama
from httpx import ConnectError
from ollama import ProgressResponse
from rich.columns import Columns
from rich.console import RenderableType
from rich.progress_bar import ProgressBar
from rich.style import Style
from rich.text import Text
from textual.color import Color

from parllama.messages.messages import (
    LocalModelCopied,
    LocalModelCreated,
    LocalModelPulled,
    LocalModelPushed,
    StatusMessage,
)
from parllama.models.jobs import CopyModelJob, CreateModelJob, PullModelJob, PushModelJob, QueueJob
from parllama.ollama_data_manager import ollama_dm
from parllama.settings_manager import settings

if TYPE_CHECKING:
    from parllama.app import ParLlamaApp
    from parllama.state_manager import AppStateManager


class ModelJobProcessor:
    """Processes model operation jobs (pull, push, copy, create) via a bounded queue.

    This class was extracted from ParLlamaApp to decompose the God Object.  It
    owns the job queue and the actual Ollama interaction logic, while the App
    retains the thin ``@on()`` handlers and ``@work()`` wrappers that Textual
    requires on the application class.
    """

    def __init__(self, app: ParLlamaApp) -> None:
        """Initialize the processor.

        Args:
            app: Reference to the Textual application for message posting,
                 notifications, and logging.
        """
        self._app = app
        self.job_queue: Queue[QueueJob] = Queue[QueueJob](maxsize=settings.job_queue_max_size)
        self._state_manager: AppStateManager = app.state_manager

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def add_job_to_queue(self, job: QueueJob) -> bool:
        """Add a job to the queue with error handling.

        Returns:
            True if the job was added successfully, False if the queue is full.
        """
        try:
            self.job_queue.put(job, timeout=settings.job_queue_put_timeout)
            return True
        except Full:
            self._app.status_notify(
                "Job queue is full. Please wait for current operations to complete.", severity="warning"
            )
            return False

    def get_next_job(self, timeout: float | None = None) -> QueueJob | None:
        """Get the next job from the queue.

        Args:
            timeout: Seconds to wait for a job.  Defaults to
                ``settings.job_queue_get_timeout``.

        Returns:
            The next ``QueueJob``, or ``None`` if the queue is empty after
            the timeout.
        """
        if timeout is None:
            timeout = settings.job_queue_get_timeout
        try:
            return self.job_queue.get(block=True, timeout=timeout)
        except Empty:
            return None

    # ------------------------------------------------------------------
    # Job dispatch (called from App.do_jobs @work wrapper)
    # ------------------------------------------------------------------

    async def process_job(self, job: QueueJob) -> None:
        """Dispatch a single job to the appropriate handler.

        Args:
            job: The job to process.

        Raises:
            ValueError: If the job type is unknown.
        """
        job_type = type(job).__name__
        self._state_manager.set_busy(True, f"processing {job_type}")
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
                raise ValueError(f"Unknown job type {type(job)}")
        finally:
            self._state_manager.set_busy(False, f"completed {job_type}")

    # ------------------------------------------------------------------
    # Progress reporting
    # ------------------------------------------------------------------

    async def do_progress(self, job: QueueJob, res: Iterator[ProgressResponse]) -> str:
        """Update the progress bar embedded in the status bar.

        Args:
            job: The job being processed (used for the model name).
            res: The iterator of progress responses from Ollama.

        Returns:
            The last status string from the progress stream.

        Raises:
            ollama.ResponseError: Re-raised after posting an error status.
        """
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
                    primary_style = Style(color=Color.parse(self._app.current_theme.primary).rich_color)
                    background_style = Style(color=Color.parse(self._app.current_theme.surface or "#111").rich_color)
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

                self._app.post_message_all(StatusMessage(Columns(parts), log_it=False))
            return last_status
        except ollama.ResponseError as e:
            self._app.post_message_all(StatusMessage(Text.assemble(("error:" + str(e), "red"))))
            raise e

    # ------------------------------------------------------------------
    # Model operations
    # ------------------------------------------------------------------

    async def do_pull(self, job: PullModelJob) -> None:
        """Pull a model from ollama.com.

        Args:
            job: The pull job containing the model name.
        """
        try:
            res: Iterator[ProgressResponse] = ollama_dm.pull_model(job.modelName)
            last_status = await self.do_progress(job, res)

            self._app.post_message_all(LocalModelPulled(model_name=job.modelName, success=last_status == "success"))
        except (ollama.ResponseError, ConnectError) as e:
            self.handle_ollama_error("Model pull", job.modelName, e)
            self._app.post_message_all(LocalModelPulled(model_name=job.modelName, success=False))
        except Exception as e:
            self._app.log_it(f"Model pull unexpected error for {job.modelName}: {type(e).__name__}: {e}")
            self.handle_ollama_error("Model pull", job.modelName, e)
            self._app.post_message_all(LocalModelPulled(model_name=job.modelName, success=False))

    async def do_push(self, job: PushModelJob) -> None:
        """Push a model to ollama.com.

        Args:
            job: The push job containing the model name.
        """
        try:
            res: Iterator[ProgressResponse] = ollama_dm.push_model(job.modelName)
            last_status = await self.do_progress(job, res)

            self._app.post_message_all(LocalModelPushed(model_name=job.modelName, success=last_status == "success"))
        except (ollama.ResponseError, ConnectError) as e:
            self.handle_ollama_error("Model push", job.modelName, e)
            self._app.post_message_all(LocalModelPushed(model_name=job.modelName, success=False))
        except Exception as e:
            self._app.log_it(f"Model push unexpected error for {job.modelName}: {type(e).__name__}: {e}")
            self.handle_ollama_error("Model push", job.modelName, e)
            self._app.post_message_all(LocalModelPushed(model_name=job.modelName, success=False))

    async def do_copy_local_model(self, event: CopyModelJob) -> None:
        """Copy a local model.

        Args:
            event: The copy job containing source and destination model names.
        """
        try:
            ret = ollama_dm.copy_model(event.modelName, event.dstModelName)
            self._app.main_screen.local_view.post_message(
                LocalModelCopied(
                    src_model_name=event.modelName,
                    dst_model_name=event.dstModelName,
                    success=ret["status"] == "success",
                )
            )
        except ollama.ResponseError as e:
            self.handle_ollama_error("Model copy", event.modelName, e)
            self._app.main_screen.local_view.post_message(
                LocalModelCopied(
                    src_model_name=event.modelName,
                    dst_model_name=event.dstModelName,
                    success=False,
                )
            )
        except Exception as e:
            self._app.log_it(f"Model copy unexpected error for {event.modelName}: {type(e).__name__}: {e}")
            self.handle_ollama_error("Model copy", event.modelName, e)
            self._app.main_screen.local_view.post_message(
                LocalModelCopied(
                    src_model_name=event.modelName,
                    dst_model_name=event.dstModelName,
                    success=False,
                )
            )

    async def do_create_model(self, job: CreateModelJob) -> None:
        """Create a new local model.

        Args:
            job: The create job containing model parameters.
        """
        success = False
        try:
            self._app.main_screen.log_view.richlog.write(f"Creating model {job.modelName} from {job.modelFrom}...")
            res = ollama_dm.create_model(
                model_name=job.modelName,
                model_from=job.modelFrom,
                system_prompt=job.systemPrompt,
                model_template=job.modelTemplate,
                model_license=job.model_license,
                quantize_level=job.quantizationLevel,
            )
            last_status = await self.do_progress(job, res)
            success = last_status == "success"
        except ollama.ResponseError as e:
            error_msg = self.handle_ollama_error("Model creation", job.modelName, e, custom_handling=True)

            # Check for specific quantization errors
            if "quantization is only supported for F16 and F32 models" in error_msg:
                self._app.status_notify(
                    "Quantization requires F16 or F32 base models. The selected model is already quantized.",
                    severity="error",
                )
            elif "unsupported quantization type" in error_msg:
                self._app.status_notify(
                    "Invalid quantization level. Please use a supported type like q4_K_M, q5_K_M, etc.",
                    severity="error",
                )
            else:
                self._app.status_notify(f"Model creation failed: {error_msg}", severity="error")
        except Exception as e:
            self._app.log_it(f"Model creation unexpected error for {job.modelName}: {type(e).__name__}: {e}")
            self.handle_ollama_error("Model creation", job.modelName, e)

        self._app.main_screen.local_view.post_message(
            LocalModelCreated(
                model_name=job.modelName,
                model_from=job.modelFrom,
                system_prompt=job.systemPrompt,
                model_template=job.modelTemplate,
                model_license=job.model_license,
                quantization_level=job.quantizationLevel,
                success=success,
            )
        )

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def handle_ollama_error(
        self, operation: str, _model_name: str, error: Exception, custom_handling: bool = False
    ) -> str:
        """Handle common Ollama error patterns.

        Args:
            operation: The operation being performed (e.g., "Model copy").
            _model_name: Reserved for future use in error messages.
            error: The exception that occurred.
            custom_handling: If True, only logs but doesn't send notifications.

        Returns:
            The error message string for custom handling.
        """
        if isinstance(error, ollama.ResponseError):
            error_msg = str(error)
            self._app.log_it(f"{operation} failed (ResponseError): {error_msg}")
            if not custom_handling:
                self._app.status_notify(f"{operation} failed: {error_msg}", severity="error")
            return error_msg
        elif isinstance(error, ConnectError):
            error_msg = "Cannot connect to Ollama server"
            self._app.log_it(f"{operation} failed: {error_msg}")
            if not custom_handling:
                self._app.status_notify("Cannot connect to Ollama server. Is it running?", severity="error")
            return error_msg
        else:
            error_msg = str(error)
            self._app.log_it(f"{operation} failed (unexpected error): {type(error).__name__}: {error_msg}")
            if not custom_handling:
                self._app.status_notify(f"{operation} failed: {error_msg}", severity="error")
            return error_msg
