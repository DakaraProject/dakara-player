# Changelog

<!---
## 0.0.1 - 1970-01-01

### Added

- New stuff.

### Changed

- Changed stuff.

### Deprecated

- Deprecated stuff.

### Removed

- Removed stuff.

### Fixed

- Fixed stuff.

### Security

- Security related fix.
-->


## Unreleased

### Added

- Mac support.

## 1.8.1 - 2022-12-18

### Fixed

- Fix missing reference to `line-awesome.json`.

## 1.8.0 - 2022-11-23

### Update notes

The project uses now a library to manage user directories on the different operating systems, the location was modified for Windows:

```cmd
# cmd
mkdir %APPDATA%\DakaraProject
move %APPDATA%\Dakara %APPDATA%\DakaraProject\dakara
# powershell
mkdir $env:APPDATA\DakaraProject
mv $env:APPDATA\Dakara $env:APPDATA\DakaraProject\dakara
```

### Added

- Fonts are automatically installed on Windows.
- Songs can be restarted, rewound, or fast forwarded during playback.
  Duration of the rewind/fast forward jump is 10 seconds by default and can be customized in the config file using the `player.durations.rewind_fast_forward_duration` key.
- Support of mpv 0.34.0 and above.
- The user can force the version of mpv to use in config using the `player.mpv.force_version` key.
- Support Python 3.10 and 3.11.

### Changed

- Fonts are searched in system and user directories recursively.
- Name of the command changed from `dakara-play` to `dakara-player`.
- Play command moved from `dakara-play` to `dakara-player play`.
- A better font icon is used (especially with a singer-style microphone).
- Elements displayed on the transition screen use now the same layout as on the web client.

### Fixed

- Stopping the karaoke when a song is paused using mpv was sending a resumed callback to the server, that was rejected.
  This behavior was fixed.

### Removed

- Dropped support of Python 3.6.

## 1.7.0 - 2021-06-20

### Update notes

Since the project has been renamed, you should migrate your configuration file, if you have one.
On Linux:

```sh
mv ~/.config/dakara/player_vlc.yaml ~/.config/dakara/player.yaml
```

On Windows:

```cmd
# cmd
move %APPDATA%\Dakara\player_vlc.yaml %APPDATA%\Dakara\player.yaml
# powershell
mv $env:APPDATA\Dakara\player_vlc.yaml $env:APPDATA\Dakara\player.yaml
```

### Added

- mpv is supported as an alternative player.
  In the config file, the player can be selected in the `player.player_name` key.
  Current accepted values are `vlc` and `mpv`.
- VLC runs in a permanent Tkinter window if possible, which doesn't close between media.
  The old behavior can be restored in config file using the `player.vlc.use_default_window` key.
- The default backgrounds and text templates can be copied to user directory with the command `dakara-play create-resources`, to be easily customized.

### Changed

- The project is renamed:
  - Repository name: `dakara-player-vlc` > `dakara-player`;
  - Module name `dakara_player_vlc` > `dakara_player`;
  - Pypi package name `dakaraplayervlc` > `dakaraplayer`;
  - Config file name `player_vlc.yamd` > `player.yaml`;
  - Command name `dakara-play-vlc` > `dakara-play`.
- Custom backgrounds and text templates are loaded from the user directory: `~/.local/share/dakara/player` on Linux and `$APPDATA\Dakara\player` on Windows.
  It is not possible to specify a custom lookup directory anymore, so the config keys `player.backgrounds.directory` and `player.templates.directory` are now ignored.

## 1.6.0 - 2020-09-05

### Added

- Manage instrumental tracks.

## 1.5.2 - 2019-12-06

### Fixed

- Dead symbolic links to fonts in user font directory are now automatically removed to avoid crash.
- Some installed fonts could be left uninstalled, this problem has been fixed.

## 1.5.1 - 2019-12-05

### Fixed

- Installation directions in readme.

## 1.5.0 - 2019-12-05

### Added

- The project can be installed with `pip`.

### Changed

- In the config file, the `player.transition_duration` is moved to `player.durations.transition_duration`;
- To run the player, invoke the command `dakara-play-vlc` or `python -m dakara_player_vlc`, instead of `dakara.py`;
- Configuration is now stored in the user directory. You can create a new config file with the command `dakara-play-vlc create-config` or `python -m dakara_player_vlc create-config`.

## 1.4.0 - 2019-05-03

### Changed

- In the config file, the `server.url` parameter is renamed `server.address` and contains the hostname of the server (without `http://` or `https://`). The encryption of the connection is obtained with the `server.ssl` parameter.

## 1.3.0 - 2018-10-07

### Changed

- Better Windows OS support.

## 1.2.1 - 2018-06-04

### Fixed

- Fix documentation inconsistency.

## 1.2.0 - 2018-06-03

### Added

- Tests can be executed with `./tests.py`.
- Resources folder, with default/example templates and backgrounds, is moved: `share` > `dakara_player_vlc/resources`.
- Work link long name can be obtained withe the `| link_type_name` filter.

### Changed

- Config file uses the [Yaml](http://yaml.org/start.html) format and should be `config.yaml`, example file is `config.yaml.example`.
- Calling `dakara.py -d` activates debug logging.

## 1.0.1 - 2017-10-22

### Added

- Changelog.
- Version file.
- Display version in log and idle screen.
- Version bump script.

## 1.0.0 - 2017-10-22

### Added

- First version.
