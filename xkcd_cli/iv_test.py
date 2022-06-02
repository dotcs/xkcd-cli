from typing import Any
from unittest.mock import Mock, patch
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


class TestIvInit:
    @patch("termios.tcgetattr")
    @patch("atexit.register")
    @patch("sys.stdin.fileno")
    def test_tty_setup(
        self,
        mock_sys_stdin_fileno: Mock,
        mock_atexit_register: Mock,
        mock_termios_tcgetattr: Mock,
    ):
        mock_sys_stdin_fileno.return_value = 1
        mock_termios_tcgetattr.return_value = [123]

        protocol: Any = "foobar"
        iv = IV(protocol)

        mock_atexit_register.assert_called_once()
        assert iv.libsixel is None
        assert iv.stdin_fd == 1
        assert iv.saved_term == [123]

    @patch("termios.tcgetattr")
    @patch("atexit.register")
    @patch("sys.stdin.fileno")
    def test_unknown_protocol(
        self,
        mock_sys_stdin_fileno: Mock,
        mock_atexit_register: Mock,
        mock_termios_tcgetattr: Mock,
    ):
        mock_sys_stdin_fileno.return_value = 1
        mock_termios_tcgetattr.return_value = []

        protocol: Any = "foobar"
        iv = IV(protocol)
        assert iv.protocol is None
