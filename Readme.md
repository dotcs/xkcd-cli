# xkcd cli tool

Get your daily dose of [xkcd] directly from the terminal! 🤩

[xkcd] is a webcomic created by [Randall Munroe][munroe]. 
It is a comic of Language, Math, Romance and Sarcasm and a [couple of other categories][explain-xkcd-categories].

If [kitty] is used as the terminal, the xkcd comic will be rendered directly in the terminal, otherwise the default viewer for PNG images is used.
This tool requires [fzf] to be installed on the machine to filter available comics by their title. 

## Installation

### With pip

Install this package directly from the [Python Package Index (PyPI)][pypi-repo].
The CLI tool requires Python >= 3.8 to be installed.

```console
$ pip install dcs-xkcd-cli
```

This will install a CLI tool named `xkcd` which can be used as described below.

### With pipx

Installation with [pipx] is similar to the pip variant above, but uses `pipx` instead of `pip`.

```console
$ pipx install dcs-xkcd-cli
```

Note that with pipx, this package can be tried out without the need to install it permanently.

```console
$ pipx run dcs-xkcd-cli <args>
```


## Usage

### Search by title

```console
$ xkcd show
```

This functionality requires [fzf] to be installed.

### Show latest xkcd comic

```console
$ xkcd show --latest
```

### Show random xkcd comic

```console
$ xkcd show --random
```

### Show xkcd comic by its ID

```console
$ xkcd show --comic-id 207
```

### Enforce render optimizations for kitty terminal

```console
$ xkcd show --use-kitty
```

Use this command if the auto-detection of the kitty terminal does not work as expected.
Kitty is auto-detected by inspecting if the `$TERM` variable includes the term `kitty`.

By default the image is upscaled to the terminal width.
Use the `--no-kitty-scale-up` flag to disable this feature if needed.

### Disable or update cache

Under the hood this tool uses a cache which is updated once per day transparently.
The cache is used to remember the list of xkcd comics from the [archive].

To disable the cache, use the following command

```console
$ xkcd show --no-cache
```

To update the cache manually, use the following command
```console
$ xkcd update-cache
```


[fzf]: https://github.com/junegunn/fzf
[kitty]: https://sw.kovidgoyal.net/kitty/
[archive]: https://xkcd.com/archive/
[xkcd]: https://xkcd.com
[munroe]: https://en.wikipedia.org/wiki/Randall_Munroe
[explain-xkcd-categories]: https://www.explainxkcd.com/wiki/index.php/Category:Comics_by_topic
[pypi-repo]: https://pypi.org/project/dcs-xkcd-cli/
[pipx]: https://pypa.github.io/pipx/
