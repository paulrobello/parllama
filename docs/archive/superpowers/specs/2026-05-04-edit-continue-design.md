# Edit & Continue: Assistant Response Editing with Continuation

## Problem

Users want to stop a model mid-generation, edit the partial response to guide the LLM in a specific direction, then continue generation from the edited text. (GitHub Issue #45)

## Current State

| Capability | Status |
|---|---|
| Stop mid-generation | Done (appends `"\n\nAborted..."`) |
| Edit assistant message via `e` key | Done (saves text, no re-generation) |
| Continue generation from edited text | Missing |

## Design Decisions

1. **Chat continuation** (not text completion API) — works with all providers (Ollama, OpenAI, Anthropic, etc.)
2. **Separate `c` key** to trigger continuation after editing — clear separation between save-only and save+continue
3. **Post-hoc cleanup** — keep existing abort behavior unchanged; strip `"\n\nAborted..."` when continuing

## Changes

### 1. `src/parllama/chat_message.py` — Data Model

Add transient runtime flag to `ParllamaChatMessage`:

```python
_was_aborted: bool = False
```

Not serialized — purely a runtime indicator set during abort.

### 2. `src/parllama/chat_session.py` — Abort Flag

Set `_was_aborted = True` on the message when abort appends `"\n\nAborted..."`. No other changes to abort behavior.

### 3. `src/parllama/widgets/chat_message_widget.py` — New Binding

Add binding on `AgentChatMessage` only:

```python
Binding(key="c", action="continue_generation", description="Continue", show=True)
```

`action_continue_generation`:
1. Check `is_final` — can only continue completed messages (includes both aborted and naturally-finished messages; continuation works on any assistant message, not just aborted ones)
2. Emit `ChatContinueRequested(session_id=self.session.id, message_id=self.msg.id)`

### 4. `src/parllama/messages/chat_messages.py` — New Message

```python
@dataclass
class ChatContinueRequested(SessionMessage):
    message_id: str
```

### 5. `src/parllama/chat_session.py` — Continuation Method

New method `continue_generation(message_id: str) -> bool`:

1. Find message by ID, verify it's an assistant role message
2. Strip trailing `"\n\nAborted..."` from content
3. Remove all messages after the continued message (orphaned context)
4. Build chat history and stream a new assistant response
5. The edited message stays as the last assistant turn; the model continues naturally from it
6. Emit `ChatMessage` events for the new response
7. Return success/failure

### 6. `src/parllama/widgets/views/chat_view.py` — UI Wiring

Add `@on(ChatContinueRequested)` handler that:
1. Gets the active session
2. Calls `session.continue_generation(message_id)` via a worker
3. Updates UI state (busy indicator, stop button enabled)

### 7. Existing Edit Flow — No Changes

The current `e` to edit and Escape to save flow remains unchanged. The user workflow is:

1. Model is generating → user clicks **Stop** (or the model finishes naturally)
2. User presses **e** on the assistant message → edits the text
3. User presses **Escape** → edits are saved
4. User presses **c** → continuation begins from the edited text

## Files Touched

| File | Change |
|---|---|
| `src/parllama/chat_message.py` | Add `_was_aborted` field |
| `src/parllama/chat_session.py` | Set abort flag, add `continue_generation()` |
| `src/parllama/messages/chat_messages.py` | Add `ChatContinueRequested` message |
| `src/parllama/widgets/chat_message_widget.py` | Add `c` binding + action on `AgentChatMessage` |
| `src/parllama/widgets/views/chat_view.py` | Add `@on(ChatContinueRequested)` handler |
