# Dakara VLC player

[![Travis CI Build Status](https://travis-ci.org/DakaraProject/dakara-player-vlc.svg?branch=develop)](https://travis-ci.org/DakaraProject/dakara-player-vlc)
[![Appveyor CI Build status](https://ci.appveyor.com/api/projects/status/gcgpwu2i8vdwhb7y?svg=true)](https://ci.appveyor.com/project/neraste/dakara-player-vlc)

Interface between the Dakara server and VLC, for the Dakara project.

### Installation

To install Dakara completely, you have to get all the parts of the project.
Installation guidelines are provided over here:

* [Dakara server](https://github.com/Nadeflore/dakara-server/);
* [Dakara web client](https://github.com/Nadeflore/dakara-client-web/);

#### System requirements

* Python3.5 or higher, for the magic to take place;
* [VLC](https://www.videolan.org/vlc/), duh.

For 64 bits operating systems, you must install the equivalent version of the requirements.
Linux and Windows are supported.

#### Virtual environment

It is strongly recommended to run the Dakara VLC player within a virtual environment.

#### Python dependencies

Install dependencies, at root level of the repo:

```sh
pip install -r requirements.txt
```

#### Settings

Copy the file `config.yaml.example` to `config.yaml`, then uncomment and modify the different config values as you wish.
Mandatory parameters are not commented. 

### Start the player

First, start the server.

Activate the virtual environment, then start the player at the root level of the repo:

```sh
./dakara.py
```

### Development

#### Run tests

You can run the tests of the player. For that, activate the virtual environment, then type:

```sh
./tests.py
```

You can execute a specific test by passing its name to the command (like `unittest`'s default command line argument):

```sh
./tests.py test_module_name
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

#### Code style

The code follows the [PEP8](https://www.python.org/dev/peps/pep-0008/) style guide.
Quality of code is checked with [Flake8](https://pypi.org/project/flake8/).
Additional checking can be manually performed with [Pylint](https://www.pylint.org/).
You can use [Autopep8](https://pypi.org/project/autopep8/) to automatically format the code according to the style guidelines.
