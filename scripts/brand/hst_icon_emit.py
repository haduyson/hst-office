# SPDX-License-Identifier: AGPL-3.0-only
"""SVG elements of snapped shapes: filled outlines (shipped) or editable strokes (drafts)."""
from html import escape

from hst_icon_outline import ellipse, flatten, polygon, stroke_ellipse, stroke_path, stroke_rect
from hst_svg_math import EPS, SnapError, fmt
from hst_svg_path import format_subpaths, rect_subpaths

INHERITED = ("fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-opacity",
             "fill-opacity", "opacity")
DRAFT_STYLE = {"fill": "none", "stroke": "currentColor", "stroke-linecap": "round", "stroke-linejoin": "round"}

def _opacity(style, name):
    value = float(style.get(name, "1")) * float(style.get("opacity", "1"))
    return "" if abs(value - 1) < EPS else f' fill-opacity="{fmt(value)}"'


def emit(shape, pen, style, state=None):
    """<path> elements that paint `shape`: its fill, then its stroke as a filled outline."""
    if style.get("stroke-linecap", "butt") != "round" and pen is not None:
        raise SnapError("only round caps are supported")
    if style.get("stroke-linejoin", "miter") != "round" and pen is not None:
        raise SnapError("only round joins are supported")
    marker = f' data-state="{escape(state)}"' if state else ""
    if shape[0] == "dot":
        colour = style.get("stroke", "none") if style.get("stroke", "none") != "none" else style.get("fill")
        return [f'<path d="{fill_shape(("rect",) + shape[1:])}" fill="{escape(colour)}"'
                f'{_opacity(style, "stroke-opacity")}{marker}/>']
    result = []
    if style.get("fill", "black") != "none":
        result.append(f'<path d="{fill_shape(shape)}" fill="{escape(style["fill"])}"'
                      f'{_opacity(style, "fill-opacity")}{marker}/>')
    if pen is not None:
        paint = f' fill="{escape(style["stroke"])}"{_opacity(style, "stroke-opacity")}{marker}'
        result += [f'<path d="{data}"{paint}/>' for data in outline_shape(shape, pen)]
    return result


def emit_stroked(shape, pen, style, state=None):
    """Editable stroked element of a snapped shape (drafts of hand-tuned masters)."""
    extra = "".join(f' {name}="{escape(style[name])}"' for name in INHERITED
                    if name != "stroke-width" and style.get(name) is not None and DRAFT_STYLE.get(name) != style[name]
                    and not (name == "fill" and style[name] == "black"))
    extra += f' data-state="{escape(state)}"' if state else ""
    if shape[0] == "dot":
        colour = style.get("stroke") if style.get("stroke", "none") != "none" else style.get("fill")
        return f'<path d="{fill_shape(("rect",) + shape[1:])}" fill="{escape(colour)}" stroke="none"{extra}/>'
    pen_attr = f' stroke-width="{pen}"' if pen is not None else ""
    if shape[0] == "rect":
        _, x0, y0, x1, y1, radius = shape
        return (f'<rect x="{fmt(x0)}" y="{fmt(y0)}" width="{fmt(x1 - x0)}" height="{fmt(y1 - y0)}"'
                + (f' rx="{fmt(radius)}"' if radius > EPS else "") + pen_attr + extra + "/>")
    if shape[0] == "ellipse":
        _, cx, cy, rx, ry = shape
        if abs(rx - ry) < EPS:
            return f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(rx)}"{pen_attr}{extra}/>'
        return f'<ellipse cx="{fmt(cx)}" cy="{fmt(cy)}" rx="{fmt(rx)}" ry="{fmt(ry)}"{pen_attr}{extra}/>'
    return f'<path d="{format_subpaths(shape[1])}"{pen_attr}{extra}/>'


def fill_shape(shape):
    """Path data that fills a snapped shape as it is."""
    kind = shape[0]
    if kind == "rect":
        _, x0, y0, x1, y1, radius = shape
        return polygon(flatten(rect_subpaths(x0, y0, x1 - x0, y1 - y0, radius, radius)[0])[0], True)
    if kind == "ellipse":
        return ellipse(*shape[1:], True)
    return format_subpaths(shape[1])


def outline_shape(shape, pen):
    """Path data of the separately painted parts of a stroked shape."""
    kind = shape[0]
    if kind == "rect":
        return [stroke_rect(*shape[1:], pen)]
    if kind == "ellipse":
        return [stroke_ellipse(*shape[1:], pen)]
    return stroke_path(shape[1], pen)
