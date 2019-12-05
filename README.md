# Dakara VLC player

[![Travis CI Build Status](https://travis-ci.com/DakaraProject/dakara-player-vlc.svg?branch=develop)](https://travis-ci.com/DakaraProject/dakara-player-vlc)
[![Appveyor CI Build status](https://ci.appveyor.com/api/projects/status/gcgpwu2i8vdwhb7y?svg=true)](https://ci.appveyor.com/project/neraste/dakara-player-vlc)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![PyPI version](https://badge.fury.io/py/dakaraplayervlc.svg)](https://pypi.python.org/pypi/dakaraplayervlc/)
[![PyPI Python versions](https://img.shields.io/pypi/pyversions/dakaraplayervlc.svg)](https://pypi.python.org/pypi/dakaraplayervlc/)

Interface between the Dakara server and VLC, for the Dakara project.

## Installation

To install Dakara completely, you have to get all the parts of the project.
Installation guidelines are provided over here:

* [Dakara server](https://github.com/DakaraProject/dakara-server/);
- [Dakara feeder](https:://github.com/DakaraProject/dakara-feeder).

### System requirements

* Python3, for the magic to take place (supported versions: 3.5, 3.6);
* [VLC](https://www.videolan.org/vlc/), duh.

For 64 bits operating systems, you must install the equivalent version of the requirements.
Linux and Windows are supported.

### Virtual environment

It is strongly recommended to use the Dakara VLC player within a virtual environment.

### Install

<!-- Install the package with: -->
<!--  -->
<!-- ```sh -->
<!-- pip install dakarafeeder -->
<!-- ``` -->

If you have downloaded the repo, you can install the package directly with:

```sh
python setup.py install
```

## Usage

The package provides the `dakara-play-vlc` command which runs the player:

```sh
dakara-play-vlc
# or
python -m dakara_player_vlc
```

One instance of the Dakara server should be running. For more help:

```sh
dakara-play-vlc -h
# or
python -m dakara_player_vlc -h
```

Before calling the command, you should create a config file with:

```sh
dakara-play-vlc create-config
# or
python -m dakara_player_vlc create-config
```

and complete it with your values. The file is stored in your user space: `~/.config/dakara` on Linux or `$APPDATA\Dakara` on Windows.

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
python setup.py test
```

To check coverage, use the `coverage` command:

```sh
coverage run setup.py test
coverage report -m
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

### Code style

The code follows the [PEP8](https://www.python.org/dev/peps/pep-0008/) style guide (88 chars per line).
Quality of code is checked with [Flake8](https://pypi.org/project/flake8/).
Style is enforced using [Black](https://github.com/ambv/black).
You need to call Black before committing changes.
You may want to configure your editor to call it automatically.
Additionnal checking can be manually performed with [Pylint](https://www.pylint.org/).
