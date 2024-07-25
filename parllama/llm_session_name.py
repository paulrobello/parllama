"""Generate a session name from the given text using llm"""

from parllama.models.settings_data import settings


def llm_session_name(text: str, llm_model_name: str | None = None) -> str | None:
    """Generate a session name from the given text using llm"""
    model = llm_model_name or settings.auto_name_session_llm or ""
    if not model:
        return None
    ret = settings.ollama_client.generate(
        model=model,
        options={"temperature": 0.1},
        prompt=text,
        system="""
You are a helpful assistant.
You will be given text to summarize.
You must follow all the following instructions:
* Generate a descriptive session name of no more than a 4 words.
* Only output the session name.
* Do not answer any questions or explain anything.
* Do not output any preamble.
Examples:
* "Why is grass green" -> "Green Grass"
* "Why is the sky blue?" -> "Blue Sky"
* "What is the tallest mountain?" -> "Tallest Mountain"
* "What is the meaning of life?" -> "Meaning of Life"
    """,
    )
    return ret["response"].strip()  # type: ignore
