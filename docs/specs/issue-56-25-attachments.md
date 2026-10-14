# Spec: Unified Attachment System (Issues #56 + #25)

**Status:** Draft for review — not yet approved for implementation
**Covers:** [#56 Add support for pdf](https://github.com/paulrobello/par-llama/issues/56), [#25 Add insert image and document option](https://github.com/paulrobello/par-llama/issues/25)
**Grounded against:** parllama @ `05917f1` (v0.9.2)

## 1. Problem statements

**#56 (part A — PDF upload):** Users want to upload and interact with PDFs directly in Parllama: attach one or more PDFs, ask questions about them, and keep them in the conversation context.

**#56 (part B — chat history fidelity):** Users report the model "forgets" context provided earlier (names, facts). Full history *is* resent every turn, but fidelity is lost in `to_langchain_native()` conversion (see F2/F3 below), which is the user-visible symptom this issue describes.

**#25 (insert image/document):** Users want an insert option for images and documents in chat (as oterm has), not only a typed slash command. The issue notes vision LLMs are "unusable due to this reason" — attaching an image should be a first-class UI action.

These pair naturally: one attachment pipeline covering images and documents, with both slash-command and file-picker entry points.

## 2. Current state (verified)

- Messages are `ParllamaChatMessage` (`src/parllama/chat_message.py`): `role`, `content`, `thinking`, `images: list[str] | None`, `tool_calls`. Only `images` exists; there is no document concept.
- Full history is sent every turn: `chat_session.py:554` (`send_chat`) and `:895` (`continue_generation`) build `[m.to_langchain_native() for m in self.messages]` and stream it.
- Image entry point today: `/add.image PATH_OR_URL PROMPT` (`widgets/views/chat_view.py:567`, registered at `:630` in `_PREFIX_COMMANDS`). No file picker, no paste, no document support.
- Image handling is single-image: `ParllamaChatMessage.__init__` (`chat_message.py:93-98`) and `to_langchain_native` (`chat_message.py:123-144`) encode/send **only `images[0]`**; additional images are silently dropped.
- File validation: `validators/file_validator.py` (extension whitelist, size caps, content sniffing, zip-bomb ratio). No `.pdf` extension, no PDF content validation.
- Settings: `settings/config_groups.py` `FileValidationSettings` — `max_image_size_mb: 50.0`, `allowed_image_extensions` includes `.webp`, `.bmp`.
- `textual-fspicker` is already a dependency (file picker dialogs available with no new deps).
- Providers come from `par_ai_core` `LlmConfig.build_chat_model()` → LangChain chat models (langchain-core ≥1.4.8). `par_ai_core` has no document/file-part helpers today (only `llm_image_utils.py`).

### Findings (bugs surfaced by grounding, fixed by this work)

- **F1 — extension mismatch:** `try_get_image_type` (`chat_message.py:18-30`) accepts only `jpeg/png/gif`, but `allowed_image_extensions` whitelists `.webp/.bmp`. A webp passes validation, then `to_langchain_native` catches the `ValueError` and **replaces the entire message content with the error string** (`chat_message.py:133-134`). User message silently destroyed.
- **F2 — multi-image drop:** only `images[0]` is ever sent (F-fidelity bug; the same message can never carry 2+ images usefully).
- **F3 — error clobbering:** any image-conversion failure replaces `msg.content` with the exception text instead of the user's text.
- **F4 — `to_ollama_native` drops images entirely** (`chat_message.py:119-121`); harmless today (Ollama goes through the LangChain path) but a trap.

## 3. Goals / Non-goals

**Goals**

1. G1: Attach one or more PDFs to a chat message; full text (native file part or extracted) reaches the model.
2. G2: Provider-aware routing: native document content parts where the provider supports them; client-side text-extraction fallback everywhere else.
3. G3: First-class attach UI: keybinding + file picker for images and documents (#25), alongside new slash commands.
4. G4: History fidelity (#56 part B): all images (not just the first), documents, and tool_calls are represented in what is sent to the provider; no error-string clobbering (F1-F3).
5. G5: Security parity: PDFs go through `FileValidator` (extension, size, content header, page-count cap) and `SecureFileOperations`.
6. G6: Backward compatibility: existing session JSON loads unchanged; old messages render and resend as before (minus the bugs).

**Non-goals (v1)**

- OCR of scanned/image-only PDFs (would add a tesseract dependency; surfaced as open question Q4).
- RAG/embedding of documents (the RAG tab is a separate effort).
- Document formats beyond PDF in v1 for *native* routing; `.txt`/`.md` ride the trivial extraction path (they are plain text — near-zero cost to include).
- Modifying `par_ai_core` (keep everything parllama-side; upstreaming helpers is a follow-up, Q6).

## 4. Design

### 4.1 Data model — `ParllamaChatMessage`

Add a `documents` field alongside `images` (keep `images` as-is for JSON back-compat):

```python
@dataclass
class DocumentAttachment:
    name: str            # display name / original filename
    mime_type: str       # "application/pdf", "text/plain", "text/markdown"
    size_bytes: int
    data_b64: str | None # raw file bytes, base64 (native providers)
    text: str | None     # extracted text (fallback providers + display)
    num_pages: int | None
```

- `ParllamaChatMessage.__init__` gains `documents: list[dict] | None = None` (dicts → `DocumentAttachment`; keeps `ParllamaChatMessage(**m)` session loading working, `chat_session.py:157`).
- `to_dict()` includes `documents`; absent key in old JSON → `None` → unchanged behavior.
- `__str__` (markdown export) renders `[Document: name (N pages)]`.
- Unlike images (inlined to data-URLs at construction, `chat_message.py:93-98`), documents are **not** eagerly decoded: `data_b64`/`text` are populated by the attach pipeline (4.4) so message construction stays cheap and loading old sessions does no I/O.

### 4.2 Provider routing

New module `src/parllama/attachment_utils.py`:

```python
PROVIDER_NATIVE_DOCUMENTS: dict[LlmProvider, bool]  # capability map
def build_document_content_block(doc, provider) -> dict  # native part
def documents_as_text(docs) -> str                   # fallback block
def estimate_document_tokens(doc) -> int             # see §6
```

| Provider | v1 route | Notes |
|---|---|---|
| Anthropic | Native | `{"type": "file", "source_type": "base64", "data": ..., "mime_type": "application/pdf"}` (langchain-anthropic document block) |
| OpenAI | Native | file content part (gpt-4o/4.1/o-series; PDF) |
| Gemini | Native | `inline_data` application/pdf (Gemini 1.5+) |
| OpenRouter, GitHub, Azure | Extraction | aggregator/upstream variance; extraction is always correct, native is a follow-up |
| Ollama, LLAMACPP, Groq, xAI, DeepSeek, Mistral, LiteLLM, Bedrock | Extraction | no stable PDF input API |

Native-vs-fallback is decided per message at send time, not persisted — a session can switch providers and documents still work (extraction always available because we keep `text` alongside `data_b64`).

### 4.3 History fidelity fixes (#56 part B)

`to_langchain_native()` (`chat_message.py:123-144`) reworked:

1. Emit **all** images as `image_url` parts, not `images[0]` (F2).
2. Extend `try_get_image_type` to accept `webp`/`bmp` → `image_url` data-URLs (F1). (Check what Ollama/vision models actually accept at impl time; if webp is rejected by a provider, that's a provider error surfaced to the user — not a silently-destroyed message.)
3. On conversion failure, keep the original `content` text and surface the error via a notify/log — never replace `content` with the exception string (F3).
4. Append document parts: native file block per provider, or a fenced text block:
   ```
   <document name="report.pdf">
   …extracted text…
   </document>
   ```
5. `to_ollama_native()` is left alone (F4 noted, unused path; out of scope).
6. `thinking` remains excluded from what is sent (existing documented constraint, `chat_message.py:135-140`); tool_calls inclusion is a separate concern — **not** changed in this work (touched only if trivially safe in the same function; default: no behavior change).

`check_consecutive_messages` (`chat_session.py:963`) gains `documents` merging alongside `images` (same pattern).

### 4.4 Attach pipeline

`attach_file(path_or_url, role_message)` in `attachment_utils.py`:

1. **Validate** via `FileValidator` with new settings (§4.5): extension whitelist, size cap, `%PDF-` magic-header check, encrypted-PDF detection (fail with actionable error: "password-protected PDFs are not supported"), page-count cap.
2. **Extract** (pypdf) text + page count immediately for all providers (needed for token estimates and fallback); store `data_b64` only when file is within the size cap for native send.
3. **Cache** extracted text in `~/.cache/parllama/documents/` keyed by content hash, mirroring `fetch_and_cache_image` in `settings_manager.py`.
4. Return the `DocumentAttachment` for the caller to put on the message.

New dependency: `pypdf>=5` (pure Python, MIT). No other new deps.

### 4.5 Settings (Options → File Security section)

`FileValidationSettings` (`settings/config_groups.py`) additions:

```python
max_document_size_mb: float = 32.0
allowed_document_extensions: list[str] = [".pdf", ".txt", ".md"]
max_pdf_pages: int = 500
max_extracted_text_chars: int = 500_000   # hard stop for extraction output
```

All surfaced in the Options view next to the existing file-validation controls.

### 4.6 UI (#25)

1. **Keybinding `ctrl+p` on the chat input** ("Attach file") opens a `textual-fspicker` `FileDialog` filtered to images + documents. Selected file → validation → pending-attachment chip row above the input (name, type, size, remove with `ctrl+x` on chip). On submit, chips attach to the outgoing user message. This is the "insert option" #25 asks for.
2. **Slash commands**, mirroring `/add.image`:
   - `/add.doc PATH_OR_URL PROMPT` — attach + send (same arg-parsing shape as `_cmd_add_image_arg`, `chat_view.py:567`).
   - `/attach` — opens the same file picker with no send.
   - `/add.image` unchanged (but now supports multiple calls before submit, since F2 is fixed).
3. **Rendering:** `ChatMessageWidget` shows attachments as a header row: `[📄 report.pdf · 12 pages · ~9k tokens]`. Images render as today. Markdown export includes document markers (§4.1).
4. **help.md + README:** document keybinding and both commands; README "What's New" entry on release (per repo version policy — only when version is bumped).

### 4.7 Persistence & compatibility

- Session JSON gains `documents` per message; `ChatSession.load`/`from_json` need no structural change (`ParllamaChatMessage(**m)` tolerates the new key; old files lack it → `None`).
- Document bytes/text live in the session JSON (bounded by `max_document_size_mb` / `max_extracted_text_chars` — at defaults that's up to ~32 MB JSON per attachment worst case; acceptable per-message, and the page/text caps bound the common case. Open question Q2 proposes a cache-reference optimization if session size becomes a complaint).

## 5. Security review checklist

- All reads through `FileValidator` + `SecureFileOperations` (no raw `open()` of user paths).
- PDF parsing (pypdf) runs on validated, size-capped files only; pypdf decompression bombs are bounded by `max_pdf_pages` + `max_extracted_text_chars` (analog of the zip-ratio check).
- No new network fetches beyond the existing image-URL path (`http_validator.py` applies if document URLs are allowed in v1 — default: **local files only** for documents, URL support is Q5).
- Filename sanitization already applies via validator settings.

## 6. Token/cost guardrails

- `estimate_document_tokens`: PDF ≈ 1,600 tokens/page (Anthropic's published approximation) for native; extracted text ≈ chars/4.
- Before send: if estimated prompt tokens exceed `num_ctx` (Ollama/LLAMACPP) or a fixed warn threshold (default 100k) for cloud providers, notify the user and require confirmation to proceed (same confirm pattern as other destructive/expensive actions).
- Per-message attachment cap: images ≤ 5, documents ≤ 3 (constants, not settings, in v1).

## 7. Implementation phases

Each phase ends with `make checkall` green and an atomic commit. Tests use pytest (`make test`); provider tests mock chat models (no network).

| Phase | Scope | Verify |
|---|---|---|
| 1 | Fidelity fixes F1–F3 in `chat_message.py` (multi-image, webp/bmp, no error clobber) | Unit tests: `to_langchain_native` with 1/2/N images, webp fixture, failing-image path keeps content |
| 2 | Settings (§4.5) + `FileValidator` PDF support (magic header, page cap, encrypted detection) | Unit tests per validator branch; `make checkall` |
| 3 | `DocumentAttachment` model + persistence round-trip (to_dict/`**m`/markdown export) | Unit tests: old-JSON load, new-JSON round-trip, export |
| 4 | `attachment_utils.py`: capability map, content blocks, pypdf extraction, cache, token estimates | Unit tests with fixture PDFs (1-page, N-page, encrypted, oversized) |
| 5 | Wire into send path (`to_langchain_native` document branch) + token guardrail + `check_consecutive_messages` | Unit tests with mocked chat models per provider class |
| 6 | UI: `ctrl+p` picker + chips, `/add.doc`, `/attach`, widget rendering, help.md | `make checkall` + manual TUI pass (attach → send → render → reload session) |
| 7 | README/docs polish | Review |

## 8. Acceptance criteria (closes both issues)

1. Attach a multi-page PDF via file picker and via `/add.doc` on Anthropic, OpenAI, Gemini, and Ollama providers; each answers a question whose answer is only inside the PDF.
2. Two images on one message both reach the model (multi-image question test).
3. A webp image attaches and sends without the message content being replaced.
4. A session with documents reloads after app restart and the model still answers questions about the document.
5. Password-protected, >size-cap, and >page-cap PDFs are rejected with clear messages.
6. Old sessions (pre-feature JSON) load and behave as before.
7. `make checkall` and `make test` green.

## 9. Open questions

- Q1: Should document **URLs** work in v1 (like `/add.image` URLs) or local files only? Spec default: local only.
- Q2: Store full `data_b64` in session JSON vs. content-hash reference into the documents cache (smaller sessions, but cache eviction breaks resend). Spec default: inline, revisit if session size complaints.
- Q3: OpenRouter native document routing per-upstream-model (it can pass through file parts for some models) — v1 extraction, follow-up?
- Q4: OCR fallback for image-only PDFs (tesseract dep)? Default: no.
- Q5: OCR/document chat for vision models via page→PNG rendering (pypdfium2) instead of text extraction — useful for scanned PDFs against vision models. Default: out of v1.
- Q6: Upstream document helpers to `par_ai_core` after parllama proves the shape?
