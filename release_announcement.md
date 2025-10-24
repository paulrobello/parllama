**PAR LLAMA v0.7.0 Released - Enhanced Memory & Execution Experience**

# **What It Does**

A powerful Terminal User Interface (TUI) for managing and interacting with Ollama and other major LLM providers — featuring **persistent AI memory**, **secure code execution**, **interactive development workflows**, and **truly personalized conversations**!

![PAR LLAMA Chat Interface](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/chat_dark_1.png)

# **What's New in v0.7.0**

## **Improved Execution Experience**
- **Better Result Formatting**: Clean, professional display of execution results
- **Smart Command Display**: Shows 'python -c <script>' instead of escaped code for CLI parameters
- **Syntax-Highlighted Code Blocks**: Short scripts (≤10 lines) display with proper syntax highlighting
- **Intelligent Language Detection**: Automatic highlighting for Python, JavaScript, and Bash
- **Clean Command Truncation**: Long commands truncated intelligently for better readability

## **Previous Major Features (v0.6.0)**

### **Memory System**
- **Persistent User Context**: AI remembers who you are and your preferences across ALL conversations
- **Memory Tab Interface**: Dedicated UI for managing your personal information and context
- **AI-Powered Memory Updates**: Use `/remember` and `/forget` slash commands for intelligent memory management
- **Automatic Injection**: Your memory context appears in every new conversation automatically
- **Real-time Synchronization**: Memory updates via commands instantly reflect in the Memory tab
- **Smart Context Management**: Never repeat your preferences or background information again

### **Template Execution System**
- **Secure Code Execution**: Execute code snippets and commands directly from chat messages using **Ctrl+R**
- **Multi-Language Support**: Python, JavaScript/Node.js, Bash, and shell scripts with automatic language detection
- **Configurable Security**: Command allowlists, content validation, and comprehensive safety controls
- **Interactive Development**: Transform PAR LLAMA into a powerful development companion
- **Real-time Results**: Execution results appear as chat responses with output, errors, and timing

### **Enhanced User Experience**
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

# **Key Features**
- **100% Python**: Built with Textual and Rich for a beautiful easy to use terminal experience. Dark and Light mode support, plus custom themes
- **Cross-Platform**: Runs on Windows, macOS, Linux, and WSL
- **Async Architecture**: Non-blocking operations for smooth performance
- **Type Safe**: Fully typed with comprehensive type checking

# **GitHub & PyPI**

- GitHub: [https://github.com/paulrobello/parllama](https://github.com/paulrobello/parllama)
- PyPI: [https://pypi.org/project/parllama/](https://pypi.org/project/parllama/)

# Comparison:
I have seen many command line and web applications for interacting with LLM's but have not found any TUI related applications as feature reach as PAR LLAMA


# **Target Audience**

If you're working with LLMs and want a powerful terminal interface that **remembers who you are** and **bridges conversation and code execution** — PAR LLAMA v0.7.0 is a game-changer. Perfect for:

- **Developers**: Persistent context about your tech stack + execute code during AI conversations
- **Data Scientists**: AI remembers your analysis preferences + run scripts without leaving chat
- **DevOps Engineers**: Maintains infrastructure context + execute commands interactively
- **Researchers**: Remembers your research focus + test experiments in real-time
- **Consultants**: Different client contexts persist across sessions + rapid prototyping
- **Anyone**: Who wants truly personalized AI conversations with seamless code execution
