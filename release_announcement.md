**PAR LLAMA v0.4.0 Released - Enhanced Terminal UI for LLMs**

# **What It Does**

A powerful Terminal User Interface (TUI) for managing and interacting with Ollama and other major LLM providers — now with **improved Textual compatibility**, **enhanced type safety**, and **better widget reliability**!

![PAR LLAMA Chat Interface](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/chat_dark_1.png)

# **What's New in v0.4.0**

## **Bug Fixes & Improvements**
- **Fixed Type Checking**: Resolved ClickableLabel widget type checking issues with Textual API
- **API Alignment**: Updated widget property access from `renderable` to `content` for proper Textual compatibility
- **Enhanced Stability**: Improved widget reliability and error handling

# **Previous v0.3.28 Features**
- Fixed outdated dependencies
- Resolved delete chat tab issues on macOS
- Streamlined markdown fence rendering

# **Core Features**
- **Multi-Provider Support**: Ollama, OpenAI, Anthropic, Groq, XAI, OpenRouter, Deepseek, LiteLLM
- **Vision Model Support**: Chat with images using vision-capable models
- **Session Management**: Save, load, and organize chat sessions
- **Custom Prompts**: Create and manage custom system prompts
- **Theme System**: Dark/light modes with custom theme support
- **Model Management**: Pull, delete, copy, and create models with native quantization
- **Smart Caching**: Intelligent per-provider model caching with configurable durations
- **Fabric Integration**: Import and use Fabric patterns as prompts
- **Security**: Comprehensive file validation and secure operations

# **Quick Setup**
```bash
# Install with pipx (recommended)
pipx install parllama

# Or install with pip
pip install parllama

# Or install with uv
uv tool install parllama

# Run the application
parllama
```

# **Key Highlights**
- **100% Python**: Built with Textual and Rich for a beautiful terminal experience
- **Cross-Platform**: Runs on Windows, macOS, Linux, and WSL
- **Async Architecture**: Non-blocking operations for smooth performance
- **Type Safe**: Fully typed with comprehensive type checking
- **Extensible**: Easy to add new providers and features

# **GitHub & PyPI**

- GitHub: [https://github.com/paulrobello/parllama](https://github.com/paulrobello/parllama)
- PyPI: [https://pypi.org/project/parllama/](https://pypi.org/project/parllama/)

# **Who's This For?**

If you're working with LLMs and want a powerful terminal interface that combines the simplicity of Ollama with the flexibility of cloud providers — PAR LLAMA is for you. Perfect for developers, researchers, and anyone who prefers terminal interfaces for their AI workflows.

**Note**: Ollama must be installed and running for local model support. Cloud providers require API keys configured in the Options screen.