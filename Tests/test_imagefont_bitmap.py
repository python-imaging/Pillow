from helper import unittest, PillowTestCase
import StringIO

from PIL import Image, ImageFont, ImageDraw

class TestImageFontBitmap(PillowTestCase):
    def test_similar(self):
        text = 'EmbeddedBitmap'
        font_outline = ImageFont.truetype(font='Tests/fonts/DejaVuSans.ttf', size=24)
        font_bitmap = ImageFont.truetype(font='Tests/fonts/DejaVuSans-bitmap.ttf', size=24)
        size_outline, size_bitmap = font_outline.getsize(text), font_bitmap.getsize(text)
        size_final = max(size_outline[0], size_bitmap[0]), max(size_outline[1], size_bitmap[1])
        im_bitmap = Image.new('RGB', size_final, (255, 255, 255))
        im_outline = im_bitmap.copy()
        draw_bitmap, draw_outline = ImageDraw.Draw(im_bitmap), ImageDraw.Draw(im_outline)
        # Don't know why, but bitmap version is always vertical 1 pixel longer than outline one on my PC.
        # Revert back to both 0, 0
        draw_bitmap.text((0, 0), text, fill=(0, 0, 0), font=font_bitmap)
        draw_outline.text((0, 0), text, fill=(0, 0, 0), font=font_outline)
        self.assert_image_similar(im_bitmap, im_outline, 0.01)

