**PAR LLAMA v0.6.0 Released - Terminal UI for LLMs with Memory & Code Execution**

# **What It Does**

A powerful Terminal User Interface (TUI) for managing and interacting with Ollama and other major LLM providers — featuring **persistent AI memory**, **secure code execution**, **interactive development workflows**, and **truly personalized conversations**!

![PAR LLAMA Chat Interface](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/chat_dark_1.png)

# **What's New in v0.6.0**

## **Memory System - REVOLUTIONARY NEW FEATURE**
- **Persistent User Context**: AI remembers who you are and your preferences across ALL conversations
- **Memory Tab Interface**: Dedicated UI for managing your personal information and context
- **AI-Powered Memory Updates**: Use `/remember` and `/forget` slash commands for intelligent memory management
- **Automatic Injection**: Your memory context appears in every new conversation automatically
- **Real-time Synchronization**: Memory updates via commands instantly reflect in the Memory tab
- **Smart Context Management**: Never repeat your preferences or background information again

## **Template Execution System - POWERFUL DEVELOPMENT FEATURE**
- **Secure Code Execution**: Execute code snippets and commands directly from chat messages using **Ctrl+R**
- **Multi-Language Support**: Python, JavaScript/Node.js, Bash, and shell scripts with automatic language detection
- **Configurable Security**: Command allowlists, content validation, and comprehensive safety controls
- **Interactive Development**: Transform PAR LLAMA into a powerful development companion
- **Real-time Results**: Execution results appear as chat responses with output, errors, and timing

## **Enhanced User Experience**
- **Memory Slash Commands**: `/remember [info]`, `/forget [info]`, `/memory.status`, `/memory.clear`
- **Intelligent Updates**: AI intelligently integrates new information into existing memory
- **Secure Storage**: All memory data stored locally with comprehensive file validation
- **Options Integration**: Both Memory and Template Execution controls in Options tab
- **Settings Persistence**: All preferences persist between sessions

# **Core Features**
- **Memory System**: Persistent user context across all conversations with AI-powered memory management
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

# **Memory System in Action**

Set up your persistent context once, and PAR LLAMA remembers forever:

**Memory Tab Setup:**
```
My name is Sarah and I'm a senior Python developer at TechCorp.

I prefer:
- Concise, technical explanations
- Code examples with detailed comments
- Security-focused best practices

Current projects:
- Building FastAPI microservices
- Migrating legacy Django apps
- Learning Rust for system programming
```

**Dynamic Memory Updates via Chat:**
```
User: /remember I just got promoted to Tech Lead
AI: ✅ Memory updated successfully

User: /forget I mentioned learning Rust
AI: ✅ Memory updated successfully

User: /memory.status
AI: Memory injection is enabled - 247 characters stored
Current memory: My name is Sarah and I'm a Tech Lead at TechCorp...
```

**Every New Conversation Automatically Includes Your Context!**

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

If you're working with LLMs and want a powerful terminal interface that **remembers who you are** and **bridges conversation and code execution** — PAR LLAMA v0.6.0 is a game-changer. Perfect for:

- **Developers**: Persistent context about your tech stack + execute code during AI conversations
- **Data Scientists**: AI remembers your analysis preferences + run scripts without leaving chat
- **DevOps Engineers**: Maintains infrastructure context + execute commands interactively
- **Researchers**: Remembers your research focus + test experiments in real-time
- **Consultants**: Different client contexts persist across sessions + rapid prototyping
- **Anyone**: Who wants truly personalized AI conversations with seamless code execution

**Configuration**: Set up your memory in the Memory tab. Enable template execution in Options → Template Execution. Configure your trusted command allowlist for security.

**Note**: Ollama must be installed and running for local model support. Cloud providers require API keys configured in the Options screen.
