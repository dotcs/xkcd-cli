# xkcd cli tool

Get your daily dose of [xkcd] directly from the terminal! 🤩

https://user-images.githubusercontent.com/3976183/163873282-f586f312-2643-4b77-af79-89e344091b2f.mp4

[xkcd] is a webcomic created by [Randall Munroe][munroe]. 
It is a comic of Language, Math, Romance and Sarcasm and a [couple of other categories][explain-xkcd-categories].

If [kitty], [iterm] or any terminal that has support for the [sixel] file format is used as the terminal, the xkcd comic will be rendered directly in the terminal, otherwise the default viewer for PNG images is used.
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

### Upscaling / width of comics

By default images are upscaled to match the terminal dimensions.
This behavior can be controlled with the `--terminal-scale-up / --no-terminal-scale-up` options.
Images can be also rendered with an explicit width by using the `--width` CLI option.

```console
$ xkcd show --comic-id 207 --no-terminal-scale-up    # disable scaling
$ xkcd show --comic-id 207 --width 1200              # set explicit width
```


### Disable rendering in terminals

```console
$ xkcd show --no-terminal-graphics
```

This command will disable the automatic image protocol detection and directly open the image with the help of `xdg-open` in the default image viewer.

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
[iterm]: https://iterm2.com/
[sixel]: https://en.wikipedia.org/wiki/Sixel