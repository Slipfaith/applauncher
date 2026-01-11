"""Helpers for configuring application tile images in the GUI."""

from .editor import IconFrameEditor
from .frame import default_icon_frame, render_framed_pixmap, resolve_icon_frame
from .utils import clamp

__all__ = [
    "IconFrameEditor",
    "clamp",
    "default_icon_frame",
    "render_framed_pixmap",
    "resolve_icon_frame",
]
