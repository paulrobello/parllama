## PAR Ollama Workflows
The app is separated into various sections.  
* Local models (models that have already be pulled / created on your machine)
* Site models (models that can be pulled from ollama.com)
* Creation / Editing / Utils (This area helps you create new models from scratch or by repackaging / quantizing existing models). Work in progress
* Chatting with models and Custom prompts to easily start new chats


## Global keys
| Key      | Command                 |
|----------|-------------------------|
| `F1`     | This help               |
| `F10`    | Toggle dark/light theme |
| `ctrl+q` | Quit the application    |


## Actions
Actions like delete, pull, etc. are queued and will be performed in the order they were queued.  
Lists / screens will automatically refresh once the action is completed.

## Local Model Tab
Displays all local models currently available to your local Ollama.
`ctrl+q` will quit the application.  
`ctrl+r` will refresh the list.  
`enter` will open its details dialog for the selected item.
`ctrl+b` will open the model card from ollama.com in a web browser.
`ctrl+f` can be used to quickly focus the filter input box.  
`ctrl+p` will pull the highlighted model.  
`ctrl+u` will push the highlighted model to Ollama.com. Ensure you have your Ollama access key setup. See the **Publishing** section for details on how to do this.
`ctrl+d` will bring up the copy model dialog which will prompt you for the name to copy the model to.  
`ctrl+c` will jump to chat tab and select the model highlighted model.  

### Local Model Tab keys

| Key      | Command                                  |
|----------|------------------------------------------|
| `ctrl+b` | Open model card on Ollama.com in browser |
| `enter`  | Open model details dialog                |
| `ctrl+f` | Focus the Filter / search input          |
| `ctrl+r` | Refresh local model grid list            |
| `p`      | Pull selected model from Ollama.com      |
| `ctrl+p` | Pull all local models from Ollama.com    |
| `ctrl+u` | Push selected model to Ollama.com        |
| `ctrl+c` | Copy selected model to new name          |


## Site Model Tab
This tab allows you to search for models on [Ollama.com](https://ollama.com/library?sort=popular) directly within the terminal.  
Ollama.com does not publish an API for this so a web scrapping method is used to get the data.  
Web scraping is not an overly reliable method to get structured data so this search / list may break if Ollama updates their site.  

The Namespace field tells the app where to search. Leaving the field blank or using "models" as a value will search the main Ollama.com model list.  
If you have a private namespace enter it and hit tab to populate the list of available models.
Scraped data is cached in a local json file to increase responsiveness.  
Use `ctrl+r` to force a refresh if needed.  
The Namespace field provides auto complete from previous successful searches.  

Use the field to the right of Namespace to filter the list of available models as well as specify a model to pull.  
Clicking / highlighting a model will populate the name of the model in the input box.  
Click a blue Tag link in the model to populate the name and tag in the input box.  
Once the name and optional tag are populated in the input box use `ctrl+p` to pull the model.  
You can queue as many pulls as you like. They will be processed in order one at a time.  
You can use `ctrl+b` to open the model card in a web browser


### Site Model Tab keys

| Key      | Command                                  |
|----------|------------------------------------------|
| `ctrl+p` | Pull selected model from Ollama.com      |
| `ctrl+b` | Open model card on Ollama.com in browser |
| `ctrl+r` | Refresh local model grid list            |


## Tools Tab
Tools to create, modify, and publish models  

## Chat Screen
Chat with local LLMs and manage saved sessions

### Chat Tab keys
| Key           | Command                         |
|---------------|---------------------------------|
| `ctrl+s`      | Toggle session list             |
| `ctrl+p`      | Toggle session config           |
| `ctrl+b`      | New session in current tab      |
| `ctrl+n`      | New chat tab                    |
| `ctrl+delete` | Remove current chat tab         |
| `ctrl+e`      | Export selected tab as Markdown |

### Message Input keys
| Key           | Command                                         |
|---------------|-------------------------------------------------|
| `enter`       | Send chat to LLM                                |
| `up` / `down` | Scroll through input history                    |
| `ctrl+j`      | Toggle between single and multi line input mode |
| `ctrl+g`      | Submit multi line edit content                  |

### Message List keys
| Key            | Command                                                             |
|----------------|---------------------------------------------------------------------|
| `ctrl+c`       | Copy selected chat message to clipboard                             |
| `ctrl+shift+c` | Cycle through fences in selected chat message and copy to clipboard |
| `e`            | Edit selected message                                               |
| `delete`       | Delete selected message                                             |
| `escape`       | Exit message edit mode                                              |


### Chat Tab Session Panel keys

| Key                     | Command                                  |
|-------------------------|------------------------------------------|
| `enter` or `dbl click`  | Load selected session into current tab   |
| `ctrl+n`                | Load selected session into new tab       |
| `delete`                | Delete selected session and related tabs |


### Chat Tab input Slash Commands:
Chat Commands:
* /? or /help - Show slash command help dialog
* /tab.# - Switch to the tab with the given number
* /tab.new - Create new tab and switch to it
* /tab.remove - Remove the active tab
* /tabs.clear - Clear / remove all tabs
* /session.new [session_name] - Start new chat session in current tab with optional name
* /session.name [session_name] - Select session name input or set the session name in current tab
* /session.model [model_name] - Select model dropdown or set model name in current tab
* /session.temp [temperature] - Select temperature input or set temperature in current tab
* /session.delete - Delete the chat session for current tab
* /session.export - Export the conversation in current tab to a Markdown file
* /session.system_prompt [system_prompt] - Set system prompt in current tab
* /session.to_prompt submit_on_load [prompt_name] - Copy current session to new custom prompt. submit_on_load = {0|1}
* /prompt.load prompt_name - Load a custom prompt using current tabs model and temperature
* /add.image image_path_or_url prompt - Add an image via path or url to the active chat session. Everything after the image path or url will be used as the prompt

## Prompts Tab
Allows you to create, edit, import and execute custom prompts

### Prompts Tab keys

| Key                    | Command                                |
|------------------------|----------------------------------------|
| `enter` or `dbl click` | Load selected prompt into new chat tab |
| `e`                    | Edit the selected prompt               |
| `delete`               | Delete selected prompt                 |

## Logs Tab
Allows viewing any messages that have passed through the status bar.

## Publishing

To publish a model to Ollama.com you need to create your own namespace and setup your public key.

The tools screen can help you with this.  

When creating a free account on [Ollama.com](https://ollama.com/signup) your username will also be your namespace.  

When you start ollama on your machine, it will create a keypair used specifically for ollama and save it into either
~/.ollama or /usr/share/ollama/.ollama as id_ed25519 (private key) and id_ed25519.pub (public key).

When you want to publish, you take the contents of id_ed25519.pub and import into [ollama settings keys](https://ollama.com/settings/keys)

If you have Ollama running on multiple machines you must import each machines key into Ollama.com

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
