#!/usr/bin/python3
import sys
import termios
import tty
import atexit
from select import select
from base64 import standard_b64encode


class IV:
    protocols = set({"iterm", "kitty", "kitty+", "sixel"})
    kitty = None
    ex_kitty = None
    sixel = None
    iterm = None

    def __init__(self, protocol=None):
        self.libsixel = None
        self.stdin_fd = sys.stdin.fileno()
        self.saved_term = termios.tcgetattr(self.stdin_fd)
        atexit.register(self.set_normal_term)
        if protocol == "auto":
            self.auto_protocol()
        elif protocol in ("iterm", "kitty", "kitty+", "sixel"):
            self.protocol = protocol
        else:
            self.protocol = ""

    # Utility function which calculates new dimension of image
    def scale_fit(self, w, h, ow, oh, aspect=True, up=False, debug=False):
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
    def set_normal_term(self):
        termios.tcsetattr(self.stdin_fd, termios.TCSAFLUSH, self.saved_term)

    def terminal_request(self, cmd, end):
        new_term = termios.tcgetattr(self.stdin_fd)
        new_term[3] = new_term[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(self.stdin_fd, termios.TCSAFLUSH, new_term)
        ret = ""
        print(cmd, end="", flush=True)
        dr, _, _ = select([sys.stdin], [], [], 0.2)
        if dr != []:
            while True:
                c = sys.stdin.read(1)
                ret += c
                if c in end:
                    break
        self.set_normal_term()
        return ret

    # Methods to send show image in various protocols.
    def kitty_remove_placement(self, p=-1):
        sys.stdout.buffer.write(f"\033_Ga=d,i=-1,d=z,z={p},q=2\033\\".encode("ascii"))
        sys.stdout.flush()

    def kitty_show_file(self, data, debug=False, extended=None, **params):
        if extended or (extended is None and self.ex_kitty):
            data = standard_b64encode(data)
        else:
            from PIL import Image
            import io

            image = Image.open(io.BytesIO(data))
            if image.format == "PNG":
                data = standard_b64encode(data)
            else:
                data = standard_b64encode(image.tobytes())
                params["f"] = 24
                params["s"] = image.width
                params["v"] = image.height
        if debug:
            print(len(data), "bytes", file=sys.stderr)
        cmd = dict()
        cmd["a"] = "T"
        cmd["f"] = 100
        cmd["q"] = 2
        for k in ("C", "p", "i", "z", "a", "f", "q", "s", "v", "c", "r"):
            if k in params:
                cmd[k] = params[k]
        first = True
        s = 0
        while s < len(data):
            w = b"\033_G"
            if first:
                for l, v in cmd.items():
                    w += f"{l}={v},".encode("ascii")
                    first = False
            s += 4096
            w += f"m={int(s<len(data))};".encode("ascii")
            w += data[s - 4096 : s]
            w += b"\033\\"
            sys.stdout.buffer.write(w)
            sys.stdout.flush()

    def iterm_show_file(self, data, debug=False, **params):
        data = standard_b64encode(data)
        if debug:
            print(len(data), "bytes", file=sys.stderr)
        extras = ""
        if "C" in params and params["C"] == 1:
            extras += ";doNotMoveCursor=1"
        if "width" in params:
            extras += f";width={params['width']}"
        sys.stdout.buffer.write(
            b"\033]1337;File=inline=1" + bytes(extras, "ascii") + b":" + data + b"\007"
        )
        sys.stdout.flush()

    def sixel_show_file(self, filename, w=-1, h=-1):
        if self.libsixel is None:
            try:
                from libsixel import encoder

                self.encoder = encoder
                self.libsixel = True
            except ModuleNotFoundError:
                self.libsixel = False
                import subprocess

                self.subprocess = subprocess
        if self.libsixel:
            enc = self.encoder.Encoder()
            if w > 0:
                enc.setopt(self.encoder.SIXEL_OPTFLAG_WIDTH, str(w))
                enc.setopt(self.encoder.SIXEL_OPTFLAG_HEIGHT, str(h))
            enc.setopt(self.encoder.SIXEL_OPTFLAG_COLORS, "256")
            enc.encode(filename)
        else:
            command = ["convert", filename]
            if w > 0:
                command += ["-geometry", f"{w}x{h}"]
            command += ["sixel:-"]
            res = self.subprocess.run(command, stdout=self.subprocess.PIPE)
            sys.stdout.buffer.write(res.stdout)
            sys.stdout.flush()

    def show_image(
        self,
        image,
        w=-1,
        h=-1,
        newline=False,
        fitwidth=False,
        fitheight=False,
        upscale=False,
        **params,
    ):
        if self.protocol not in self.protocols:
            return
        params = {}
        if fitwidth:
            _, w = self.pixel_size()
        if fitheight:
            h, _ = self.pixel_size()
        if type(image) == str:
            if self.protocol == "sixel":
                self.sixel_show_file(image, w, h)
            else:
                if w > 0 or h > 0:
                    from PIL import Image
                    import io

                    im = Image.open(image)
                    x, y = im.size
                    nw, nh = self.scale_fit(w, h, x, y, up=upscale)
                    data = io.BytesIO()
                    im.resize((nw, nh)).save(data, format=im.format)
                    data.seek(0)
                    data = data.read()
                else:
                    data = open(image, "rb").read()
                if self.protocol == "iterm":
                    self.iterm_show_file(data, **params)
                elif self.protocol.startswith("kitty"):
                    self.kitty_show_file(data, **params)
                if newline:
                    print()
        else:
            if self.protocol == "sixel":
                import tempfile

                file = tempfile.TemporaryFile()
                file.write(image)
                self.sixel_show_file(file, w, h)
            else:
                if self.protocol == "iterm":
                    self.iterm_show_file(image, **params)
                elif self.protocol.startswith("kitty"):
                    self.kitty_show_file(image, **params)
                if newline:
                    print()

    # Get various sizes of screen
    def pixel_size(self):
        size_ret = self.terminal_request("\x1b[14t", "t").split(";")
        if len(size_ret) < 3 or not size_ret[0][-1] == "4":
            terminal_width, terminal_height = -1, -1
        else:
            terminal_height, terminal_width = int(size_ret[1]), int(size_ret[2][:-1])
        return terminal_height, terminal_width

    def cell_size(self):
        size_ret = self.terminal_request("\x1b[16t", "t").split(";")
        if len(size_ret) < 3 or not size_ret[0][-1] == "6":
            cell_width, cell_height = -1, -1
        else:
            cell_height, cell_width = int(size_ret[1]), int(size_ret[2][:-1])
        return cell_height, cell_width

    def iterm_cell_size(self):
        size_ret = self.terminal_request("\x1b]1337;ReportCellSize\x07", "\x07").split(
            ";"
        )
        if len(size_ret) < 3 or not size_ret[1].startswith("ReportCellSize="):
            cell_width, cell_height = -1, -1
        else:
            cell_height, cell_width = float(size_ret[1].split("=")[1]), float(
                size_ret[2].strip("\07")
            )
            if len(size_ret) == 4:
                factor = float(size_ret[3].strip("\07"))
            else:
                factor = 1
            cell_height, cell_width = round(cell_height * factor), round(
                cell_width * factor
            )

        return cell_height, cell_width

    def terminal_size(self):
        size_ret = self.terminal_request("\x1b[18t", "t").split(";")
        if len(size_ret) < 3 or not size_ret[0][-1] == "8":
            terminal_lines, terminal_cols = -1, -1
        else:
            terminal_lines, terminal_cols = int(size_ret[1]), int(size_ret[2][:-1])
        return terminal_lines, terminal_cols

    # Identify supported protocols
    def have_iterm(self):
        if self.iterm is None:
            self.iterm = -1 not in self.iterm_cell_size()
        return self.iterm

    def have_kitty(self):
        if self.kitty is None:
            self.kitty = "_G" in self.terminal_request(
                "\x1b_Gi=31,s=1,v=1,a=q,t=d,f=24;AAAA\x1b\\", "\\"
            )
        return self.kitty

    def have_extended_kitty(self):
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

    def have_sixel(self):
        if self.sixel is None:
            # reply starts with '\x1b[?' and ends with 'c'
            self.sixel = "4" in self.terminal_request("\x1b[c", "c")[3:-1].split(";")
        return self.sixel

    def auto_protocol(self):
        if self.have_extended_kitty():
            self.protocol = "kitty+"
        elif self.have_iterm():
            self.protocol = "iterm"
        elif self.have_kitty():
            self.protocol = "kitty"
        elif self.have_sixel():
            self.protocol = "sixel"
        else:
            self.protocol = "None"
        return self.protocol
