# PAR LLAMA

## Table of Contents

* [About](#about)
   * [Screenshots](#screenshots)
* [Prerequisites for running](#prerequisites-for-running)
* [Prerequisites for dev](#prerequisites-for-dev)
* [Prerequisites for huggingface model quantization](#prerequisites-for-huggingface-model-quantization)
* [Installing using pipx](#installing-from-mypi-using-pipx)
* [Installing from mypi using pip](#installing-from-mypi-using-pip)
* [Installing for dev mode](#installing-for-dev-mode)
* [Command line arguments](#command-line-arguments)
* [Environment Variables](#environment-variables)
* [Running PAR_LLAMA](#running-par_llama)
    * [with pipx installation](#with-pipx-installation)
    * [with pip installation](#with-pip-installation)
* [Running against a remote instance](#running-against-a-remote-instance)
* [Running under Windows WSL](#running-under-windows-wsl)
    * [Dev mode](#dev-mode)
* [Quick start chat workflow](#quick-start-chat-workflow)
* [Custom Prompts](#Custom-Prompts)
* [Themes](#themes)
* [Screen Help](https://github.com/paulrobello/parllama/blob/main/src/parllama/help.md)
* [Contributing](#contributing)
* [FAQ](#faq)
* [Roadmap](#roadmap)
    * [Where we are](#where-we-are)Ï
    * [Where we're going](#where-were-going)
* [What's new](#whats-new)
    * [v0.3.11](#v0311)* 
    * [v0.3.10](#v0310)
    * [v0.3.9](#v039)
    * [v0.3.8](#v038)
    * [v0.3.7](#v037)
    * [v0.3.6](#v036)
    * [v0.3.5](#v035)
    * [v0.3.4](#v034)
    * [v0.3.3](#v033)
    * [v0.3.2](#v032)
    * [v0.3.1](#v031)
    * [v0.3.0](#v030)
    * [v0.2.51](#v0251)
    * [v0.2.5](#v025)

[![PyPI](https://img.shields.io/pypi/v/parllama)](https://pypi.org/project/parllama/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/parllama.svg)](https://pypi.org/project/parllama/)  
![Runs on Linux | MacOS | Windows](https://img.shields.io/badge/runs%20on-Linux%20%7C%20MacOS%20%7C%20Windows-blue)
![Arch x86-63 | ARM | AppleSilicon](https://img.shields.io/badge/arch-x86--64%20%7C%20ARM%20%7C%20AppleSilicon-blue)  
![PyPI - License](https://img.shields.io/pypi/l/parllama)

## About
PAR LLAMA is a TUI (Text UI) application designed for easy management and use of Ollama based LLMs.
The application was built with [Textual](https://textual.textualize.io/) and [Rich](https://github.com/Textualize/rich?tab=readme-ov-file)
and runs on all major OS's including but not limited to Windows, Windows WSL, Mac, and Linux.

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/probello3)

## Screenshots
Supports Dark and Light mode as well as custom themes.

![Chat Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/chat_dark_1.png)

![Chat Image Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/chat_image_dark_1.png)

![Local Models Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/local_models_dark_1.png)

![Model View Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/models_view_dark_1.png)

![Site Models Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/site_models_dark_1.png)

![Custom Prompt Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/custom_prompt_dark_1.png)

![Options Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/options_dark_1.png)

![Local Models Light](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/local_models_light_1.png)

## Videos
[V0.3.5 demo](https://www.youtube.com/watch?v=Genv46SKA5o)

## Prerequisites for running
* Install and run [Ollama](https://ollama.com/download)
* Install Python 3.11 or newer
  * [https://www.python.org/downloads/](https://www.python.org/downloads/) has installers for all versions of Python for all os's
  * On Windows the [Scoop](https://scoop.sh/) tool makes it easy to install and manage things like python
    * Install Scoop then do `scoop install python`

## Prerequisites for dev
* Install uv
  * See the [Using uv](#Using-uv) section
* Install GNU Compatible Make command
  * On windows if you have scoop installed you can install make with `scoop install make`

## Prerequisites for huggingface model quantization
If you want to be able to quantize custom models from huggingface, download the following tool from the releases area:
[HuggingFaceModelDownloader](https://github.com/bodaay/HuggingFaceModelDownloader)

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)

Pull the docker image ollama/quantize
```bash
docker pull ollama/quantize
```

## Using uv

### Installing uv
If you don't have uv installed you can run the following:  
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### MyPi install
```shell
uv tool install parllama
```

To upgrade an existing uv installation use the -U --force flags:
```bash
uv tool install parllama -U --force
```

### Installing / running using uvx
```shell
uvx parllama
```

### Source install from GitHub
```bash
uv tool install git+https://github.com/paulrobello/parllama
```
To upgrade an existing installation use the --force flag:
```bash
uv tool install git+https://github.com/paulrobello/parllama -U --force
```

## pipx
### Installing
If you don't have pipx installed you can run the following:  
```bash
pip install pipx
pipx ensurepath
```

### MyPi install
```shell
pipx install parllama
```

To upgrade an existing pipx installation use the --force flag:
```bash
pipx install parllama --force
```

### Source install from GitHub
```bash
pipx install git+https://github.com/paulrobello/parllama
```

To upgrade an existing installation use the --force flag:
```bash
pipx install git+https://github.com/paulrobello/parllama --force
```


## Installing for dev mode
Clone the repo and run the setup make target. Note `uv` is required for this.
```bash
git clone https://github.com/paulrobello/parllama
cd parllama
make setup
```


## Command line arguments
```
usage: parllama [-h] [-v] [-d DATA_DIR] [-u OLLAMA_URL] [-t THEME_NAME] [-m {dark,light}]
                [-s {local,site,chat,prompts,tools,create,options,logs}] [--use-last-tab-on-startup {0,1}] [-p PS_POLL] [-a {0,1}]
                [--restore-defaults] [--purge-cache] [--purge-chats] [--purge-prompts] [--no-save] [--no-chat-save]

PAR LLAMA -- Ollama TUI.

options:
  -h, --help            show this help message and exit
  -v, --version         Show version information.
  -d DATA_DIR, --data-dir DATA_DIR
                        Data Directory. Defaults to ~/.parllama
  -u OLLAMA_URL, --ollama-url OLLAMA_URL
                        URL of your Ollama instance. Defaults to http://localhost:11434
  -t THEME_NAME, --theme-name THEME_NAME
                        Theme name. Defaults to par
  -m {dark,light}, --theme-mode {dark,light}
                        Dark / Light mode. Defaults to dark
  -s {local,site,chat,prompts,tools,create,options,logs}, --starting-tab {local,site,chat,prompts,tools,create,options,logs}
                        Starting tab. Defaults to local
  --use-last-tab-on-startup {0,1}
                        Use last tab on startup. Defaults to 1
  -p PS_POLL, --ps-poll PS_POLL
                        Interval in seconds to poll ollama ps command. 0 = disable. Defaults to 3
  -a {0,1}, --auto-name-session {0,1}
                        Auto name session using LLM. Defaults to 0
  --restore-defaults    Restore default settings and theme
  --purge-cache         Purge cached data
  --purge-chats         Purge all chat history
  --purge-prompts       Purge all custom prompts
  --no-save             Prevent saving settings for this session
  --no-chat-save        Prevent saving chats for this session
```

Unless you specify "--no-save" most flags such as -u, -t, -m, -s are sticky and will be used next time you start PAR_LLAMA.

## Environment Variables
### Variables are loaded in the following order, last one to set a var wins
* PARLLAMA_DATA_DIR/.env
* HOST Environment
* ParLlama Options Screen

### Environment Variables for PAR LLAMA configuration
* PARLLAMA_DATA_DIR - Used to set --data-dir
* PARLLAMA_THEME_NAME - Used to set --theme-name
* PARLLAMA_THEME_MODE - Used to set --theme-mode
* OLLAMA_URL - Used to set --ollama-url
* PARLLAMA_AUTO_NAME_SESSION - Set to 0 or 1 to disable / enable session auto naming using LLM

## Running PAR_LLAMA

### with pipx or uv tool installation
From anywhere:
```bash
parllama
```

### with pip installation
From parent folder of venv
```bash
source venv/Scripts/activate
parllama
```
## Running against a remote Ollama instance
```bash
parllama -u "http://REMOTE_HOST:11434"
```

## Running under Windows WSL
Ollama by default only listens to localhost for connections, so you must set the environment variable OLLAMA_HOST=0.0.0.0:11434
to make it listen on all interfaces.  
**Note: this will allow connections to your Ollama server from other devices on any network you are connected to.**  
If you have Ollama installed via the native Windows installer you must set OLLAMA_HOST=0.0.0.0:11434 in the "System Variable" section
of the "Environment Variables" control panel.  
If you installed Ollama under WSL, setting the var with ```export OLLAMA_HOST=0.0.0.0:11434``` before starting the Ollama server will have it listen on all interfaces.
If your Ollama server is already running, stop and start it to ensure it picks up the new environment variable.  
You can validate what interfaces the Ollama server is listening on by looking at the server.log file in the Ollama config folder.  
You should see as one of the first few lines "OLLAMA_HOST:http://0.0.0.0:11434"  

Now that the server is listening on all interfaces you must instruct PAR_LLAMA to use a custom Ollama connection url with the "-u" flag.  
The command will look something like this:  
```bash
parllama -u "http://$(hostname).local:11434"
```
Depending on your DNS setup if the above does not work, try this:  
```bash
parllama -u "http://$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}'):11434"
```

PAR_LLAMA will remember the -u flag so subsequent runs will not require that you specify it.

### Dev mode
From repo root:
```bash
make dev
```

## Quick start chat workflow
* Start parllama.
* Click the "Site" tab.
* Use ^R to fetch the latest models from Ollama.com.
* Use the "Filter Site models" text box and type "llama3".
* Find the entry with title of "llama3".
* Click the blue tag "8B" to update the search box to read "llama3:8b".
* Press ^P to pull the model from Ollama to your local machine. Depending on the size of the model and your internet connection this can take a few min.
* Click the "Local" tab to see models that have been locally downloaded.
* Select the "llama3:8b" entry and press ^C to jump to the "Chat" tab and auto select the model.
* Type a message to the model such as "Why is the sky blue?". It will take a few seconds for Ollama to load the model. After which the LLMs answer will stream in.
* Towards the very top of the app you will see what model is loaded and what percent of it is loaded into the GPU / CPU. If a model cant be loaded 100% on the GPU it will run slower.
* To export your conversation as a Markdown file type "/session.export" in the message input box. This will open a export dialog.
* Press ^N to add a new chat tab.
* Select a different model or change the temperature and ask the same questions.
* Jump between the tabs to compare responses by click the tabs or using slash commands `/tab.1` and `/tab.2`
* Press ^S to see all your past and current sessions. You can recall any past session by selecting it and pressing Enter or ^N if you want to load it into a new tab.
* Press ^P to see / change your sessions config options such as provider, model, temperature, etc.
* Type "/help" or "/?" to see what other slash commands are available.

## Quick start image chat workflow
* Start parllama.
* Click the "Site" tab.
* Use ^R to fetch the latest models from Ollama.com.
* Use the "Filter Site models" text box and type "llava-llama3".
* Find the entry with title of "llava-llama3".
* Click the blue tag "8B" to update the search box to read "llava-llama3:8b".
* Press ^P to pull the model from Ollama to your local machine. Depending on the size of the model and your internet connection this can take a few min.
* Click the "Local" tab to see models that have been locally downloaded. If the download is complete and it isn't showing up here you may need to refresh the list with ^R.
* Select the "llava-llama3" entry and press ^C to jump to the "Chat" tab and auto select the model.
* Use a slash command to add an image and a prompt "/add.image PATH_TO_IMAGE describe whats happening in this image". It will take a few seconds for Ollama to load the model. After which the LLMs answer will stream in.
* Towards the very top of the app you will see what model is loaded and what percent of it is loaded into the GPU / CPU. If a model cant be loaded 100% on the GPU it will run slower.
* Type "/help" or "/?" to see what other slash commands are available.

## LlamaCPP support
Parllama supports LlamaCPP running OpenAI server mode. Parllama will use the default base_url of http://127.0.0.1:8080. This can be configured on the Options tab.  
To start a LlamaCPP server run the following command in separate terminal:  
```bash
llama-server -m PATH_TO_MODEL
```
or
```bash
llama-server -mu URL_TO_MODEL
```

## Custom Prompts
You can create a library of custom prompts for easy starting of new chats.  
You can set up system prompts and user messages to prime conversations with the option of sending immediately to the LLM upon loading of the prompt.  
Currently, importing prompts from the popular Fabric project is supported with more on the way.  


## Themes
Themes are json files stored in the themes folder in the data directory which defaults to **~/.parllama/themes**  

The default theme is "par" so can be located in **~/.parllama/themes/par.json**  

Themes have a dark and light mode are in the following format:  
```json
{
  "dark": {
    "primary": "#e49500",
    "secondary": "#6e4800",
    "warning": "#ffa62b",
    "error": "#ba3c5b",
    "success": "#4EBF71",
    "accent": "#6e4800",
    "panel": "#111",
    "surface":"#1e1e1e",
    "background":"#121212",
    "dark": true
  },
  "light": {
    "primary": "#004578",
    "secondary": "#ffa62b",
    "warning": "#ffa62b",
    "error": "#ba3c5b",
    "success": "#4EBF71",
    "accent": "#0178D4",
    "background":"#efefef",
    "surface":"#f5f5f5",
    "dark": false
  }
}
```

You must specify at least one of light or dark for the theme to be usable.  

Theme can be changed via command line with the ```--theme-name``` option.

## Contributing
Start by following the instructions in the section **Installing for dev mode**.  

Please ensure that all pull requests are formatted with black, pass mypy and pylint with 10/10 checks.  
You can run the make target **pre-commit** to ensure the pipeline will pass with your changes.  
There is also a pre-commit config to that will assist with formatting and checks.  
The easiest way to setup your environment to ensure smooth pull requests is:  

With uv installed:
```bash
uv tool install pre-commit
```

With pipx installed:
```bash
pipx install pre-commit
```

From repo root run the following:
```bash
pre-commit install
pre-commit run --all-files
```
After running the above all future commits will auto run pre-commit. pre-commit will fix what it can and show what
if anything remains to be fixed before the commit is allowed.

## FAQ
* Q: Do I need Docker?
  * A: Docker is only required if you want to Quantize models downloaded from Huggingface or similar llm repositories.
* Q: Does ParLlama require internet access?
  * A: ParLlama by default does not require any network / internet access unless you enable checking for updates or want to import / use data from an online source.
* Q: Does ParLlama run on ARM?
  * A: Short answer is yes. ParLlama should run any place python does. It has been tested on Windows 11 x64, Windows WSL x64, Mac OSX intel and silicon
* Q: Does ParLlama require Ollama be installed locally?
  * A: No. ParLlama has options to connect to remote Ollama instances
* Q: Does ParLlama require Ollama?
  * A: No. ParLlama can be used with most online AI providers
* Q: Does ParLlama support vision LLMS?
  * A: Yes. If the selected provider / model supports vision you can add images to the chat via /slash commands 

## Roadmap

### Where we are
* Initial release - Find, maintain and create new models
* Theme support
* Connect to remote instances
* Chat with history / conversation management
* Chat tabs allow chat with multiple models at same time
* Custom prompt library with import from Fabric
* Auto complete of slash commands, input history, multi line edit
* Ability to use cloud AI providers like OpenAI, Anthropic, Groq, and Google
* Use images with vision capable LLMs

### Where we're going

* Better image support via file pickers
* Ability to copy code and other sub sections from chat
* RAG for local documents and web pages
* Expand ability to import custom prompts of other tools
* LLM tool use


## What's new

### v0.3.11

* Added ability to set max context size for Ollama and other providers that support it
* Limited support for LLamaCpp running in OpenAI Mode.
* Added ability to cycle through fences in selected chat message and copy to clipboard with `ctrl+shift+c`
* Added theme selector
* Varius bug fixes and performance improvements
* Updated core AI library and dependencies
* Fixed crash due to upstream library update

### v0.3.10
* Fixed crash issues on fresh installs
* Images are now stored in chat session json files
* Added API key checks for online providers

### v0.3.9
* Image support for models that support them using /add.image slash command. See the [Quick start image chat workflow](#quick-start-image-chat-workflow)
* Add history support for both single and multi line input modes
* Fixed crash on models that dont have a license
* Fixed last model used not get used with new sessions

### v0.3.8
* Major rework of core to support providers other than Ollama
* Added support for the following online providers: OpenAI, Anthropic, Groq, Google
* New session config panel docked to right side of chat tab (more settings coming soon)
* Better counting of tokens (still not always 100% accurate)

### v0.3.7
* Fix for possible crash when there is more than one model loaded into ollama

### v0.3.6
* Added option to save chat input history and set its length
* Fixed tab switch issue on startup
* Added cache for Fabric import to speed up subsequent imports

### v0.3.5
* Added first time launch welcome
* Added Options tab which exposes more options than are available via command line switches
* Added option to auto check for new versions
* Added ability to import custom prompts from [fabric](https://github.com/danielmiessler/fabric)
* Added toggle between single and multi line input (Note auto complete and command history features not available in multi line edit mode)

### v0.3.4
* Added custom prompt library support  (Work in progress)
* Added cli option and environment var to enable auto naming of sessions using LLM (Work in progress)
* Added tokens per second stats to session info line on chat tab
* Fixed app crash when it cant contact ollama server for PS info
* Fixed slow startup when you have a lot of models available locally
* Fixed slow startup and reduced memory utilization when you have many / large chats
* Fixed session unique naming bug where it would always add a "1" to the session name
* Fixed app sometimes slowing down during LLM generation
* Major rework of internal message handling
* Issue where some footer items are not clickable has been resolved by a library PARLLAMA depends on

### v0.3.3
* Added ability to edit existing messages. select message in chat list and press "e" to edit, then "escape" to exit edit mode
* Add chat input history access via up / down arrow while chat message input has focus
* Added /session.system_prompt command to set system prompt in current chat tab

### v0.3.2
* Ollama ps stats bar now works with remote connections except for CPU / GPU %'s which ollama's api does not provide
* Chat tabs now have a session info bar with info like current / max context length
* Added conversation stop button to abort llm response
* Added ability to delete messages from session
* More model details displayed on model detail screen
* Better performance when changing session params on chat tab

### v0.3.1
* Add chat tabs to support multiple sessions
* Added cli option to prevent saving chat history to disk
* Renamed / namespaced chat slash commands for better consistency and grouping
* Fixed application crash when ollama binary not found

### v0.3.0
* Added chat history panel and management to chat page

### v0.2.51
* Fix missing dependency in package

### v0.2.5
* Added slash commands to chat input
* Added ability to export chat to markdown file
* ctrl+c on local model list will jump to chat tab and select currently selected local model
* ctrl+c on chat tab will copy selected chat message
