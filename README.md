# Dakara player

<!-- Badges are displayed for the develop branch -->
[![Appveyor CI Build status](https://ci.appveyor.com/api/projects/status/seo2wb9u01ga9vpd/branch/develop?svg=true)](https://ci.appveyor.com/project/neraste/dakara-player/branch/develop)
[![Codecov coverage analysis](https://codecov.io/gh/DakaraProject/dakara-player/branch/develop/graph/badge.svg)](https://codecov.io/gh/DakaraProject/dakara-player)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![PyPI version](https://badge.fury.io/py/dakaraplayer.svg)](https://pypi.python.org/pypi/dakaraplayer/)
[![PyPI Python versions](https://img.shields.io/pypi/pyversions/dakaraplayer.svg)](https://pypi.python.org/pypi/dakaraplayer/)

Interface between the Dakara server and a media player, for the Dakara project.

## Installation

To install Dakara completely, you have to get all the parts of the project.
Installation guidelines are provided over here:

* [Dakara server](https://github.com/DakaraProject/dakara-server/);
* [Dakara feeder](https:://github.com/DakaraProject/dakara-feeder).

### System requirements

* Python3, for the magic to take place (supported versions: 3.6, 3.7, 3.8 and 3.9).

At least one of there players:

* [VLC](https://www.videolan.org/vlc/) (supported version: 3.0.0 and higher, note that versions 3.0.13 and 3.0.14 cannot be used);
* [mpv](https://mpv.io/) (supported version: 0.27 and higher).

For 64 bits operating systems, you must install the equivalent version of the requirements.
Linux and Windows are supported.

### Virtual environment

It is strongly recommended to use the Dakara player within a virtual environment.

### Install

Install the package with:

```sh
pip install dakaraplayer
```

If you have downloaded the repo, you can install the package directly with:

```sh
python setup.py install
```

## Usage

The package provides the `dakara-play` command which runs the player:

```sh
dakara-play
# or
python -m dakara_player
```

One instance of the Dakara server should be running. For more help:

```sh
dakara-play -h
# or
python -m dakara_player -h
```

Before calling the command, you should create a config file with:

```sh
dakara-play create-config
# or
python -m dakara_player create-config
```

and complete it with your values. The file is stored in your user space: `~/.config/dakara` on Linux or `$APPDATA\Dakara` on Windows.

## Customization

The different text screens used when the player is idle, or before a song, can be customized, both for the background and the text template.
The program looks for custom files at startup in the user directory: `~/.local/share/dakara/player` on Linux or `$APPDATA\Dakara\player` on Windows.
Backgrounds are located in the `backgrounds` subfolder, and text templates in the `templates` subfolder.
File names can be modified in the config file, see `player.templates` and `player.backgrounds`.

You can dump the default backgrounds and templates in the user directory as a starter with:

```sh
dakara-play create-resources
# or
python -m dakara_player create-resources
```

## Development

### Install dependencies

Please ensure you have a recent enough version of `setuptools`:

```sh
pip install --upgrade "setuptools>=40.0"
```

Install the dependencies with:

```sh
pip install -e ".[tests]"
```

This installs the normal dependencies of the package plus the dependencies for tests.

### Run tests

Run tests simply with:

```sh
pytest
# or
python -m pytest
```

Tests are split between unit tests, which are ligthweight and do not require VLC or mpv to be installed, and integration tests, which are heavier:

```sh
pytest tests/unit
pytest tests/integration
# or
python -m pytest tests/unit
python -m pytest tests/integration
```

To check coverage, use the `coverage` command:

```sh
coverage run -m pytest
coverage report -m
# or
python -m coverage run -m pytest
python -m coverage report -m
```

### Hooks

Git hooks are included in the `hooks` directory.

Use the following command to use this hook folder for the project:

```
git config core.hooksPath hooks
```

If you're using git < 2.9 you can make a symlink instead:

```
ln -s -f ../../hooks/pre-commit .git/hooks/pre-commit
```

Note that pre-commit hook does not run integration tests.

### Code style

The code follows the [PEP8](https://www.python.org/dev/peps/pep-0008/) style guide (88 chars per line).
Quality of code is checked with [Flake8](https://pypi.org/project/flake8/).
Style is enforced using [Black](https://github.com/ambv/black).
You need to call Black before committing changes.
You may want to configure your editor to call it automatically.
Additionnal checking can be manually performed with [Pylint](https://www.pylint.org/).
