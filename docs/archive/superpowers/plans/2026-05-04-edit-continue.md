# Edit & Continue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to edit an assistant message and continue generation from the edited text using the `c` key, working with all LLM providers.

**Architecture:** Chat continuation — the edited assistant message stays in history as the last assistant turn. A new `continue_generation` method on `ChatSession` streams a new assistant response from the model, which naturally continues from the prior assistant message. A new `ChatContinueRequested` message connects the widget action to the session logic.

**Tech Stack:** Python, Textual TUI, LangChain `BaseChatModel.stream()`, existing message passing system.

---

### Task 1: Add `_was_aborted` flag to `ParllamaChatMessage`

**Files:**
- Modify: `src/parllama/chat_message.py:74-91`

- [ ] **Step 1: Add `_was_aborted` field and initialization**

In `src/parllama/chat_message.py`, add the transient runtime flag to the `__init__` method after `self.tool_calls = tool_calls` (line 91):

```python
        self._was_aborted = False
```

The full `__init__` becomes:

```python
    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        id: str | None = None,  # pylint: disable=redefined-builtin
        role: MessageRoles,
        content: str = "",
        thinking: str = "",
        images: list[str] | None = None,
        tool_calls: Sequence[ToolCall] | None = None,
    ) -> None:
        """Initialize the chat message"""
        super().__init__(id=id)
        self.parent: Any | None = None
        self.role = role
        self.content = content
        self.thinking = thinking
        self.images = images
        self.tool_calls = tool_calls
        self._was_aborted = False

        if self.images:
            image = self.images[0]
            if not image.startswith("data:"):
                image_type = try_get_image_type(image)
                image = image_to_base64(fetch_and_cache_image(image)[1], image_type)
                self.images[0] = image
```

- [ ] **Step 2: Verify `make checkall` passes**

Run: `make checkall`
Expected: PASS (no new code paths exercised by type checker, just an attribute assignment)

- [ ] **Step 3: Commit**

```bash
git add src/parllama/chat_message.py
git commit -m "feat(chat): add _was_aborted flag to ParllamaChatMessage"
```

---

### Task 2: Set `_was_aborted` flag during abort in `ChatSession.send_chat`

**Files:**
- Modify: `src/parllama/chat_session.py:383-393`

- [ ] **Step 1: Add `_was_aborted = True` in the abort block**

In `src/parllama/chat_session.py`, inside the `if self._abort:` block (around line 384), add `msg._was_aborted = True` right after `is_aborted = True`:

Change from:
```python
                    if self._abort:
                        is_aborted = True
                        try:
                            msg.content += "\n\nAborted..."
```

To:
```python
                    if self._abort:
                        is_aborted = True
                        msg._was_aborted = True
                        try:
                            msg.content += "\n\nAborted..."
```

- [ ] **Step 2: Verify `make checkall` passes**

Run: `make checkall`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/parllama/chat_session.py
git commit -m "feat(chat): set _was_aborted flag when generation is aborted"
```

---

### Task 3: Add `ChatContinueRequested` message

**Files:**
- Modify: `src/parllama/messages/chat_messages.py:13-15`
- Modify: `src/parllama/messages/messages.py:20-32,119-165`

- [ ] **Step 1: Add `ChatContinueRequested` to `chat_messages.py`**

In `src/parllama/messages/chat_messages.py`, add after the `ChatGenerationAborted` class (after line 19):

```python
@dataclass
class ChatContinueRequested(SessionMessage):
    """Request to continue generation from an edited assistant message."""

    message_id: str
    """ID of the assistant message to continue from."""
```

- [ ] **Step 2: Export `ChatContinueRequested` from the barrel file**

In `src/parllama/messages/messages.py`:

1. Add to the import block from `chat_messages` (around line 21-32), add `ChatContinueRequested` to the import list:

```python
from parllama.messages.chat_messages import (
    ChatContinueRequested,
    ChatGenerationAborted,
    ChatMessage,
    ChatMessageDeleted,
    ChatMessageSent,
    ClearChatInputHistory,
    HistoryNext,
    HistoryPrev,
    StopChatGeneration,
    ToggleInputMode,
    UpdateChatControlStates,
    UpdateChatStatus,
)
```

2. Add to the `__all__` list (around line 119-165), in the Chat section:

```python
    # Chat
    "ChatContinueRequested",
    "ChatGenerationAborted",
```

- [ ] **Step 3: Verify `make checkall` passes**

Run: `make checkall`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/parllama/messages/chat_messages.py src/parllama/messages/messages.py
git commit -m "feat(chat): add ChatContinueRequested message class"
```

---

### Task 4: Add `continue_generation` method to `ChatSession`

**Files:**
- Modify: `src/parllama/chat_session.py:661-663`

- [ ] **Step 1: Add the `continue_generation` method**

In `src/parllama/chat_session.py`, add after the `stop_generation` method (after line 663). First, add `ChatContinueRequested` to the imports from `parllama.messages.messages` at the top of the file (around line 23-30). Add it to the existing import:

```python
from parllama.messages.messages import (
    ChatContinueRequested,
    ChatGenerationAborted,
    ChatMessage,
    DeleteSession,
    SessionAutoNameRequested,
    SessionChanges,
    SessionUpdated,
)
```

Then add the method after `stop_generation`:

```python
    async def continue_generation(self, message_id: str) -> bool:
        """Continue generation from an edited assistant message.

        Strips any trailing 'Aborted...' text from the message, removes
        any messages that follow it, and streams a new assistant response.
        """
        if self._generating:
            return False

        msg = self[message_id]
        if msg is None or msg.role != "assistant":
            return False

        # Strip abort suffix if present
        if msg.content.endswith("\n\nAborted..."):
            msg.content = msg.content[: -len("\n\nAborted...")]
            msg._was_aborted = False

        # Remove all messages after the continued message
        idx = next((i for i, m in enumerate(self.messages) if m.id == message_id), -1)
        if idx == -1:
            return False

        removed_ids = [m.id for m in self.messages[idx + 1 :]]
        self.messages = self.messages[: idx + 1]
        for rid in removed_ids:
            if rid in self._id_to_msg:
                del self._id_to_msg[rid]
                self._emit(ChatMessageDeleted(parent_id=self.id, message_id=rid))

        self._changes.add("messages")
        self.save()

        # Stream a new assistant response
        self._generating = True
        is_aborted = False
        new_msg: ParllamaChatMessage | None = None
        try:
            self._ensure_memory_injection()

            num_tokens: int = 0
            start_time = datetime.now(UTC)
            ttft: float = 0.0

            chat_history = [m.to_langchain_native() for m in self.messages]
            chat_model = self._llm_config.build_chat_model()

            stream: Iterator[BaseMessageChunk] = chat_model.stream(
                chat_history,  # type: ignore
                config=llm_run_manager.get_runnable_config(chat_model.name or ""),
            )
            new_msg = ParllamaChatMessage(role="assistant")
            self.add_message(new_msg)
            self._emit(ChatMessage(parent_id=self.id, message_id=new_msg.id))
            try:
                for chunk in stream:
                    elapsed_time = datetime.now(UTC) - start_time
                    if chunk.content:
                        if num_tokens == 0:
                            ttft = elapsed_time.total_seconds()
                        num_tokens += 1
                        if isinstance(chunk.content, str):
                            new_msg.content += chunk.content
                        elif isinstance(chunk.content, list):
                            if len(chunk.content) > 0:
                                part: str | dict[str, Any] = chunk.content[0]
                                if isinstance(part, str):
                                    new_msg.content += part
                                else:
                                    part_type: str = "?"
                                    if "type" in part:
                                        part_type = part["type"]
                                    if part_type == "text" and part_type in part:
                                        new_msg.content += part[part_type]
                                    if part_type.startswith("think") and part_type in part:
                                        new_msg.thinking += part[part_type]

                    if self._abort:
                        is_aborted = True
                        try:
                            new_msg.content += "\n\nAborted..."
                            new_msg._was_aborted = True
                            self._emit(ChatGenerationAborted(self.id))
                            stream.close()  # type: ignore
                        except (OSError, ValueError):  # pylint:disable=broad-exception-caught
                            pass
                        finally:
                            self._abort = False
                        break

                    if (
                        hasattr(chunk, "usage_metadata") and chunk.usage_metadata  # pyright: ignore [reportAttributeAccessIssue]
                    ):
                        usage_metadata = chunk.usage_metadata  # pyright: ignore [reportAttributeAccessIssue]
                        self._stream_stats = TokenStats(
                            model=self._llm_config.model_name,
                            created_at=datetime.now(),
                            total_duration=int(elapsed_time.total_seconds()),
                            load_duration=0,
                            prompt_eval_count=usage_metadata["input_tokens"],
                            prompt_eval_duration=0,
                            eval_count=usage_metadata["output_tokens"],
                            eval_duration=int(elapsed_time.total_seconds() - ttft),
                            input_tokens=usage_metadata["input_tokens"],
                            output_tokens=usage_metadata["output_tokens"],
                            total_tokens=usage_metadata["total_tokens"],
                            time_til_first_token=int(ttft),
                        )
                    if hasattr(chunk, "response_metadata"):
                        if "model" in chunk.response_metadata:
                            self._stream_stats = TokenStats(
                                model=chunk.response_metadata.get("model") or "?",
                                created_at=chunk.response_metadata.get("created_at") or datetime.now(),
                                total_duration=chunk.response_metadata.get("total_duration") or 0,
                                load_duration=chunk.response_metadata.get("load_duration") or 0,
                                prompt_eval_count=chunk.response_metadata.get("prompt_eval_count") or 0,
                                prompt_eval_duration=chunk.response_metadata.get("prompt_eval_duration") or 0,
                                eval_count=chunk.response_metadata.get("eval_count") or 0,
                                eval_duration=int(chunk.response_metadata.get("eval_duration", 0) / 1_000_000_000) or 0,
                                input_tokens=0,
                                output_tokens=0,
                                total_tokens=0,
                                time_til_first_token=int(ttft),
                            )
                    self._emit(ChatMessage(parent_id=self.id, message_id=new_msg.id, is_final=not chunk.content))
            except Exception as e:
                self.log_it(f"Stream error ({type(e).__name__}): {e}")
                self.log_it("Error generating message", notify=True, severity="error")
                if new_msg is not None:
                    err_msg = self._parse_llm_error(str(e))
                    new_msg.content += f"\n\n{err_msg}"
                    new_msg.content = new_msg.content.strip()

            self._changes.add("messages")
            self.save()

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log_it(f"Continue generation error ({type(e).__name__}): {e}")
            self.log_it("Error generating message", notify=True, severity="error")
            if new_msg is not None:
                err_msg = self._parse_llm_error(str(e))
                new_msg.content += f"\n\n{err_msg}"
                new_msg.content = new_msg.content.strip()
                self._changes.add("messages")
                self.save()
                self._emit(ChatMessage(parent_id=self.id, message_id=new_msg.id, is_final=True))
                return False
        finally:
            self._generating = False

        return not is_aborted
```

Note: This method mirrors `send_chat` but skips the user message insertion — it sends the existing conversation history (ending with the edited assistant message) directly to the model, so the model naturally continues from where the assistant left off.

- [ ] **Step 2: Verify `make checkall` passes**

Run: `make checkall`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/parllama/chat_session.py
git commit -m "feat(chat): add continue_generation method to ChatSession"
```

---

### Task 5: Add `c` keybinding and action to `AgentChatMessage`

**Files:**
- Modify: `src/parllama/widgets/chat_message_widget.py:280-291`

- [ ] **Step 1: Add import for `ChatContinueRequested`**

At the top of `src/parllama/widgets/chat_message_widget.py`, update the import from `parllama.messages.messages` (line 24) to include `ChatContinueRequested`:

Change:
```python
from parllama.messages.messages import ExecuteMessageRequested, SendToClipboard
```

To:
```python
from parllama.messages.messages import ChatContinueRequested, ExecuteMessageRequested, SendToClipboard
```

- [ ] **Step 2: Add binding and action to `AgentChatMessage`**

In `src/parllama/widgets/chat_message_widget.py`, replace the `AgentChatMessage` class (lines 280-291) with:

```python
class AgentChatMessage(ChatMessageWidget):
    """Agent chat message widget"""

    BINDINGS = [
        Binding(key="c", action="continue_generation", description="Continue", show=True),
    ]

    DEFAULT_CSS = """
    AgentChatMessage {
        background: $panel;
        border-title-align: right;
    }
    AgentChatMessage:light {
        background: #ccc;
    }
    """

    async def action_continue_generation(self) -> None:
        """Continue generation from this assistant message."""
        if not self.is_final:
            self.notify("Only completed messages can be continued", severity="error")
            return
        if self.session.is_generating:
            self.notify("LLM is busy", severity="error")
            return
        self.app.post_message(ChatContinueRequested(session_id=self.session.id, message_id=self.msg.id))
```

- [ ] **Step 3: Verify `make checkall` passes**

Run: `make checkall`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/parllama/widgets/chat_message_widget.py
git commit -m "feat(chat): add 'c' continue keybinding to AgentChatMessage"
```

---

### Task 6: Wire up `ChatContinueRequested` handler in `ChatTab`

**Files:**
- Modify: `src/parllama/widgets/views/chat_tab.py:440-450`

- [ ] **Step 1: Add import for `ChatContinueRequested`**

At the top of `src/parllama/widgets/views/chat_tab.py`, add `ChatContinueRequested` to the imports from `parllama.messages.messages`. Find the existing import and add `ChatContinueRequested`:

```python
from parllama.messages.messages import ChatContinueRequested, ChatMessageSent
```

- [ ] **Step 2: Add `do_continue_generation` worker method and handler**

In `src/parllama/widgets/views/chat_tab.py`, add after the `on_chat_message_sent` method (after line 450):

```python
    @work(thread=True, name="msg_continue_worker")
    async def do_continue_generation(self, message_id: str) -> None:
        """Continue generation from an edited assistant message."""
        self.busy = True
        await self.session.continue_generation(message_id)
        self.post_message(ChatMessageSent(self.session.id))

    @on(ChatContinueRequested)
    async def on_chat_continue_requested(self, event: ChatContinueRequested) -> None:
        """Handle continue generation request."""
        event.stop()
        if self.session.id != event.session_id:
            return
        if self.busy:
            self.notify("LLM is busy", severity="error")
            return
        self.do_continue_generation(event.message_id)
```

- [ ] **Step 3: Verify `make checkall` passes**

Run: `make checkall`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/parllama/widgets/views/chat_tab.py
git commit -m "feat(chat): wire up ChatContinueRequested handler in ChatTab"
```

---

### Task 7: Wire up `ChatContinueRequested` in `ChatView` for stop button

**Files:**
- Modify: `src/parllama/widgets/views/chat_view.py:841-845`

- [ ] **Step 1: Add `ChatContinueRequested` to imports**

At the top of `src/parllama/widgets/views/chat_view.py`, find the import block from `parllama.messages.messages` (around line 29) and add `ChatContinueRequested`:

```python
    ChatContinueRequested,
    ChatGenerationAborted,
```

- [ ] **Step 2: Add handler for `ChatContinueRequested`**

In `src/parllama/widgets/views/chat_view.py`, add after the `on_chat_generation_aborted` handler (after line 845):

```python
    @on(ChatContinueRequested)
    def on_chat_continue_requested(self, event: ChatContinueRequested) -> None:
        """Handle continue generation request."""
        event.stop()
        if self.session.id != event.session_id:
            return
        self.stop_button.disabled = False
```

- [ ] **Step 3: Verify `make checkall` passes**

Run: `make checkall`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/parllama/widgets/views/chat_view.py
git commit -m "feat(chat): wire up stop button for ChatContinueRequested in ChatView"
```

---

## Self-Review

**Spec coverage:**
1. `_was_aborted` flag → Task 1 + Task 2 ✅
2. `ChatContinueRequested` message → Task 3 ✅
3. `c` binding on `AgentChatMessage` → Task 5 ✅
4. `continue_generation` method → Task 4 ✅
5. UI wiring in `ChatTab` → Task 6 ✅
6. UI wiring in `ChatView` (stop button) → Task 7 ✅
7. Post-hoc cleanup (strip abort text) → Task 4 (inside `continue_generation`) ✅

**Placeholder scan:** No TBDs, TODOs, or vague steps. All code shown inline.

**Type consistency:**
- `ChatContinueRequested(session_id=..., message_id=...)` used consistently in Task 5 (emission) and Task 6/7 (handling) ✅
- `_was_aborted` is `bool`, set to `True` in Task 2, checked and reset in Task 4 ✅
- `continue_generation(message_id: str) -> bool` matches Task 4 definition and Task 6 call site ✅
- `ChatMessageDeleted` import exists in `chat_session.py` already via `messages.py` barrel ✅
