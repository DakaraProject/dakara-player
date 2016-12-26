# Dakara VLC player

Interface between Dakara server and VLC, for the Dakara project.

### Installation

To install Dakara completely, you have to get all the parts of the project.
Installation guidelines are provided over here:

* [Dakara server](https://github.com/Nadeflore/dakara-server/);
* [Dakara web client](https://github.com/Nadeflore/dakara-client-web/);

#### System requirements

* Python3, for the magic to take place;
* [VLC](https://www.videolan.org/vlc/), duh.

#### Virtual environment

It is strongly recommended to run Dakara player VLC on virtual environment.

#### Python dependencies

Install dependencies, at root level of the repo:

```
pip install -r requirements.txt
```

#### Settings

Copy the file `config.ini.example` to `config.py`, then uncomment and modify the different config values as you wish.
Mandatory parameters are not commented. 

### Start the player

First, start the server.

Activate the virtual environment, then start the player at the root level of the repo:

```
python dakara.py
```
