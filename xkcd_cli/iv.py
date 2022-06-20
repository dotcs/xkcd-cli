#!/usr/bin/python3
import shutil
import sys
import termios
import atexit
import select
from base64 import standard_b64encode
from typing import BinaryIO, Literal, Optional, Set, TextIO, Tuple, Union
import subprocess

Protocol = Union[
    Literal["iterm"], Literal["kitty"], Literal["kitty+"], Literal["sixel"]
]


class IV:
    protocols: Set[Protocol] = set(("iterm", "kitty", "kitty+", "sixel"))
    protocol: Optional[Protocol]
    kitty: Optional[bool] = None
    ex_kitty: Optional[bool] = None
    sixel: Optional[bool] = None
    iterm: Optional[bool] = None

    def __init__(self, protocol: Optional[Union[Protocol, Literal["auto"]]] = None):
        self.libsixel = None
        self.stdin_fd = sys.stdin.fileno()
        self.saved_term = termios.tcgetattr(self.stdin_fd)
        atexit.register(self.set_normal_term)
        if protocol == "auto":
            self.auto_protocol()
        elif protocol in self.protocols:
            self.protocol = protocol
        else:
            self.protocol = None

    @staticmethod
    def scale_fit(
        w: int,
        h: int,
        ow: int,
        oh: int,
        aspect: bool = True,
        up: bool = False,
        debug: bool = False,
    ) -> Tuple[int, int]:
        """Utility function which calculates new dimension of image"""
        if debug:
            print(w, h, ow, oh, aspect)
        a = ow / oh
        if not up and w > ow:
            w = ow
        if not up and h > oh:
            h = oh
        if w > 0 and h > 0:
            if aspect:
                if w / h > a:
                    return int(h * a), h
                else:
                    return w, int(w / a)
            else:
                return w, h
        elif w > 0:
            if aspect:
                return w, int(w / a)
            else:
                return w, oh
        elif h > 0:
            if aspect:
                return int(h * a), h
            else:
                return ow, h
        else:
            return ow, oh

    # Send and escape sequence and read reply.
    def set_normal_term(self) -> None:  # pragma: no cover
        """
        Reset the terminal to normal mode.
        """
        termios.tcsetattr(self.stdin_fd, termios.TCSAFLUSH, self.saved_term)

    def set_raw_like_term(self) -> None:  # pragma: no cover
        """
        Sets the terminal in raw-like mode (noncanonical mode + nonecho mode).

        See also: https://docs.python.org/3.8/library/termios.html#termios.tcgetattr
        """
        new_term = termios.tcgetattr(self.stdin_fd)
        new_term[3] = new_term[3] & ~termios.ICANON & ~termios.ECHO  # lflags
        termios.tcsetattr(self.stdin_fd, termios.TCSAFLUSH, new_term)

    def terminal_request(
        self,
        cmd: str,
        end: str,
        out: BinaryIO = sys.stdout.buffer,
        in_: TextIO = sys.stdin,
    ) -> str:
        """
        In raw-like term, run the `cmd` and read from stdin until the matching
        `end` character has been found. After executing the command, the command
        terminal is switched back to normal mode.
        """
        try:
            self.set_raw_like_term()
            ret = ""
            out.write(cmd.encode("ascii"))
            out.flush()
            timeout = 0.2  # in seconds
            dr, _, _ = select.select(
                [in_], [], [], timeout
            )  # wait for response on stdin
            if dr != []:
                while True:
                    c = in_.read(1)
                    ret += c
                    if c in end:
                        break
        finally:
            # ensure to switch back to normal terminal mode
            self.set_normal_term()
        return ret

    # Methods to send show image in various protocols.
    def kitty_remove_placement(self, p: int = -1) -> None:
        """
        Delete an image.
        See kitty documentation for details: https://sw.kovidgoyal.net/kitty/graphics-protocol/#deleting-images
        """
        sys.stdout.buffer.write(f"\033_Ga=d,i=-1,d=z,z={p},q=2\033\\".encode("ascii"))
        sys.stdout.flush()

    @staticmethod
    def image_data_and_metadata(data: bytes) -> Tuple[bytes, Optional[str], int, int]:
        from PIL import Image
        import io

        image = Image.open(io.BytesIO(data))
        if image.format == "PNG":
            data = standard_b64encode(data)
        else:
            data = standard_b64encode(image.tobytes())

        return data, image.format, image.height, image.width

    def kitty_show_file(
        self,
        data: bytes,
        debug: bool = False,
        extended: Optional[bool] = None,
        out: BinaryIO = sys.stdout.buffer,
        **params: int,
    ) -> None:
        if extended or (extended is None and self.ex_kitty):
            # if rendering JPG data is supported, no additional action is required
            data = standard_b64encode(data)
        else:
            # if rendering JPG data is not supported, either use PNG directly or
            # use raw image instead
            data, img_format, img_height, img_width = IV.image_data_and_metadata(data)
            if img_format != "PNG":
                params["f"] = 24  # 24-bit RGB data
                params["s"] = img_width
                params["v"] = img_height

        if debug:
            print(len(data), "bytes", file=sys.stderr)

        # See explanation of kitty control data keys here:
        # https://sw.kovidgoyal.net/kitty/graphics-protocol/?highlight=image#control-data-reference
        cmd = dict()
        cmd["a"] = "T"  # simultaneously transmit and display an image
        cmd["f"] = 100  # f=100 indicates PNG data
        cmd["q"] = 2  # Suppress responses from the terminal to this graphics command
        for k in ("C", "p", "i", "z", "a", "f", "q", "s", "v", "c", "r"):
            if k in params:
                cmd[k] = params[k]

        # Write image to kitty terminal in chunks, `m=1` means there is more
        # chunked data available.
        first = True
        s = 0
        chunk_size = 4096
        while s < len(data):
            w = b"\033_G"
            if first:
                for l, v in cmd.items():
                    w += f"{l}={v},".encode("ascii")
                    first = False
            s += chunk_size
            w += f"m={int(s<len(data))};".encode("ascii")
            w += data[s - chunk_size : s]
            w += b"\033\\"
            out.write(w)
            out.flush()

    def iterm_show_file(
        self,
        data: bytes,
        debug: bool = False,
        out: BinaryIO = sys.stdout.buffer,
        **params: int,
    ):
        data = standard_b64encode(data)
        if debug:
            print(len(data), "bytes", file=sys.stderr)
        extras = ""
        if "C" in params and params["C"] == 1:
            extras += ";doNotMoveCursor=1"
        if "width" in params:
            extras += f";width={params['width']}"
        out.write(
            b"\033]1337;File=inline=1" + bytes(extras, "ascii") + b":" + data + b"\007"
        )
        out.flush()

    def _setup_libsixel_or_fallback(self):  # pragma: no cover
        try:
            from libsixel import encoder  # type: ignore

            self.encoder = encoder
            self.libsixel = True
        except ModuleNotFoundError:
            self.libsixel = False

    def sixel_show_file(
        self,
        filename: str,
        w: int = -1,
        h: int = -1,
        out: BinaryIO = sys.stdout.buffer,
    ) -> None:
        if self.libsixel is None:
            self._setup_libsixel_or_fallback()
        if self.libsixel:
            enc = self.encoder.Encoder()
            enc.setopt(self.encoder.SIXEL_OPTFLAG_WIDTH, str(w) if w > 0 else "auto")
            enc.setopt(self.encoder.SIXEL_OPTFLAG_HEIGHT, str(h) if h > 0 else "auto")
            enc.setopt(self.encoder.SIXEL_OPTFLAG_COLORS, "256")
            enc.encode(filename)
        elif shutil.which("convert") is not None:
            # Use imagemagick convert command as a fallback to convert to sixel format.
            # See also: https://konfou.xyz/posts/sixel-for-terminal-graphics/
            command = ["convert", filename]
            if w > 0 or h > 0:
                command += ["-geometry", f"{w if w > 0 else ''}x{h if h > 0 else ''}"]
            command += ["sixel:-"]
            res = subprocess.run(command, stdout=subprocess.PIPE)
            out.write(res.stdout)
            out.flush()
        else:
            out.write("Could not find an terminal image renderer.".encode("ascii"))
            out.flush()

    def show_image(
        self,
        image: Union[str, bytes],
        w: int = -1,
        h: int = -1,
        newline: bool = False,
        fitwidth: bool = False,
        fitheight: bool = False,
        upscale: bool = False,
        **params: int,
    ):
        """
        Display an image in the current terminal instance.

        Uses the following logic:
        1. If `fitwidth` then scale the image (keeping aspect ratio) so it is as
           wide as the terminal.
        2. If `fitheight` then scale the image (keeping aspect ratio) so it is as
            high as the terminal.
        3. If both are given uses the smaller scale of the above.
        4. Otherwise: If `w` is positive, scale the image (keeping aspect ratio)
           to the given width.
        5. If `h` is positive, scale the image (keeping aspect ratio) to the given
           height.
        6. If both are given uses the smaller scale of the above
        7. In all cases if the scaling factor is larger than 1, it is applied
           only if `upscale` is true.
        """
        if self.protocol not in self.protocols:
            return
        params = {}
        if fitwidth:
            _, w = self.terminal_pixel_size()
        if fitheight:
            h, _ = self.terminal_pixel_size()
        if isinstance(image, str):
            self._show_image_str(image, w, h, upscale=upscale, **params)
        elif isinstance(image, bytes):
            self._show_image_bytes(image, w, h, **params)
        if newline:
            print()

    def _show_image_str(
        self,
        image: str,
        w: int = -1,
        h: int = -1,
        upscale: bool = False,
        **params: int,
    ):
        if self.protocol == "sixel":
            self.sixel_show_file(image, w, h)
        else:
            if w > 0 or h > 0:
                from PIL import Image
                import io

                im = Image.open(image)
                x, y = im.size
                nw, nh = IV.scale_fit(w, h, x, y, up=upscale)
                data = io.BytesIO()
                im.resize((nw, nh)).save(data, format=im.format)
                data.seek(0)
                data = data.read()
            else:
                data = open(image, "rb").read()
            if self.protocol == "iterm":
                self.iterm_show_file(data, **params)
            elif self.protocol is not None and self.protocol.startswith("kitty"):
                self.kitty_show_file(data, **params)

    def _show_image_bytes(
        self,
        image: bytes,
        w: int = -1,
        h: int = -1,
        **params: int,
    ):
        if self.protocol == "sixel":
            import tempfile

            file = tempfile.TemporaryFile()
            file.write(image)
            self.sixel_show_file(file.name, w, h)
        else:
            if self.protocol == "iterm":
                self.iterm_show_file(image, **params)
            elif self.protocol is not None and self.protocol.startswith("kitty"):
                self.kitty_show_file(image, **params)

    # Get various sizes of screen
    def terminal_pixel_size(self) -> Tuple[int, int]:
        """
        Use ANSI escape code to determine the terminal screen dimensions in
        pixels of the area that may be covered by graphics.
        See also: https://notes.burke.libbey.me/ansi-escape-codes/
        See also: https://sw.kovidgoyal.net/kitty/graphics-protocol/#getting-the-window-size
        """
        size_ret = self.terminal_request("\x1b[14t", "t").split(";")
        if len(size_ret) < 3 or not size_ret[0][-1] == "4":
            terminal_width, terminal_height = -1, -1
        else:
            terminal_height, terminal_width = int(size_ret[1]), int(size_ret[2][:-1])
        return terminal_height, terminal_width

    def cell_size(self) -> Tuple[int, int]:
        """
        Use ANSI escape code to determine the cell dimensions.
        See also: https://notes.burke.libbey.me/ansi-escape-codes/
        """
        size_ret = self.terminal_request("\x1b[16t", "t").split(";")
        if len(size_ret) < 3 or not size_ret[0][-1] == "6":
            cell_width, cell_height = -1, -1
        else:
            cell_height, cell_width = int(size_ret[1]), int(size_ret[2][:-1])
        return cell_height, cell_width

    def iterm_cell_size(self) -> Tuple[int, int]:
        """
        Use proprietary ANSI escape code to termine cell dimensions in iTerm.
        See also: https://iterm2.com/documentation-escape-codes.html
        """
        size_ret = self.terminal_request(
            "\x1b]1337;ReportCellSize\x07", "\x07\\"
        ).split(";")
        if len(size_ret) < 3 or not size_ret[1].startswith("ReportCellSize="):
            cell_width, cell_height = -1, -1
        else:
            cell_height, cell_width = float(size_ret[1].split("=")[1]), float(
                size_ret[2].strip("\07\\\x1b")
            )
            if len(size_ret) == 4:
                factor = float(size_ret[3].strip("\07\\\x1b"))
            else:
                factor = 1
            cell_height, cell_width = round(cell_height * factor), round(
                cell_width * factor
            )

        return cell_height, cell_width

    def terminal_cell_size(self) -> Tuple[int, int]:
        """
        Use ANSI escape code to determine the terminal dimensions as number of
        lines and columns.
        See also: https://notes.burke.libbey.me/ansi-escape-codes/
        """
        size_ret = self.terminal_request("\x1b[18t", "t").split(";")
        if len(size_ret) < 3 or not size_ret[0][-1] == "8":
            terminal_lines, terminal_cols = -1, -1
        else:
            terminal_lines, terminal_cols = int(size_ret[1]), int(size_ret[2][:-1])
        return terminal_lines, terminal_cols

    # Identify supported protocols
    def have_iterm(self) -> bool:
        """
        Identify if the current terminal is an `iterm` terminal instance by
        running a proprietary command that only works on those terminals.

        This method sets the `iterm` variable on the current instance.
        """
        if self.iterm is None:
            self.iterm = -1 not in self.iterm_cell_size()
        return self.iterm

    def have_kitty(self) -> bool:
        """
        Identify if the current terminal is a `kitty` terminal instance by
        sending a sample 24-bit RGB image with dimensions 1x1 (params s, v) in
        query action mode (a=q).

        This method sets the `kitty` variable on the current instance.

        See also: https://sw.kovidgoyal.net/kitty/graphics-protocol/?highlight=image#querying-support-and-available-transmission-mediums
        """
        if self.kitty is None:
            self.kitty = "OK" in self.terminal_request(
                "\x1b_Gi=31,s=1,v=1,a=q,t=d,f=24;AAAA\x1b\\", "\\"
            )
        return self.kitty

    def have_extended_kitty(self) -> bool:
        """
        Determine if extended support for JPG images is available.
        Note that JPG support is implemented by a limited number of terminals,
        e.g. konsole or wezterm, but not kitty.

        This method sets the `ex_kitty` variable, and the `kitty` variable if
        unset, on the currrent instance.
        """
        if self.ex_kitty is None:
            # A small jpeg from https://stackoverflow.com/questions/2253404
            self.ex_kitty = "OK" in self.terminal_request(
                "\x1b_Gi=31,s=1,v=1,a=q,t=d,f=100;"
                + "/9j/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wgALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAAA//aAAgBAQAAAAE//9k="
                + "\x1b\\",
                "\\",
            )
            if self.ex_kitty and self.kitty is None:
                self.kitty = True
        return self.ex_kitty

    def have_sixel(self) -> bool:
        """
        Determine if sixel support is available in the current terminal instance
        through ANSI escape code.

        This method sets the `sixel` variable on the current instance.
        """
        if self.sixel is None:
            # reply starts with '\x1b[?' and ends with 'c'
            self.sixel = "4" in self.terminal_request("\x1b[c", "c")[3:-1].split(";")
        return self.sixel

    def auto_protocol(self) -> Optional[Protocol]:
        """
        Automatically detect the terminal image protocol by testing various
        methods on-the-fly.

        This method sets the `protocol` variable on the current instance.
        """
        protocol: Optional[Protocol] = None
        if self.have_extended_kitty():
            protocol = "kitty+"
        elif self.have_iterm():
            protocol = "iterm"
        elif self.have_kitty():
            protocol = "kitty"
        elif self.have_sixel():
            protocol = "sixel"
        self.protocol = protocol
        return protocol
