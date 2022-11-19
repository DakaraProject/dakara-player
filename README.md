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

* Python3, for the magic to take place (supported versions: 3.7, 3.8, 3.9, 3.10 and 3.11).

At least one of there players:

* [VLC](https://www.videolan.org/vlc/) (supported version: 3.0.0 and higher, note that versions 3.0.13 to 3.0.16 cannot be used);
* [mpv](https://mpv.io/) (supported version: 0.27 and higher).

For 64 bits operating systems, you must install the equivalent version of the requirements.
Linux and Windows are supported.

### Virtual environment

It is strongly recommended to use the Dakara player within a virtual environment.

### Install

Please ensure you have a recent enough version of `setuptools`:

```sh
pip install --upgrade "setuptools>=46.4.0"
```

Install the package with:

```sh
pip install dakaraplayer
```

If you have downloaded the repo, you can install the package directly with:

```sh
pip install .
```

## Usage

The package provides the `dakara-player play` command which runs the player:

```sh
dakara-player play
# or
python -m dakara_player play
```

One instance of the Dakara server should be running.

For more help:

```sh
dakara-player -h
# or
python -m dakara_player -h
```

Before calling the command, you should create a config file with:

```sh
dakara-player create-config
# or
python -m dakara_player create-config
```

and complete it with your values. The file is stored in your user space: `~/.config/dakara` on Linux, or `$APPDATA\DakaraProject\dakara` on Windows.

### Configuration

The configuration is created with the previously cited command. Several aspect of the player can be configured with this file. Please check with the file documentation.

Authentication to the server can only be done with a player token that can be generated and copied from the web client. Please note that only a playlist manager can generate such a player token.

### Customization

The different text screens used when the player is idle, or before a song, can be customized, both for the background and the text template.
The program looks for custom files at startup in the user directory: `~/.local/share/dakara/player` on Linux or `$APPDATA\DakaraProject\dakara\player` on Windows.
Backgrounds are located in the `backgrounds` subfolder, and text templates in the `templates` subfolder.
File names can be modified in the config file, see `player.templates` and `player.backgrounds`.

You can dump the default backgrounds and templates in the user directory as a starter with:

```sh
dakara-player create-resources
# or
python -m dakara_player create-resources
```

## Development

Please read the [developers documentation](CONTRIBUTING.md).
