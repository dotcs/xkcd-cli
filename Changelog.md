# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2022-04-17
### Added

- Fetching and caching comics from the xkcd.com archive
- Support for rendering images directly in kitty through its [`icat` command](https://sw.kovidgoyal.net/kitty/kittens/icat/)
- Add support for rendering comics with fuzzy search throught its titles (default), directly (via `--comic-id` option) or at random choice (via `--random`).