**PAR LLAMA v0.5.0 Released - Terminal UI for LLMs with Code Execution**

# **What It Does**

A powerful Terminal User Interface (TUI) for managing and interacting with Ollama and other major LLM providers — now with **secure code execution**, **interactive development workflows**, and **seamless chat-to-code integration**!

![PAR LLAMA Chat Interface](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/chat_dark_1.png)

# **What's New in v0.5.0**

## **Template Execution System - MAJOR NEW FEATURE**
- **Secure Code Execution**: Execute code snippets and commands directly from chat messages using **Ctrl+R**
- **Multi-Language Support**: Python, JavaScript/Node.js, Bash, and shell scripts with automatic language detection
- **Configurable Security**: Command allowlists, content validation, and comprehensive safety controls
- **Interactive Development**: Transform PAR LLAMA into a powerful development companion
- **Real-time Results**: Execution results appear as chat responses with output, errors, and timing

## **Enhanced Configuration**
- **Options Integration**: New "Template Execution" section in Options tab
- **Execution Toggle**: Enable/disable execution feature with one click
- **Command Management**: Configure allowed commands list for security
- **Settings Persistence**: Execution preferences now properly persist between sessions

## **Security & Safety**
- **Command Allowlists**: Only pre-approved commands can be executed
- **Pattern Detection**: Dangerous command patterns automatically blocked
- **Sandboxed Environment**: Commands run with restricted permissions
- **Timeout Protection**: Configurable execution time limits
- **Output Limiting**: Command output truncated to prevent resource exhaustion

# **Core Features**
- **Template Execution**: Secure code execution system with configurable safety controls
- **Multi-Provider Support**: Ollama, OpenAI, Anthropic, Groq, XAI, OpenRouter, Deepseek, LiteLLM
- **Vision Model Support**: Chat with images using vision-capable models
- **Session Management**: Save, load, and organize chat sessions
- **Custom Prompts**: Create and manage custom system prompts and Fabric patterns
- **Theme System**: Dark/light modes with custom theme support
- **Model Management**: Pull, delete, copy, and create models with native quantization
- **Smart Caching**: Intelligent per-provider model caching with configurable durations
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

# **Template Execution in Action**

Simply paste code in any chat message and press **Ctrl+R** to execute:

**Python Example:**
```python
print("Hello from PAR LLAMA!")
import math
result = math.sqrt(16)
print(f"Square root of 16 is: {result}")
```
*Press Ctrl+R → Executes instantly with output in chat*

**Shell Commands:**
```bash
ls -la
echo "Current directory contents"
date
```
*Press Ctrl+R → Shows command output directly in conversation*

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

If you're working with LLMs and want a powerful terminal interface that **bridges conversation and code execution** — PAR LLAMA v0.5.0 is a game-changer. Perfect for:

- **Developers**: Execute code snippets during AI conversations for rapid prototyping
- **Data Scientists**: Run analysis scripts and see results without leaving the chat
- **DevOps Engineers**: Execute shell commands and automation scripts interactively
- **Researchers**: Test code examples and experiments in real-time
- **Anyone**: Who wants seamless integration between AI chat and code execution

**Configuration**: Enable template execution in Options → Template Execution. Configure your trusted command allowlist for security.

**Note**: Ollama must be installed and running for local model support. Cloud providers require API keys configured in the Options screen.
