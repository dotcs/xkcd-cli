import io
from typing import Any, Dict, List
from unittest import mock
from unittest.mock import Mock, patch
import unittest
from pathlib import Path
from dataclasses import dataclass
import pytest

from .iv import IV


@pytest.mark.parametrize(
    "params,expected",
    [
        # trivial case, unknown original dimensions
        (dict(w=100, h=0, ow=-1, oh=-1, aspect=True, up=False), (-1, -1)),
        # same height, width -> no scaling
        (dict(w=100, h=10, ow=100, oh=10, aspect=True, up=False), (100, 10)),
        # 10x larger with disabled upscaling -> don't upscale
        (dict(w=1000, h=100, ow=100, oh=10, aspect=True, up=False), (100, 10)),
        # 2x smaller -> downscale
        (dict(w=50, h=0, ow=100, oh=10, aspect=True, up=False), (50, 5)),
        # 2x smaller with no w value -> downscale
        (dict(w=0, h=5, ow=100, oh=10, aspect=True, up=False), (50, 5)),
        # 2x smaller with wrong aspect ratio -> downscale
        (dict(w=50, h=6, ow=100, oh=10, aspect=True, up=False), (50, 5)),
        # 2x smaller with wrong aspect ratio -> downscale
        (dict(w=55, h=5, ow=100, oh=10, aspect=True, up=False), (50, 5)),
        # 10x larger with upscale allowed -> upscale
        (dict(w=1000, h=100, ow=100, oh=10, aspect=True, up=True), (1000, 100)),
        # larger with upscale allowed, don't keep aspect -> keep
        (dict(w=1000, h=50, ow=100, oh=10, aspect=False, up=True), (1000, 50)),
        # larger with upscale allowed, no target height, don't keep aspect -> keep original h
        (dict(w=1000, h=-1, ow=100, oh=10, aspect=False, up=True), (1000, 10)),
        # larger with upscale allowed, no target width, don't keep aspect -> keep original w
        (dict(w=-1, h=50, ow=100, oh=10, aspect=False, up=True), (100, 50)),
        # 5x larger with upscale allowed and wrong aspect ratio -> upscale and reset height
        (dict(w=500, h=55, ow=100, oh=10, aspect=True, up=True), (500, 50)),
        # 5x larger with upscale allowed and wrong aspect ratio -> upscale and reset width
        (dict(w=550, h=50, ow=100, oh=10, aspect=True, up=True), (500, 50)),
    ],
)
def test_scale_fit(params, expected):
    assert IV.scale_fit(**params) == expected


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

    def test_auto_protocol(self):
        mock_ap = Mock()
        IV.auto_protocol = mock_ap(return_value="test_protocol")
        IV("auto")

        mock_ap.assert_called_once()


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

        height, width = iv.terminal_cell_size()
        assert height == -1
        assert width == -1


class TestItermCellSize(IvInitMixin, unittest.TestCase):
    def test_happy_path(self):
        iv = IV("iterm")

        iv.terminal_request = Mock(return_value="\x1b]1337;ReportCellSize=1200;800\x07")

        height, width = iv.iterm_cell_size()
        assert height == 1200
        assert width == 800

    def test_with_scaling_factor(self):
        iv = IV("iterm")

        iv.terminal_request = Mock(
            return_value="\x1b]1337;ReportCellSize=1200;800;2\x07"
        )

        height, width = iv.iterm_cell_size()
        assert height == 1200 * 2
        assert width == 800 * 2

    def test_escape_code_not_working(self):
        iv = IV("iterm")

        iv.terminal_request = Mock(return_value="")

        height, width = iv.iterm_cell_size()
        assert height == -1
        assert width == -1


class TestShowImage(IvInitMixin, unittest.TestCase):
    png_sample = Path("tests") / "assets" / "1x1.png"

    def test_byte_data(self):
        iv = IV("kitty")

        iv._show_image_str = Mock()
        iv._show_image_bytes = Mock()

        with open(self.png_sample, "rb") as f:
            data = f.read()

        iv.show_image(data)

        iv._show_image_bytes.assert_called_once()
        iv._show_image_str.assert_not_called()

    def test_str_data(self):
        iv = IV("kitty")

        iv._show_image_str = Mock()
        iv._show_image_bytes = Mock()

        fp = self.png_sample.as_posix()
        iv.show_image(fp)

        iv._show_image_bytes.assert_not_called()
        iv._show_image_str.assert_called_once()

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


class StubLibsixelEncoder:
    _opts: Dict[str, str] = {}
    _filename: str = ""

    def setopt(self, name: str, value: str):
        self._opts[name] = value

    def encode(self, filename: str):
        self._filename = filename


class TestSixelShowFile(IvInitMixin, unittest.TestCase):
    png_sample = Path("tests") / "assets" / "1x1.png"

    def test_libsixel(self):
        fp = self.png_sample.as_posix()
        iv = IV("sixel")
        iv._setup_libsixel_or_fallback = Mock()
        iv.libsixel = True
        iv.encoder = Mock()
        stubEncoder = StubLibsixelEncoder()
        iv.encoder.configure_mock(
            **{
                "Encoder.return_value": stubEncoder,
                "SIXEL_OPTFLAG_WIDTH": "SIXEL_OPTFLAG_WIDTH",
                "SIXEL_OPTFLAG_HEIGHT": "SIXEL_OPTFLAG_HEIGHT",
            }
        )

        out = io.BytesIO()  # mock output to which response will be written

        iv.sixel_show_file(fp, w=100, h=10, out=out)

        assert stubEncoder._filename == fp
        assert stubEncoder._opts["SIXEL_OPTFLAG_WIDTH"] == "100"
        assert stubEncoder._opts["SIXEL_OPTFLAG_HEIGHT"] == "10"

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_fallback_imagemagick_convert(
        self,
        mock_subp_run: Mock,
        mock_shutil_which: Mock,
    ):
        mock_shutil_which.return_value = "/usr/bin/convert"
        fp = self.png_sample.as_posix()

        @dataclass
        class TC:
            """Parameterized test case"""

            w: int
            h: int
            expected: List[str]

        tests: List[TC] = [
            TC(-1, -1, ["convert", fp, "sixel:-"]),
            TC(100, 10, ["convert", fp, "-geometry", "100x10", "sixel:-"]),
            TC(100, -1, ["convert", fp, "-geometry", "100x", "sixel:-"]),
            TC(-1, 10, ["convert", fp, "-geometry", "x10", "sixel:-"]),
        ]

        @dataclass
        class SubprocessRunReturnMock:
            stdout = b"foobar"

        for t_param in tests:
            iv = IV("sixel")
            out = io.BytesIO()  # mock output to which response will be written
            mock_subp_run.reset_mock()

            mock_subp_run.return_value = SubprocessRunReturnMock()

            # mock setup fn to test behavior if libsixel is not found
            iv._setup_libsixel_or_fallback = Mock()
            iv.sixel_show_file(fp, w=t_param.w, h=t_param.h, out=out)
            iv._setup_libsixel_or_fallback.assert_called_once()
            iv.libsixel = False  # simulate missing libsixel

            mock_subp_run.assert_called_once_with(t_param.expected, stdout=mock.ANY)

            out.seek(0)
            assert out.read() == b"foobar"

    @patch("shutil.which")
    def test_fallback_failure(
        self,
        mock_shutil_which: Mock,
    ):
        mock_shutil_which.return_value = None

        fp = self.png_sample.as_posix()

        iv = IV("sixel")
        iv._setup_libsixel_or_fallback = Mock()
        iv.libsixel = False
        out = io.BytesIO()  # mock output to which response will be written

        iv.sixel_show_file(fp, out=out)

        out.seek(0)
        assert b"Could not find" in out.read()


class TestKittyShowFile(IvInitMixin, unittest.TestCase):
    png_sample = Path("tests") / "assets" / "1x1.png"
    jpg_sample = Path("tests") / "assets" / "1x1.jpg"

    def test_with_png(self):
        iv = IV("kitty")

        with open(self.png_sample, "rb") as f:
            data = f.read()

        out = io.BytesIO()  # mock output to which response will be written
        iv.kitty_show_file(data, out=out)

        out.seek(0)
        result = out.read()
        assert result.startswith(b"\033_Ga=T,f=100,q=2,m=0;")
        assert result.endswith(b"\033\\")

    def test_with_jpg_without_jpg_support(self):
        iv = IV("kitty")

        with open(self.jpg_sample, "rb") as f:
            data = f.read()

        out = io.BytesIO()  # mock output to which response will be written
        iv.kitty_show_file(data, out=out)

        out.seek(0)
        result = out.read()
        assert result.startswith(
            b"\033_Ga=T,f=24,q=2,s=1,v=1,m=0;"
        )  # expect fallback to f=24, RGB data
        assert result.endswith(b"\033\\")

    def test_with_jpg_with_jpg_support(self):
        iv = IV("kitty")

        with open(self.jpg_sample, "rb") as f:
            data = f.read()

        out = io.BytesIO()  # mock output to which response will be written
        iv.kitty_show_file(data, extended=True, out=out)

        out.seek(0)
        result = out.read()
        assert result.startswith(
            b"\033_Ga=T,f=100,q=2,m=0;"
        )  # expect sticking with f=100 mode, no fallback
        assert result.endswith(b"\033\\")


class TestItermShowFile(IvInitMixin, unittest.TestCase):
    png_sample = Path("tests") / "assets" / "1x1.png"
    jpg_sample = Path("tests") / "assets" / "1x1.jpg"

    def test_with_png(self):
        iv = IV("iterm")

        with open(self.jpg_sample, "rb") as f:
            data = f.read()

        out = io.BytesIO()  # mock output to which response will be written
        iv.iterm_show_file(data, out=out)

        out.seek(0)
        result = out.read()
        assert result.startswith(b"\033]1337;File=inline=1:")
        assert result.endswith(b"\007")

    def test_with_png_with_extras(self):
        iv = IV("iterm")

        with open(self.jpg_sample, "rb") as f:
            data = f.read()

        out = io.BytesIO()  # mock output to which response will be written
        iv.iterm_show_file(data, out=out, C=1, width=100)

        out.seek(0)
        result = out.read()
        assert result.startswith(
            b"\033]1337;File=inline=1;doNotMoveCursor=1;width=100:"
        )
        assert result.endswith(b"\007")


class TestImageDataAndMetadata:
    png_sample = Path("tests") / "assets" / "1x1.png"
    jpg_sample = Path("tests") / "assets" / "1x1.jpg"

    def test_png_image(self):
        with open(self.png_sample, "rb") as f:
            data = f.read()

        ret_data, img_format, img_height, img_width = IV.image_data_and_metadata(data)

        assert ret_data is not None
        assert img_format == "PNG"
        assert img_height == 1
        assert img_width == 1

    def test_jpg_image(self):
        with open(self.jpg_sample, "rb") as f:
            data = f.read()

        ret_data, img_format, img_height, img_width = IV.image_data_and_metadata(data)

        assert ret_data is not None
        assert img_format == "JPEG"
        assert img_height == 1
        assert img_width == 1


class TestItermDetection(IvInitMixin, unittest.TestCase):
    def test_iterm_positive(self):
        iv = IV("iterm")

        assert iv.iterm is None
        iv.iterm_cell_size = Mock(return_value=(100, 100))

        ret = iv.have_iterm()

        assert ret == True
        assert iv.iterm == True

    def test_iterm_negative(self):
        iv = IV("iterm")

        assert iv.iterm is None
        iv.iterm_cell_size = Mock(return_value=(-1, -1))

        ret = iv.have_iterm()

        assert ret == False
        assert iv.iterm == False


class TestKittyDetection(IvInitMixin, unittest.TestCase):
    def test_kitty_positive(self):
        iv = IV("kitty")

        assert iv.kitty is None
        iv.terminal_request = Mock(return_value="\x1b_Gi=31;OK\x1b\\")

        ret = iv.have_kitty()

        assert ret == True
        assert iv.kitty == True

    def test_kitty_negative(self):
        iv = IV("kitty")

        assert iv.kitty is None
        iv.terminal_request = Mock(return_value="")

        ret = iv.have_kitty()

        assert ret == False
        assert iv.kitty == False

    def test_extended_kitty_positive(self):
        iv = IV("iterm")

        assert iv.kitty is None
        assert iv.ex_kitty is None
        iv.terminal_request = Mock(return_value="\x1b_Gi=31;OK\x1b\\")

        ret = iv.have_extended_kitty()

        assert ret == True
        assert iv.kitty == True
        assert iv.ex_kitty == True

    def test_extended_kitty_negative(self):
        iv = IV("iterm")

        assert iv.kitty is None
        assert iv.ex_kitty is None
        iv.terminal_request = Mock(
            return_value="\x1b_Gi=31;EBADPNG:Not a PNG file\x1b\\"
        )

        ret = iv.have_extended_kitty()

        assert ret == False
        assert iv.kitty is None
        assert iv.ex_kitty == False


class TestSixelDetection(IvInitMixin, unittest.TestCase):
    def test_sixel_positive(self):
        iv = IV("sixel")

        assert iv.iterm is None
        iv.terminal_request = Mock(return_value="\x1b[?62;4;22c")

        ret = iv.have_sixel()

        assert ret == True
        assert iv.sixel == True

    def test_sixel_negative(self):
        iv = IV("sixel")

        assert iv.iterm is None
        iv.terminal_request = Mock(return_value="\x1b[?62;c")

        ret = iv.have_sixel()

        assert ret == False
        assert iv.sixel == False
