"""Generate a session name from the given text using llm"""

from __future__ import annotations

from par_ai_core.llm_config import LlmConfig, llm_run_manager


def llm_session_name(text: str, llm_config: LlmConfig | None = None) -> str | None:
    """Generate a session name from the given text using llm"""
    if not llm_config:
        return None
    chat_model = llm_config.build_chat_model()
    ret = chat_model.invoke(
        [
            (
                "system",
                """
# IDENTITY and PURPOSE

You are an expert content summarizer.
You take a conversation and generate a simple and succinct one line title based on this conversation.
Your title should be concise and capture the essence of the conversation.
Minimize the thinking time as much as possible and focus on the given context.

# STEPS

- Combine all of your understanding of the conversation into a single, 3-8 word title.
- Make sure the title is simple short and easy to understand.
- DO NOT answer or reply to the content, only summarize it.

# OUTPUT INSTRUCTIONS

- DO NOT answer or reply to the content, only summarize it.
- DO NOT reply with more than 8 words.
- Output the title in plain text. Do not use any special characters or Markdown. This is very important.
- Do not output anything else. Strictly answer with only title and no other text.
- Do not provide any additional information or context. Just the title.
    """,
            ),
            ("user", text),
        ],
        config=llm_run_manager.get_runnable_config(chat_model.name or ""),
    )
    return str(ret.content).strip()


def llm_summarize_session(text: str, llm_config: LlmConfig) -> str:
    """Generate a session name from the given text using llm"""
    chat_model = llm_config.build_chat_model()
    ret = chat_model.invoke(
        [
            (
                "system",
                """
# IDENTITY and PURPOSE

You are an expert content summarizer.
You take a conversation and generate a summary of that conversation.

# STEPS

- Combine all of your understanding of the conversation into a single paragraph.
- All content will be enclosed in a CONTENT tag

# OUTPUT INSTRUCTIONS

- DO NOT answer or reply to the content, only summarize it.
- DO NOT reply with more than 1 paragraph.
- DO NOT output anything other than the summary no other text.
- DO NOT add a preamble such as "here is a summary of the conversation".
- DO NOT include the CONTENT tag, only the summary.
    """,
            ),
            ("user", f"<CONTENT>{text}</CONTENT>"),
        ],
        config=llm_run_manager.get_runnable_config(chat_model.name or ""),
    )
    return str(ret.content).strip()
