#
# The Python Imaging Library
# $Id$
#
# drawing interface operations
#
# History:
# 1996-04-13 fl   Created (experimental)
# 1996-08-07 fl   Filled polygons, ellipses.
# 1996-08-13 fl   Added text support
# 1998-06-28 fl   Handle I and F images
# 1998-12-29 fl   Added arc; use arc primitive to draw ellipses
# 1999-01-10 fl   Added shape stuff (experimental)
# 1999-02-06 fl   Added bitmap support
# 1999-02-11 fl   Changed all primitives to take options
# 1999-02-20 fl   Fixed backwards compatibility
# 2000-10-12 fl   Copy on write, when necessary
# 2001-02-18 fl   Use default ink for bitmap/text also in fill mode
# 2002-10-24 fl   Added support for CSS-style color strings
# 2002-12-10 fl   Added experimental support for RGBA-on-RGB drawing
# 2002-12-11 fl   Refactored low-level drawing API (work in progress)
# 2004-08-26 fl   Made Draw() a factory function, added getdraw() support
# 2004-09-04 fl   Added width support to line primitive
# 2004-09-10 fl   Added font mode handling
# 2006-06-19 fl   Added font bearing support (getmask2)
#
# Copyright (c) 1997-2006 by Secret Labs AB
# Copyright (c) 1996-2006 by Fredrik Lundh
#
# See the README file for information on usage and redistribution.
#

import numbers
import warnings

from PIL import Image, ImageColor
from PIL._util import isStringType

"""
A simple 2D drawing interface for PIL images.
<p>
Application code should use the <b>Draw</b> factory, instead of
directly.
"""


class ImageDraw(object):

    def __init__(self, im, mode=None):
        """
        Create a drawing instance.

        @param im The image to draw in.
        @param mode Optional mode to use for color values.  For RGB
           images, this argument can be RGB or RGBA (to blend the
           drawing into the image).  For all other modes, this argument
           must be the same as the image mode.  If omitted, the mode
           defaults to the mode of the image.
        """
        im.load()
        if im.readonly:
            im._copy()  # make it writeable
        blend = 0
        if mode is None:
            mode = im.mode
        if mode != im.mode:
            if mode == "RGBA" and im.mode == "RGB":
                blend = 1
            else:
                raise ValueError("mode mismatch")
        if mode == "P":
            self.palette = im.palette
        else:
            self.palette = None
        self.im = im.im
        self.draw = Image.core.draw(self.im, blend)
        self.mode = mode
        if mode in ("I", "F"):
            self.ink = self.draw.draw_ink(1, mode)
        else:
            self.ink = self.draw.draw_ink(-1, mode)
        if mode in ("1", "P", "I", "F"):
            # FIXME: fix Fill2 to properly support matte for I+F images
            self.fontmode = "1"
        else:
            self.fontmode = "L"  # aliasing is okay for other modes
        self.fill = 0
        self.font = None

    def setink(self, ink):
        raise NotImplementedError("setink() has been removed. " +
                                  "Please use keyword arguments instead.")

    def setfill(self, onoff):
        raise NotImplementedError("setfill() has been removed. " +
                                  "Please use keyword arguments instead.")

    def setfont(self, font):
        warnings.warn("setfont() is deprecated. " +
                      "Please set the attribute directly instead.")
        # compatibility
        self.font = font

    def getfont(self):
        """Get the current default font."""
        if not self.font:
            # FIXME: should add a font repository
            from PIL import ImageFont
            self.font = ImageFont.load_default()
        return self.font

    def _getink(self, ink, fill=None):
        if ink is None and fill is None:
            if self.fill:
                fill = self.ink
            else:
                ink = self.ink
        else:
            if ink is not None:
                if isStringType(ink):
                    ink = ImageColor.getcolor(ink, self.mode)
                if self.palette and not isinstance(ink, numbers.Number):
                    ink = self.palette.getcolor(ink)
                ink = self.draw.draw_ink(ink, self.mode)
            if fill is not None:
                if isStringType(fill):
                    fill = ImageColor.getcolor(fill, self.mode)
                if self.palette and not isinstance(fill, numbers.Number):
                    fill = self.palette.getcolor(fill)
                fill = self.draw.draw_ink(fill, self.mode)
        return ink, fill

    def arc(self, xy, start, end, fill=None):
        """Draw an arc."""
        ink, fill = self._getink(fill)
        if ink is not None:
            self.draw.draw_arc(xy, start, end, ink)

    def bitmap(self, xy, bitmap, fill=None):
        """Draw a bitmap."""
        bitmap.load()
        ink, fill = self._getink(fill)
        if ink is None:
            ink = fill
        if ink is not None:
            self.draw.draw_bitmap(xy, bitmap.im, ink)

    def chord(self, xy, start, end, fill=None, outline=None):
        """Draw a chord."""
        ink, fill = self._getink(outline, fill)
        if fill is not None:
            self.draw.draw_chord(xy, start, end, fill, 1)
        if ink is not None:
            self.draw.draw_chord(xy, start, end, ink, 0)

    def ellipse(self, xy, fill=None, outline=None):
        """Draw an ellipse."""
        ink, fill = self._getink(outline, fill)
        if fill is not None:
            self.draw.draw_ellipse(xy, fill, 1)
        if ink is not None:
            self.draw.draw_ellipse(xy, ink, 0)

    def line(self, xy, fill=None, width=0):
        """Draw a line, or a connected sequence of line segments."""
        ink, fill = self._getink(fill)
        if ink is not None:
            self.draw.draw_lines(xy, ink, width)

    def shape(self, shape, fill=None, outline=None):
        """(Experimental) Draw a shape."""
        shape.close()
        ink, fill = self._getink(outline, fill)
        if fill is not None:
            self.draw.draw_outline(shape, fill, 1)
        if ink is not None:
            self.draw.draw_outline(shape, ink, 0)

    def pieslice(self, xy, start, end, fill=None, outline=None):
        """Draw a pieslice."""
        ink, fill = self._getink(outline, fill)
        if fill is not None:
            self.draw.draw_pieslice(xy, start, end, fill, 1)
        if ink is not None:
            self.draw.draw_pieslice(xy, start, end, ink, 0)

    def point(self, xy, fill=None):
        """Draw one or more individual pixels."""
        ink, fill = self._getink(fill)
        if ink is not None:
            self.draw.draw_points(xy, ink)

    def polygon(self, xy, fill=None, outline=None):
        """Draw a polygon."""
        ink, fill = self._getink(outline, fill)
        if fill is not None:
            self.draw.draw_polygon(xy, fill, 1)
        if ink is not None:
            self.draw.draw_polygon(xy, ink, 0)

    def rectangle(self, xy, fill=None, outline=None):
        """Draw a rectangle."""
        ink, fill = self._getink(outline, fill)
        if fill is not None:
            self.draw.draw_rectangle(xy, fill, 1)
        if ink is not None:
            self.draw.draw_rectangle(xy, ink, 0)

    def _multiline_check(self, text):
        """Draw text."""
        split_character = "\n" if isinstance(text, type("")) else b"\n"

        return split_character in text

    def _multiline_split(self, text):
        split_character = "\n" if isinstance(text, type("")) else b"\n"

        return text.split(split_character)

    def text(self, xy, text, fill=None, font=None, anchor=None,
             *args, **kwargs):
        if self._multiline_check(text):
            return self.multiline_text(xy, text, fill, font, anchor,
                                       *args, **kwargs)

        ink, fill = self._getink(fill)
        if font is None:
            font = self.getfont()
        if ink is None:
            ink = fill
        if ink is not None:
            try:
                mask, offset = font.getmask2(text, self.fontmode)
                xy = xy[0] + offset[0], xy[1] + offset[1]
            except AttributeError:
                try:
                    mask = font.getmask(text, self.fontmode)
                except TypeError:
                    mask = font.getmask(text)
            self.draw.draw_bitmap(xy, mask, ink)

    def multiline_text(self, xy, text, fill=None, font=None, anchor=None,
                       spacing=4, align="left"):
        widths = []
        max_width = 0
        lines = self._multiline_split(text)
        line_spacing = self.textsize('A', font=font)[1] + spacing
        for line in lines:
            line_width, line_height = self.textsize(line, font)
            widths.append(line_width)
            max_width = max(max_width, line_width)
        left, top = xy
        for idx, line in enumerate(lines):
            if align == "left":
                pass  # left = x
            elif align == "center":
                left += (max_width - widths[idx]) / 2.0
            elif align == "right":
                left += (max_width - widths[idx])
            else:
                assert False, 'align must be "left", "center" or "right"'
            self.text((left, top), line, fill, font, anchor)
            top += line_spacing
            left = xy[0]

    ##
    # Get the size of a given string, in pixels.
    def textsize(self, text, font=None, *args, **kwargs):
        """Get the size of a given string, in pixels."""
        if self._multiline_check(text):
            return self.multiline_textsize(text, font, *args, **kwargs)

        if font is None:
            font = self.getfont()
        return font.getsize(text)

    def multiline_textsize(self, text, font=None, spacing=4):
        max_width = 0
        lines = self._multiline_split(text)
        line_spacing = self.textsize('A', font=font)[1] + spacing
        for line in lines:
            line_width, line_height = self.textsize(line, font)
            max_width = max(max_width, line_width)
        return max_width, len(lines)*line_spacing

    # Note that font metrics assume an origin on a baseline. So xMin is negative
    # pixels to the left of the origin, xMax is positive pixels to the right of the
    # origin, yMin is negative pixels below the baseline, yMax is positive pixels
    # above the baseline.
    # if text contains "\n" it is treated as multiple lines of text.
    #    yMin becomes really negative.
    #    lineHeight and lineHeightPercent become relevant.
    #    lineHeightPercent is only used if LineHeight is None, and defaults to 100%.
    #    Use of a lineHeight < sum( font.getmetrics ) may result in text overlap.
    #    The best lineHeight would be that returned from the font.font.height
    #    attribute, but in versions of PIL in which that isn't accessible,
    #    sum( font.getmetrics()) is used instead.
    def textInfo(self, text, font=None, lineHeight=None, lineHeightPercent=None):
        if font is None:
            font = self.getfont()
        lines = text.split('\n')
        txMax = 0
        txMin = 0
        txWid = 0
        tyMax = None
        tyMin = None
        if len(lines) > 1:
            if lineHeight is None:
                if lineHeightPercent is None:
                    lineHeightPercent = 100
                try:
                    lineHeight = font.font.height
                except AttributeError:
                    lineHeight = sum(font.getmetrics())
                lineHeight = int(lineHeight * lineHeightPercent / 100)

        lineBBs = []
        for line in lines:
            lxMin, lyMin, lxMax, lyMax = font.getBB(line)
            lineBBs.append((lxMin, lyMin, lxMax, lyMax, line))
            lxWid = lxMax - lxMin
            if txWid < lxWid:
                txWid = lxWid
            if txMax < lxMax:
                txMax = lxMax
            if txMin > lxMin:
                txMin = lxMin
            if tyMax is None:
                tyMax = lyMax  # from first line only
            if tyMin is None:
                tyMin = 0  # skips first line (unless it is also last)
            else:
                tyMin -= lineHeight
        tyMin += lyMin  # from last line
        return (txMin, tyMin, txMax, tyMax, txWid, lineHeight, lineBBs)

    # Text is drawn as close as possible to the specified alignment edges of the
    # image, without truncation on those edges, then adjusted by the origin value.
    # alignX or alignY of 'exact' means to use the specified origin point exactly
    # in that direction. Otherwise origin is used as an offset from the calculated
    # alignment position. alignX can also be 'left', 'center', or 'right'; alignY
    # can also be 'top', 'middle', or 'bottom'. justifyX can be 'left', 'center',
    # or 'right'. Other parameters like textInfo.
    def textAtPos(self, text, font=None, lineHeight=None, lineHeightPercent=None,
                  origin=(0, 0), alignX='exact', alignY='exact', justifyX='left',
                  fill=None):
        if font is None:
            font = self.getfont()
        ink, fill = self._getink(fill)
        if ink is None:
            if ink is None:
                return
        if justifyX not in ('left', 'center', 'right'):
            raise ValueError('Unknown justifyX value "%s".' % justifyX)
        txMin, tyMin, txMax, tyMax, txWid, lineHeight, lineBBs = self.textInfo(
            text, font, lineHeight, lineHeightPercent)
        if alignX == 'exact':
            ox = 0
        elif alignX == 'left':
            ox = -txMin
        elif alignX == 'right':
            ox = self.im.size[0] - txMax
        elif alignX == 'center':
            ox = self.im.size[0] // 2 - txMax // 2
        else:
            raise ValueError('Unknown alignX value "%s".' % alignX)
        if alignY == 'exact':
            oy = 0
        elif alignY == 'top':
            oy = tyMax
        elif alignY == 'bottom':
            oy = self.im.size[1] + tyMin
        elif alignY == 'middle':
            oy = self.im.size[1] // 2 + (tyMax + tyMin) // 2
        else:
            raise ValueError('Unknown alignY value "%s".' % alignY)
        ox += origin[0]
        oy += origin[1]
        ascent, descent = font.getmetrics()
        while lineBBs:
            lxMin, lyMin, lxMax, lyMax, line = lineBBs.pop(0)
            if justifyX == 'left':
                lox = ox
            elif justifyX == 'right':
                lox = ox + txMax - lxMax
            else:
                lox = ox + txMax // 2 - lxMax // 2

            # finally, draw some text
            lox = lox + lxMin
            loy = oy - lyMax
            im = Image.core.fill("L", (lxMax - lxMin, lyMax - lyMin), 0)
            font.font.render(line, im.id, self.fontmode == "1")
            self.draw.draw_bitmap((lox, loy), im, ink)

            if not lineBBs:
                break
            oy += lineHeight


##
# A simple 2D drawing interface for PIL images.
#
# @param im The image to draw in.
# @param mode Optional mode to use for color values.  For RGB
#    images, this argument can be RGB or RGBA (to blend the
#    drawing into the image).  For all other modes, this argument
#    must be the same as the image mode.  If omitted, the mode
#    defaults to the mode of the image.
def Draw(im, mode=None):
    """
    A simple 2D drawing interface for PIL images.

    @param im The image to draw in.
    @param mode Optional mode to use for color values.  For RGB
       images, this argument can be RGB or RGBA (to blend the
       drawing into the image).  For all other modes, this argument
       must be the same as the image mode.  If omitted, the mode
       defaults to the mode of the image.
    """
    try:
        return im.getdraw(mode)
    except AttributeError:
        return ImageDraw(im, mode)

# experimental access to the outline API
try:
    Outline = Image.core.outline
except AttributeError:
    Outline = None


def getdraw(im=None, hints=None):
    """
    (Experimental) A more advanced 2D drawing interface for PIL images,
    based on the WCK interface.

    @param im The image to draw in.
    @param hints An optional list of hints.
    @return A (drawing context, drawing resource factory) tuple.
    """
    # FIXME: this needs more work!
    # FIXME: come up with a better 'hints' scheme.
    handler = None
    if not hints or "nicest" in hints:
        try:
            from PIL import _imagingagg as handler
        except ImportError:
            pass
    if handler is None:
        from PIL import ImageDraw2 as handler
    if im:
        im = handler.Draw(im)
    return im, handler


def floodfill(image, xy, value, border=None):
    """
    (experimental) Fills a bounded region with a given color.

    @param image Target image.
    @param xy Seed position (a 2-item coordinate tuple).
    @param value Fill color.
    @param border Optional border value.  If given, the region consists of
        pixels with a color different from the border color.  If not given,
        the region consists of pixels having the same color as the seed
        pixel.
    """
    # based on an implementation by Eric S. Raymond
    pixel = image.load()
    x, y = xy
    try:
        background = pixel[x, y]
        if background == value:
            return  # seed point already has fill color
        pixel[x, y] = value
    except IndexError:
        return  # seed point outside image
    edge = [(x, y)]
    if border is None:
        while edge:
            newedge = []
            for (x, y) in edge:
                for (s, t) in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
                    try:
                        p = pixel[s, t]
                    except IndexError:
                        pass
                    else:
                        if p == background:
                            pixel[s, t] = value
                            newedge.append((s, t))
            edge = newedge
    else:
        while edge:
            newedge = []
            for (x, y) in edge:
                for (s, t) in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
                    try:
                        p = pixel[s, t]
                    except IndexError:
                        pass
                    else:
                        if p != value and p != border:
                            pixel[s, t] = value
                            newedge.append((s, t))
            edge = newedge

# End of file
