from bs4 import BeautifulSoup, Tag
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from random import randint
from subprocess import Popen, PIPE
from textwrap import wrap
from typing import List, Tuple, Optional
import json
import os
import requests
import shutil
import subprocess
import sys
import tempfile
import typer

BASE_URL = "https://xkcd.com"
ARCHIVE_ENDPOINT = "/archive/"
CACHE_DIR = Path("~", ".cache", "xkcd-cli").expanduser()
CACHE_PATH = Path(CACHE_DIR, "cache.json")
TERM_MAX_WIDTH_CHARS = 80

app = typer.Typer()


@app.callback()
def callback():
    """
    xkcd terminal viewer

    This tool fetches xkcd comics from upstream and allows users to grep a comic
    by selecting it in the terminal.

    It relies on fzf for fuzzy searching the comic titles and kitty to render
    the images in the terminal.
    """
    pass


def setup():
    os.makedirs(CACHE_DIR, exist_ok=True)


@dataclass
class XkcdComicMeta:
    """
    Meta information of a xkcd comic as described in the archive.
    """

    id: int
    href: str
    title: str


@dataclass
class XkcdComic(XkcdComicMeta):
    """
    Full information of a xkcd comic.
    """

    img_src: str
    subtext: str


@dataclass
class Cache:
    """
    Internal representation of all xkcd comics metadata from the official archive.
    """

    last_updated: datetime
    comics: List[XkcdComicMeta]

    @classmethod
    def read(cls, path: Path):
        content = json.load(open(path))
        last_updated = datetime.fromisoformat(content["last_updated"])
        comics = [XkcdComicMeta(**c) for c in content["comics"]]
        return Cache(last_updated=last_updated, comics=comics)

    def write(self, path: Path):
        with open(path, "w") as f:
            f.write(json.dumps(asdict(self), default=str))


def fetch_xkcd_archive() -> List[XkcdComicMeta]:
    """
    Fetches all xkcd comic meta information from the archive
    page: https://xkcd.com/archive/
    Since a single page contains all historic xkcds, no pagination logic is needed.
    """
    r = requests.get(BASE_URL + ARCHIVE_ENDPOINT)
    r.raise_for_status()
    text = r.text

    soup = BeautifulSoup(text, "html.parser")
    comics: List[XkcdComicMeta] = []

    container = soup.find(id="middleContainer")
    assert isinstance(container, Tag)

    for el in container.find_all("a"):
        href = el.get("href")
        title = el.get_text()
        cid = int(href.replace("/", ""))

        meta = XkcdComicMeta(id=cid, href=href, title=title)
        comics.append(meta)

    return comics


def fetch_xkcd_comic(comic: XkcdComicMeta) -> XkcdComic:
    """
    Fetch an individual xkcd comic from upstream.
    """
    r = requests.get(BASE_URL + comic.href)
    r.raise_for_status()
    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    comic_soup = soup.find(id="comic")
    assert isinstance(comic_soup, Tag)
    img = comic_soup.find("img")
    assert isinstance(img, Tag)
    img_src = img.get("src")
    assert isinstance(img_src, str)
    img_src = "https:" + img_src
    subtext = img.get("title")
    assert isinstance(subtext, str)
    return XkcdComic(
        title=comic.title,
        id=comic.id,
        href=comic.href,
        img_src=img_src,
        subtext=subtext,
    )


def choice_fzf(fzf_cmd: Path, comics: List[XkcdComicMeta]) -> Tuple[bytes, bytes]:
    """
    Uses fzf to select a comic by its title.
    """
    titles = [str(c.id) + ": " + c.title for c in comics]
    content = "\n".join(titles)

    p = Popen([fzf_cmd], stdin=PIPE, stdout=PIPE)
    assert p.stdin
    p.stdin.write(content.encode())
    p.stdin.flush()
    stdout, stderr = p.communicate()
    return stdout, stderr


def _update_cache_if_outdated(
    cache_filename: Path,
    cache_timeout: timedelta = timedelta(hours=24),
) -> Cache:
    """
    Updates the cache if it is older than the last updated timestamp plus the
    cache_timeout.
    """
    cache = Cache.read(cache_filename)
    if datetime.utcnow() > (cache.last_updated + cache_timeout):
        # Transparently create cache for the user if the cache is older than the
        # cache timeout.
        cache = _update_cache(cache_filename)
    return cache


def _update_cache(cache_filename: Path) -> Cache:
    """
    Updates the cache by fetching all comics from the xkcd archive page and
    updating the cache file on disk.
    """
    dt = datetime.utcnow()
    comics = fetch_xkcd_archive()

    cache = Cache(last_updated=dt, comics=comics)
    cache.write(cache_filename)
    return cache


@app.command()
def update_cache(
    cache_filename: Path = typer.Option(
        CACHE_PATH,
        writable=True,
        help="Path to the cache file.",
    )
):
    """
    Updates the cache file by fetching the latest comics from the xkcd archive website.
    """
    _update_cache(cache_filename)
    typer.echo("Cache updated 👍")


@app.command()
def show(
    use_kitty: bool = typer.Option(
        "kitty" in os.getenv("TERM", "").lower(),
        help=(
            "Defines if the output will be optimized for the kitty terminal by "
            "rendering the image in the terminal window"
        ),
    ),
    fzf_cmd: Path = typer.Option(
        shutil.which("fzf") or os.getenv("FZF_CMD"),
        help="Path to the fzf tool",
    ),
    kitty_cmd: Path = typer.Option(
        shutil.which("kitty") or os.getenv("KITTY_CMD"),
        help="Path to the kitty terminal",
    ),
    kitty_scale_up: bool = typer.Option(
        True, help="Scales the image up to max possible width if kitty is being used."
    ),
    latest: bool = typer.Option(
        False,
        help="""\
        Fetches and renders the latest xkcd without going through a selection first.
        """,
    ),
    random: bool = typer.Option(False, help="Fetches and renders a random xkcd comic."),
    comic_id: Optional[int] = typer.Option(
        None,
        help="Renders a comic with a certain ID.",
    ),
    cache: bool = typer.Option(
        True,
        help="""\
        Defines if a cache should be used for listing all available xkcd comics.
        Otherwise calls the xkcd archive endpoint to gather the list of comics
        (slower).""",
    ),
    cache_filename: Path = typer.Option(
        CACHE_PATH,
        exists=False,
        readable=True,
        help="Path to the cache file.",
    ),
):
    """
    Show an individual xkcd comic.
    """
    if cache:
        if not cache_filename.exists():
            # Transparently create cache for the user if cache does not yet exist.
            _update_cache(cache_filename)

        content = _update_cache_if_outdated(cache_filename)
        comics = content.comics
    else:
        # Bypass cache and read fetched results directly
        comics = fetch_xkcd_archive()

    if random:
        meta = comics[randint(0, len(comics))]
    elif latest:
        meta = comics[0]
    elif comic_id is not None:
        try:
            meta = next(c for c in comics if c.id == comic_id)
        except StopIteration:
            typer.echo(
                f"""\
Comic with ID {comic_id} is unknown. Sometimes this happens because the cache is \
outdated. Please use the 'update-cache' command to fetch most recent comics from \
xkcd upstream.""",
                err=True,
            )
            sys.exit(1)
    else:
        stdout, _ = choice_fzf(fzf_cmd, comics)
        choice = stdout.decode("UTF-8").strip()
        try:
            choice_title = choice.split(":")[1].strip()
        except IndexError:
            # Happens if user uses ctrl+c to exit selection
            typer.echo("Unknown index. Abort.", err=True)
            sys.exit(1)

        meta = next(c for c in comics if c.title == choice_title)
    comic = fetch_xkcd_comic(meta)

    wrapped_title = "\n".join(wrap(comic.title, width=TERM_MAX_WIDTH_CHARS))
    typer.echo(typer.style(wrapped_title, bold=True) + f" ({comic.id})")

    # Kitty and the alternative method based on xdg-open would support rendering
    # images directly from an HTTP endpoint but we find it cleaner to download
    # the file first and serve it from local disk.
    with tempfile.TemporaryDirectory() as tempdir:
        r = requests.get(comic.img_src)
        r.raise_for_status()
        tmp_img_path = Path(tempdir, str(comic.id) + ".png", stream=True)
        with open(tmp_img_path, "wb") as f:
            for chunk in r:
                f.write(chunk)
        if not use_kitty:
            cmd = [
                "xdg-open",
                tmp_img_path,
            ]
            subprocess.run(cmd, stdout=None, stderr=None)
        else:
            cmd = [
                kitty_cmd,
                "+kitten",
                "icat",
                "--align=left",
                "--scale-up" if kitty_scale_up else None,
                tmp_img_path,
            ]
            # Remove any None values to have a list of PathLike objects
            cmd_filtered: List[os.PathLike] = list(filter(lambda x: x is not None, cmd))
            subprocess.run(cmd_filtered)
    typer.echo("\n".join(wrap(comic.subtext, width=TERM_MAX_WIDTH_CHARS)))


def main():
    setup()
    app()


if __name__ == "__main__":
    main()
