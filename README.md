# PAR LLAMA

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
usage: parllama [-h] [-v] [-d DATA_DIR] [-u OLLAMA_URL] [-t THEME_NAME] [-m {dark,light}] [-s {local,site,tools,create,logs}]
                [--restore-defaults] [--clear-cache] [--no-save]

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
  -s {local,site,tools,create,logs}, --starting-screen {local,site,tools,create,logs}
                        Starting screen. Defaults to local
  --restore-defaults    Restore default settings and theme
  --clear-cache         Clear cached data
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

PAR_LLAMA will remember the -u flag so subsequent runs will not require that you specify it.

### Dev mode
From repo root:
```bash
make dev
```

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

**Where we're going**
* Chat history / conversation management
* Chat with multiple models at same time to compare outputs
* LLM tool use
