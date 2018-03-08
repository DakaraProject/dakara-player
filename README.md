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

```sh
pip install -r requirements.txt
```

#### Settings

Copy the file `config.ini.example` to `config.py`, then uncomment and modify the different config values as you wish.
Mandatory parameters are not commented. 

### Start the player

First, start the server.

Activate the virtual environment, then start the player at the root level of the repo:

```sh
./dakara.py runplayer
```

### Development

#### Run tests

You can run the tests of the player. For that, activate the virtual environment, then type:

```sh
./dakara.py test
```

You can execute a specific test by passing its name to the command (like `unittest`'s default command line argument):

```sh
./dakara.py test test_module_name
```

#### Hooks

Git hooks are included in the `hooks` directory.

Use the following command to use this hook folder for the project:

```
git config core.hooksPath hooks
```

If you're using git < 2.9 you can make a symlink instead:

```
ln -s -f ../../hooks/pre-commit .git/hooks/pre-commit
```
