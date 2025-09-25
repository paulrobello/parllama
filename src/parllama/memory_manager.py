"""Memory management class for handling user memory with LLM assistance."""

from __future__ import annotations

from typing import Any

from par_ai_core.llm_config import LlmConfig, llm_run_manager
from par_ai_core.llm_providers import LlmProvider
from textual.app import App

from parllama.settings_manager import settings


class MemoryManager:
    """Memory management class for handling user memory with LLM assistance."""

    def __init__(self, app: App[Any] | None = None) -> None:
        """Initialize the memory manager."""
        self._app = app

    @property
    def memory_content(self) -> str:
        """Get current memory content."""
        return settings.user_memory

    @memory_content.setter
    def memory_content(self, value: str) -> None:
        """Set memory content and save to settings."""
        settings.user_memory = value
        settings.save()

        # Notify the UI that memory has been updated
        if self._app and hasattr(self._app, "post_message_all"):
            from parllama.messages.messages import MemoryUpdated

            # Use post_message_all to broadcast to all registered widgets
            # Type ignore because post_message_all is a ParLlamaApp method, not base App
            self._app.post_message_all(MemoryUpdated(new_content=value))  # type: ignore[attr-defined]

    @property
    def is_memory_enabled(self) -> bool:
        """Check if memory injection is enabled."""
        return settings.memory_enabled and bool(settings.user_memory.strip())

    def get_memory_for_injection(self) -> str | None:
        """Get memory content for injection into new conversations."""
        if not self.is_memory_enabled:
            return None
        return settings.user_memory.strip()

    async def update_memory_with_llm(self, current_memory: str, instruction: str, llm_config: LlmConfig) -> str:
        """Update memory using LLM assistance.

        Args:
            current_memory: The current memory content
            instruction: The instruction for updating memory
            llm_config: LLM configuration to use for processing

        Returns:
            Updated memory content
        """
        system_prompt = """You are a memory management assistant. Your job is to update user memory based on instructions.

Rules:
1. Keep all relevant existing information unless specifically instructed to remove it
2. Integrate new information naturally into the existing memory
3. Organize information logically and coherently
4. Return only the updated memory content, nothing else
5. If asked to remove information, remove only what is specifically mentioned
6. Be concise but comprehensive"""

        user_prompt = f"""Current Memory:
{current_memory}

Instruction:
{instruction}

Please update the memory according to the instruction above. Return only the updated memory content."""

        try:
            # Create langchain message structure for the LLM call
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

            # Build chat model and invoke
            chat_model = llm_config.build_chat_model()
            response = chat_model.invoke(messages, config=llm_run_manager.get_runnable_config(chat_model.name or ""))

            return str(response.content).strip()

        except Exception as e:
            if self._app:
                self._app.notify(f"Error updating memory: {str(e)}", severity="error")
            # Return original memory if LLM call fails
            return current_memory

    async def remember_information(self, memory: str, new_info: str, llm_config: LlmConfig) -> str:
        """Add new information to memory using LLM.

        Args:
            memory: Current memory content
            new_info: New information to remember
            llm_config: LLM configuration to use

        Returns:
            Updated memory content
        """
        instruction = f"Please add this new information to the memory: {new_info}"
        return await self.update_memory_with_llm(memory, instruction, llm_config)

    async def forget_information(self, memory: str, forget_instruction: str, llm_config: LlmConfig) -> str:
        """Remove information from memory using LLM.

        Args:
            memory: Current memory content
            forget_instruction: Description of what to forget
            llm_config: LLM configuration to use

        Returns:
            Updated memory content
        """
        instruction = f"Please remove or forget the following from the memory: {forget_instruction}"
        return await self.update_memory_with_llm(memory, instruction, llm_config)

    def get_default_llm_config(self) -> LlmConfig | None:
        """Get default LLM configuration for memory operations."""
        if settings.memory_llm_config:
            return LlmConfig.from_json(settings.memory_llm_config)

        # Fallback to last used LLM config if no memory-specific config is set
        if hasattr(settings, "last_llm_config") and settings.last_llm_config:
            return LlmConfig(
                provider=settings.last_llm_config.provider,
                model_name=settings.last_llm_config.model_name,
                temperature=0.3,  # Lower temperature for more consistent memory updates
                num_ctx=settings.last_llm_config.num_ctx,
            )

        # Final fallback to a reasonable default
        return LlmConfig(provider=LlmProvider.OLLAMA, model_name="llama3.2", temperature=0.3, num_ctx=2048)

    def set_memory_llm_config(self, llm_config: LlmConfig) -> None:
        """Set the LLM configuration for memory operations."""
        settings.memory_llm_config = llm_config.to_json()
        settings.save()

    def clear_memory(self) -> None:
        """Clear all memory content."""
        self.memory_content = ""

    def enable_memory(self, enabled: bool = True) -> None:
        """Enable or disable memory injection."""
        settings.memory_enabled = enabled
        settings.save()


# Global memory manager instance
memory_manager = MemoryManager()
