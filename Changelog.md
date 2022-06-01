# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- [#3](https://github.com/dotcs/xkcd-cli/pull/3): Multiple terminals and image protocols are now auto-detected . This includes kitty, iterm and terminals that support the [`sixel` graphic format](https://en.wikipedia.org/wiki/Sixel). Thanks to [MatanZ](https://github.com/MatanZ) for this contribution.
- `--width` CLI option to explicitly set the width of the rendered graphic

### Changed

- Removed CLI option `--use-kitty` in favor of `--terminal-graphics`.


## [1.0.0] - 2022-04-17
### Added

- Fetching and caching comics from the xkcd.com archive
- Support for rendering images directly in kitty through its [`icat` command](https://sw.kovidgoyal.net/kitty/kittens/icat/)
- Add support for rendering comics with fuzzy search throught its titles (default), directly (via `--comic-id` option) or at random choice (via `--random`).