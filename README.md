# PAR LLAMA

## Table of Contents

- [About](#about)
- [Screenshots](#screenshots)
- [Prerequisites](#prerequisites-for-running)
  - [For Running](#prerequisites-for-running)
  - [For Development](#prerequisites-for-dev)
  - [For Model Quantization](#prerequisites-for-model-quantization)
- [Installation](#installing-from-mypi-using-pipx)
  - [Using pipx](#installing-from-mypi-using-pipx)
  - [Using pip](#installing-from-mypi-using-pip)
  - [For Development](#installing-for-dev-mode)
- [Command Line Arguments](#command-line-arguments)
- [Environment Variables](#environment-variables)
- [Running PAR_LLAMA](#running-par_llama)
  - [With pipx installation](#with-pipx-installation)
  - [With pip installation](#with-pip-installation)
  - [Under Windows WSL](#running-under-windows-wsl)
  - [In Development Mode](#dev-mode)
- [Example Workflow](#example-workflow)
- [Themes](#themes)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [What's New](#whats-new)

## About
PAR LLAMA is a TUI application designed for easy management and use of Ollama based LLMs.
The application was built with [Textual](https://textual.textualize.io/) and [Rich](https://github.com/Textualize/rich?tab=readme-ov-file)

### Screenshots
Supports Dark and Light mode as well as custom themes.

![Local Models Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/local_models_dark_1.png)

![Model View Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/models_view_dark_1.png)

![Site Models Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/site_models_dark_1.png)

![Chat Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/chat_dark_1.png)

![Local Models Light](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/local_models_light_1.png)

## Prerequisites for running
* Install and run [Ollama](https://ollama.com/download)
* Install Python 3.11 or newer

## Prerequisites for dev
* Install pipenv
* Install GNU Compatible Make command

## Prerequisites for model quantization
If you want to be able to quantize custom models, download the following tool from the releases area:
[HuggingFaceModelDownloader](https://github.com/bodaay/HuggingFaceModelDownloader)

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)

Pull the docker image ollama/quantize
```bash
docker pull ollama/quantize
```

## Installing from mypi using pipx
If you don't have pipx installed you can run the following:  
```bash
pip install pipx
pipx ensurepath
```
Once pipx is installed, run the following:  
```bash
pipx install parllama
```

## Installing from mypi using pip
Create a virtual environment and install using pip
```bash
mkdir parllama
cd parllama
python -m venv venv
source venv/Scripts/activate
pip install parllama
```

## Installing for dev mode
Clone the repo and run the following from the root of the repo:
```bash
make first-setup
```


## Command line arguments
```
usage: parllama [-h] [-v] [-d DATA_DIR] [-u OLLAMA_URL] [-t THEME_NAME] [-m {dark,light}] [-s {local,site,tools,create,chat,logs}] [-p PS_POLL]
                [--restore-defaults] [--clear-cache] [--purge-chats] [--no-save]

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
  -s {local,site,tools,create,chat,logs}, --starting-screen {local,site,tools,create,chat,logs}
                        Starting screen. Defaults to local
  -p PS_POLL, --ps-poll PS_POLL
                        Interval in seconds to poll ollama ps command. 0 = disable. Defaults to 3
  --restore-defaults    Restore default settings and theme
  --clear-cache         Clear cached data
  --purge-chats         Purge all chat history
  --no-save             Prevent saving settings for this session.
```

Unless you specify "--no-save" most flags such as -u, -t, -m, -s are sticky and will be used next time you start PAR_LLAMA.

## Environment Variables
* PARLLAMA_DATA_DIR - Used to set --data-dir
* PARLLAMA_THEME_NAME - Used to set --theme-name
* PARLLAMA_THEME_MODE - Used to set --theme-mode
* OLLAMA_URL - Used to set --ollama-url

## Running PAR_LLAMA

### with pipx installation
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

## Example workflow
* Start parllama.
* Click the "Site" tab.
* Use ^R to fetch the latest models from Ollama.com.
* User the "Filter Site models" text box and type "llama3".
* Find the entry with title of "llama3".
* Click the blue tag "8B" to update the search box to read "llama3:8b".
* Press ^P to pull the model from Ollama to your local machine. Depending on the size of the model and your internet connection this can take a few min.
* Click the "Local" tab to see models that have been locally downloaded
* Select the "llama3:8b" entry and press ^C to jump to the "Chat" tab and auto select the model
* Type a message to the model such as "Why is the sky blue?". It will take a few seconds for Ollama to load the model. After which the LLMs answer will stream in.
* Towards the very top of the app you will see what model is loaded and what percent of it is loaded into the GPU / CPU. If a model cant be loaded 100% on the GPU it will run slower.
* To export your conversation as a Markdown file type "/export" in the message input box. This will open a export dialog.
* Type "/help" to see what other slash commands are available.

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
You can run the make target **do-before-commit** to ensure the pipeline will pass with your changes.  
There is also a pre-commit config to that will assist with formatting and checks.  
The easiest way to setup your environment to ensure smooth pull requests is:  

If you don't have pipx installed you can run the following:  
```bash
pip install pipx
```

```bash
pipx install pre-commit
pre-commit install
pre-commit run --all-files
```
After running the above all future commits will auto run pre-commit. pre-commit will fix what it can and show what
if anything remains to be fixed before the commit is allowed.


## Roadmap

**Where we are**  
* Initial release - Find, maintain and create new models
* Basic chat with LLM
* Chat history / conversation management

**Where we're going**
* Chat with multiple models at same time to compare outputs
* LLM tool use


## What's new

### v0.2.6
* Added chat history panel and management to chat page

### v0.2.51
* Fix missing dependency in package

### v0.2.5
* Added slash commands to chat input
* Added ability to export chat to markdown file
* ctrl+c on local model list will jump to chat tab and select currently selected local model
* ctrl+c on chat tab will copy selected chat message
