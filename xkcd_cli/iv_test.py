import io
from typing import Any
from unittest import mock
from unittest.mock import Mock, patch
import unittest
from pathlib import Path

from .iv import IV


def test_scale_fit():
    tests = [
        # trivial case, unknown original dimensions
        {
            "params": dict(w=100, h=0, ow=-1, oh=-1, aspect=True, up=False),
            "expect": (-1, -1),
        },
        # same height, width -> no scaling
        {
            "params": dict(w=100, h=10, ow=100, oh=10, aspect=True, up=False),
            "expect": (100, 10),
        },
        # 10x larger with disabled upscaling -> don't upscale
        {
            "params": dict(w=1000, h=100, ow=100, oh=10, aspect=True, up=False),
            "expect": (100, 10),
        },
        # 2x smaller -> downscale
        {
            "params": dict(w=50, h=0, ow=100, oh=10, aspect=True, up=False),
            "expect": (50, 5),
        },
        # 2x smaller with no w value -> downscale
        {
            "params": dict(w=0, h=5, ow=100, oh=10, aspect=True, up=False),
            "expect": (50, 5),
        },
        # 2x smaller with wrong aspect ratio -> downscale
        {
            "params": dict(w=50, h=6, ow=100, oh=10, aspect=True, up=False),
            "expect": (50, 5),
        },
        # 2x smaller with wrong aspect ratio -> downscale
        {
            "params": dict(w=55, h=5, ow=100, oh=10, aspect=True, up=False),
            "expect": (50, 5),
        },
        # 10x larger with upscale allowed -> upscale
        {
            "params": dict(w=1000, h=100, ow=100, oh=10, aspect=True, up=True),
            "expect": (1000, 100),
        },
        # 5x larger with upscale allowed and wrong aspect ratio -> upscale and reset height
        {
            "params": dict(w=500, h=55, ow=100, oh=10, aspect=True, up=True),
            "expect": (500, 50),
        },
        # 5x larger with upscale allowed and wrong aspect ratio -> upscale and reset width
        {
            "params": dict(w=550, h=50, ow=100, oh=10, aspect=True, up=True),
            "expect": (500, 50),
        },
    ]
    for test in tests:
        assert IV.scale_fit(**test["params"]) == test["expect"]


class IvInitMixin:
    def setUp(self):
        super(IvInitMixin, self).setUp()  # type: ignore
        patcher = patch("termios.tcgetattr", return_value=[])
        self.mock_termios_tcgetattr = patcher.start()
        self.addCleanup(patcher.stop)  # type: ignore

        patcher = patch("atexit.register")
        self.mock_atexit_register = patcher.start()
        self.addCleanup(patcher.stop)  # type: ignore

        patcher = patch("sys.stdin.fileno", return_value=1)
        self.mock_sys_stdin_fileno = patcher.start()
        self.addCleanup(patcher.stop)  # type: ignore


class TestIvInit(IvInitMixin, unittest.TestCase):
    def test_tty_setup(self):
        self.mock_termios_tcgetattr.return_value = [123]

        protocol: Any = "foobar"
        iv = IV(protocol)

        self.mock_atexit_register.assert_called_once()
        assert iv.libsixel is None
        assert iv.stdin_fd == 1
        assert iv.saved_term == [123]

    def test_unknown_protocol(self):
        protocol: Any = "foobar"
        iv = IV(protocol)
        assert iv.protocol is None


class TestTerminalRequest(IvInitMixin, unittest.TestCase):
    @patch("select.select")
    def test_happy_path(
        self,
        mock_select: Mock,
    ):
        # mock return value of otherwise hard to test function
        mock_select.return_value = (["OK"], [], [])

        protocol: Any = "foobar"
        iv = IV(protocol)

        # Mock that will modify terminal behavior. In this test case it is only
        # important that they are called.
        iv.set_raw_like_term = Mock()
        iv.set_normal_term = Mock()

        expected = "some_value_t"
        out = io.BytesIO()  # mock output to which cmd will be written
        # mock input from which terminal response will be read
        in_ = io.StringIO(expected)

        cmd = "\x1b[14t"
        actual = iv.terminal_request(cmd, "t", out=out, in_=in_)

        out.seek(0)
        assert out.readline() == cmd.encode("ascii")

        # Ensure that terminal mode has been modified once, first into raw-like
        # mode, later back into normal mode.
        iv.set_raw_like_term.assert_called_once()
        iv.set_normal_term.assert_called_once()

        mock_select.assert_called_once()

        assert actual == expected


class TestTerminalPixelSize(IvInitMixin, unittest.TestCase):
    def test_happy_path(self):
        protocol: Any = "foobar"
        iv = IV(protocol)

        iv.terminal_request = Mock(return_value="\x1b[4;1260;2118t")

        height, width = iv.terminal_pixel_size()
        assert height == 1260
        assert width == 2118

    def test_escape_code_not_working(self):
        protocol: Any = "foobar"
        iv = IV(protocol)

        iv.terminal_request = Mock(return_value="")

        height, width = iv.terminal_pixel_size()
        assert height == -1
        assert width == -1


class TestCellSize(IvInitMixin, unittest.TestCase):
    def test_happy_path(self):
        protocol: Any = "foobar"
        iv = IV(protocol)

        iv.terminal_request = Mock(return_value="\x1b[6;22;9t")

        height, width = iv.cell_size()
        assert height == 22
        assert width == 9

    def test_escape_code_not_working(self):
        protocol: Any = "foobar"
        iv = IV(protocol)

        iv.terminal_request = Mock(return_value="")

        height, width = iv.cell_size()
        assert height == -1
        assert width == -1


class TestTerminalCellSize(IvInitMixin, unittest.TestCase):
    def test_happy_path(self):
        protocol: Any = "foobar"
        iv = IV(protocol)

        iv.terminal_request = Mock(return_value="\x1b[8;56;223t")

        height, width = iv.terminal_cell_size()
        assert height == 56
        assert width == 223

    def test_escape_code_not_working(self):
        protocol: Any = "foobar"
        iv = IV(protocol)

        iv.terminal_request = Mock(return_value="")

        height, width = iv.terminal_pixel_size()
        assert height == -1
        assert width == -1


class TestShowImage(IvInitMixin, unittest.TestCase):
    png_sample = Path("tests") / "assets" / "1x1.png"

    def test_fitwidth(self):
        iv = IV("kitty")

        iv._show_image_str = Mock()
        iv._show_image_bytes = Mock()
        fp = self.png_sample.as_posix()
        iv.terminal_pixel_size = Mock(return_value=(10, 100))
        iv.show_image(fp, 1, 1, fitwidth=True)

        iv._show_image_str.assert_called_once_with(fp, 100, 1, upscale=False)
        iv._show_image_bytes.assert_not_called()

    def test_fitheight(self):
        iv = IV("kitty")

        iv._show_image_str = Mock()
        iv._show_image_bytes = Mock()
        fp = self.png_sample.as_posix()
        iv.terminal_pixel_size = Mock(return_value=(10, 100))
        iv.show_image(fp, 1, 1, fitheight=True)

        iv._show_image_str.assert_called_once_with(fp, 1, 10, upscale=False)
        iv._show_image_bytes.assert_not_called()

    def test_kitty_with_png_bytes(self):
        iv = IV("kitty")

        with open(self.png_sample, "rb") as f:
            img_data = f.read()

        iv.kitty_show_file = Mock()
        iv._show_image_bytes(img_data, 1, 1)
        iv.kitty_show_file.assert_called_once_with(img_data)

    def test_kitty_with_png_str(self):
        iv = IV("kitty")

        iv.kitty_show_file = Mock()
        fp = self.png_sample.as_posix()
        iv._show_image_str(fp, 1, 1)
        iv.kitty_show_file.assert_called_once_with(mock.ANY)
        assert isinstance(iv.kitty_show_file.call_args[0][0], bytes)

    def test_kittyplus_with_png_bytes(self):
        iv = IV("kitty+")

        with open(self.png_sample, "rb") as f:
            img_data = f.read()

        iv.kitty_show_file = Mock()
        iv._show_image_bytes(img_data, 1, 1)
        iv.kitty_show_file.assert_called_once_with(img_data)

    def test_kittyplus_with_png_str(self):
        iv = IV("kitty+")

        iv.kitty_show_file = Mock()
        fp = self.png_sample.as_posix()
        iv._show_image_str(fp, 1, 1)
        iv.kitty_show_file.assert_called_once_with(mock.ANY)
        assert isinstance(iv.kitty_show_file.call_args[0][0], bytes)

    def test_sixel_with_png_bytes(self):
        iv = IV("sixel")

        with open(self.png_sample, "rb") as f:
            img_data = f.read()

        iv.sixel_show_file = Mock()
        iv._show_image_bytes(img_data, 1, 1)

        iv.sixel_show_file.assert_called_once_with(mock.ANY, 1, 1)
        assert isinstance(iv.sixel_show_file.call_args[0][0], int)

    def test_sixel_with_png_str(self):
        iv = IV("sixel")

        iv.sixel_show_file = Mock()
        fp = self.png_sample.as_posix()
        iv._show_image_str(fp, 1, 1)

        iv.sixel_show_file.assert_called_once_with(fp, 1, 1)

    def test_iterm_with_png_bytes(self):
        iv = IV("iterm")

        with open(self.png_sample, "rb") as f:
            img_data = f.read()

        iv.iterm_show_file = Mock()
        iv._show_image_bytes(img_data, 1, 1)
        iv.iterm_show_file.assert_called_once_with(img_data)

    def test_iterm_with_png_str(self):
        iv = IV("iterm")

        iv.iterm_show_file = Mock()
        fp = self.png_sample.as_posix()
        iv._show_image_str(fp, 1, 1)

        iv.iterm_show_file.assert_called_once_with(mock.ANY)
        assert isinstance(iv.iterm_show_file.call_args[0][0], bytes)
