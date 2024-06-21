# PAR LLAMA

## About
PAR LLAMA is a TUI application designed for easy management and use of Ollama based LLMs.
The application was built with [Textual](https://textual.textualize.io/) and [Rich](https://github.com/Textualize/rich?tab=readme-ov-file)

### Screenshots
Supports Dark and Light mode as well as custom themes.

![Local Models Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/local_models_dark_1.png)
    
![Model View Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/models_view_dark_1.png)

![Site Models Dark](https://raw.githubusercontent.com/paulrobello/parllama/main/docs/site_models_dark_1.png)

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

## Installing from mypi using pip
Create a virtual environment and install using pip
```bash
mkdir parllama
cd parllama
python -m venv venv
source venv/Scripts/activate
pip install parllama
```

## Installing from mypi using pipx
```bash
pipx install parllama
```

## Installing for dev mode
Clone the repo and run the following from the root of the repo:
```bash
make first-setup
```


## Command line arguments
```
usage: PAR LLAMA TUI [-h] [-v] [-d DATA_DIR] [-t THEME_NAME] [-m {dark,light}] [--restore-defaults] [--clear-cache] [--no-save]

PAR LLAMA TUI -- Ollama TUI.

options:
  -h, --help            show this help message and exit
  -v, --version         Show version information.
  -d DATA_DIR, --data-dir DATA_DIR
                        Data Directory. Defaults to ~/.parllama
  -t THEME_NAME, --theme-name THEME_NAME
                        Theme name. Defaults to par
  -m {dark,light}, --theme-mode {dark,light}
                        Dark / Light mode. Defaults to dark
  --restore-defaults    Restore default settings and theme
  --clear-cache         Clear cached data
  --no-save             Prevent saving settings for this session.
  --clear-cache         Clear cached data
```

## Environment Variables
* PARLLAMA_DATA_DIR - Used to set --data-dir
* PARLLAMA_THEME_NAME - Used to set --theme-name
* PARLLAMA_THEME_MODE - Used to set --theme-mode


## Running Par Llama

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


# Changelog

### 0.2.0
Initial Release
