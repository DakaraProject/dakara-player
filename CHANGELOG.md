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

### Changed

- In the config file, the `player.transition_duration` is moved to `player.durations.transition_duration`.

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
