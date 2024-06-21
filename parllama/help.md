## PAR Ollama Workflows
The app is separated into 3 sections.  
* Local models (models that have already be pulled / created on your machine)
* Site models (models that can be pulled from ollama.com)
* Creation / Editing / Utils (This area helps you create new models from scratch or by repackaging / quantizing existing models). Work in progress


## Global keys
| Key      | Command                 |
|----------|-------------------------|
| `F1`     | This help               |
| `F10`    | Toggle dark/light theme |
| `ctrl+l` | Local models            |
| `ctrl+s` | Site models             |
| `ctrl+t` | Model tools             |
| `ctrl+d` | Debug log               |
| `ctrl+q` | Quit the application    |


## Actions
Actions like delete, pull, etc. are queued and will be performed in the order they were queued.  
Lists / screens will automatically refresh once the action is completed.

## Local Model Screen
This screen displays all local models currently available to your local Ollama.
`ctrl+q` will quit the application.  
`ctrl+r` will refresh the list.   
`enter` will open its details dialog for the selected item.
`ctrl+b` will open the model card from ollama.com in a web browser.
`ctrl+f` can be used to quickly focus the filter input box.  
`ctrl+p` will pull the highlighted model.  
`ctrl+u` will push the highlighted model to Ollama.com. Ensure you have your Ollama access key setup. See the **Publishing** section for details on how to do this.
`ctrl+c` will bring up the copy model dialog which will prompt you for the name to copy the model to.  

### Local Model Screen keys

| Key      | Command                                  |
|----------|------------------------------------------|
| `ctrl+b` | Open model card on Ollama.com in browser |
| `enter`  | Open model details dialog                |
| `ctrl+f` | Focus the Filter / search input          |
| `ctrl+r` | Refresh local model grid list            |
| `ctrl+p` | Pull selected model from Ollama.com      |
| `ctrl+u` | Push selected model to Ollama.com        |
| `ctrl+c` | Copy selected model to new name          |


## Site Model Screen
This screen allows you to search for models on [Ollama.com](https://ollama.com/library?sort=popular) directly within the terminal.  
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


### Site Model Screen keys

| Key      | Command                                  |
|----------|------------------------------------------|
| `ctrl+p` | Pull selected model from Ollama.com      |
| `ctrl+b` | Open model card on Ollama.com in browser |
| `ctrl+r` | Refresh local model grid list            |


## Model Tools Screen
This screen allows you to access tools to create, modify, and publish models  

Work in progress...


## Publishing
 
To publish a model to Ollama.com you need to create your own namespace and setup your public key.

The tools screen can help you with this.  

When creating a free account on [Ollama.com](https://ollama.com/signup) your username will also be your namespace.  

When you start ollama on your machine, it will create a keypair used specifically for ollama and save it into either 
~/.ollama or /usr/share/ollama/.ollama as id_ed25519 (private key) and id_ed25519.pub (public key). 

When you want to publish, you take the contents of id_ed25519.pub and import into [ollama settings keys](https://ollama.com/settings/keys)

If you have Ollama running on multiple machines you must import each machines key into Ollama.com
