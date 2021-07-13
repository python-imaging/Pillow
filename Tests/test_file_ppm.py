from io import BytesIO

import pytest

from PIL import Image, PpmImagePlugin

from .helper import assert_image_equal_tofile, assert_image_similar, hopper

# sample ppm stream
TEST_FILE = "Tests/images/hopper.ppm"


def test_sanity():
    with Image.open(TEST_FILE) as im:
        im.load()
        assert im.mode == "RGB"
        assert im.size == (128, 128)
        assert im.format, "PPM"
        assert im.get_format_mimetype() == "image/x-portable-pixmap"


def test_16bit_pgm():
    with Image.open("Tests/images/16_bit_binary.pgm") as im:
        im.load()
        assert im.mode == "I"
        assert im.size == (20, 100)
        assert im.get_format_mimetype() == "image/x-portable-graymap"

        assert_image_equal_tofile(im, "Tests/images/16_bit_binary_pgm.png")


def test_16bit_pgm_write(tmp_path):
    with Image.open("Tests/images/16_bit_binary.pgm") as im:
        im.load()

        f = str(tmp_path / "temp.pgm")
        im.save(f, "PPM")

        assert_image_equal_tofile(im, f)


def test_pnm(tmp_path):
    with Image.open("Tests/images/hopper.pnm") as im:
        assert_image_similar(im, hopper(), 0.0001)

        f = str(tmp_path / "temp.pnm")
        im.save(f)

        assert_image_equal_tofile(im, f)


def test_plain_pbm(tmp_path):
    with Image.open("Tests/images/hopper_1bit_plain.pbm") as im:
        assert_image_equal_tofile(im, "Tests/images/hopper_1bit.pbm")


def test_8bit_plain_pgm(tmp_path):
    with Image.open("Tests/images/hopper_8bit_plain.pgm") as im:
        assert_image_equal_tofile(im, "Tests/images/hopper_8bit.pgm")


def test_8bit_plain_ppm(tmp_path):
    with Image.open("Tests/images/hopper_8bit_plain.ppm") as im:
        assert_image_equal_tofile(im, "Tests/images/hopper_8bit.ppm")


def test_16bit_plain_pgm(tmp_path):
    with Image.open("Tests/images/hopper_16bit_plain.pgm") as im:
        assert im.mode == "I"
        assert im.size == (128, 128)
        assert im.get_format_mimetype() == "image/x-portable-graymap"

        assert_image_equal_tofile(im, "Tests/images/hopper_16bit.pgm")


def test_32bit_plain_pgm(tmp_path):
    with Image.open("Tests/images/hopper_32bit_plain.pgm") as im:
        assert im.mode == "I"
        assert im.size == (128, 128)
        assert im.get_format_mimetype() == "image/x-portable-graymap"

        assert_image_equal_tofile(im, "Tests/images/hopper_32bit.pgm")


def test_plain_pbm_data_with_comments(tmp_path):
    path1 = str(tmp_path / "temp1.ppm")
    path2 = str(tmp_path / "temp2.ppm")
    comment = b"# veeery long comment" * 10 ** 6
    with open(path1, "wb") as f1, open(path2, "wb") as f2:
        f1.write(b"P1\n2 2\n\n1010")
        f2.write(b"P1\n2 2\n" + comment + b"\n1010" + comment)

    with Image.open(path1) as im:
        assert_image_equal_tofile(im, path2)


def test_plain_pbm_truncated_data(tmp_path):
    path = str(tmp_path / "temp.ppm")
    with open(path, "wb") as f:
        f.write(b"P1\n128 128\n")

    with Image.open(path) as im:
        with pytest.raises(ValueError):
            im.load()


def test_plain_pbm_invalid_data(tmp_path):
    path = str(tmp_path / "temp.ppm")
    with open(path, "wb") as f:
        f.write(b"P1\n128 128\n1009")

    with Image.open(path) as im:
        with pytest.raises(ValueError):
            im.load()


def test_plain_ppm_data_with_comments(tmp_path):
    path1 = str(tmp_path / "temp1.ppm")
    path2 = str(tmp_path / "temp2.ppm")
    comment = b"# veeery long comment" * 10 ** 6
    with open(path1, "wb") as f1, open(path2, "wb") as f2:
        f1.write(b"P3\n2 2\n255\n0 0 0 001 1 1 2 2 2 255 255 255")
        f2.write(
            b"P3\n2 2\n255\n" + comment + b"\n0 0 0 001 1 1 2 2 2 255 255 255" + comment
        )

    with Image.open(path1) as im:
        assert_image_equal_tofile(im, path2)


def test_plain_ppm_truncated_data(tmp_path):
    path = str(tmp_path / "temp.ppm")
    with open(path, "wb") as f:
        f.write(b"P3\n128 128\n255\n")

    with Image.open(path) as im:
        with pytest.raises(ValueError):
            im.load()


def test_plain_ppm_invalid_data(tmp_path):
    path = str(tmp_path / "temp.ppm")
    with open(path, "wb") as f:
        f.write(b"P3\n128 128\n255\n100A")

    with Image.open(path) as im:
        with pytest.raises(ValueError):
            im.load()


def test_plain_ppm_half_token_too_long(tmp_path):
    path = str(tmp_path / "temp.ppm")
    with open(path, "wb") as f:
        f.write(b"P3\n128 128\n255\n012345678910")

    with Image.open(path) as im:
        with pytest.raises(ValueError):
            im.load()


def test_plain_ppm_token_too_long(tmp_path):
    path = str(tmp_path / "temp.ppm")
    with open(path, "wb") as f:
        f.write(b"P3\n128 128\n255\n012345678910 0")

    with Image.open(path) as im:
        with pytest.raises(ValueError):
            im.load()


def test_plain_ppm_value_too_large(tmp_path):
    path = str(tmp_path / "temp.ppm")
    with open(path, "wb") as f:
        f.write(b"P3\n128 128\n255\n256")

    with Image.open(path) as im:
        with pytest.raises(ValueError):
            im.load()


def test_not_ppm(tmp_path):
    with pytest.raises(SyntaxError):
        PpmImagePlugin.PpmImageFile(fp=BytesIO(b"PyInvalid"))


def test_header_with_comments(tmp_path):
    path = str(tmp_path / "temp.ppm")
    with open(path, "wb") as f:
        f.write(b"P6 #comment\n#comment\r 12#comment\r8\n128 #comment\n255\n")

    with Image.open(path) as im:
        assert im.size == (128, 128)


def test_nondecimal_header(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"P6\n128\x00")

    with pytest.raises(ValueError):
        with Image.open(path):
            pass


def test_header_token_too_long(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"P6\n 012345678910")

    with pytest.raises(ValueError):
        with Image.open(path):
            pass


def test_too_many_colors(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"P6\n1 1\n1000\n")

    with pytest.raises(ValueError):
        with Image.open(path):
            pass


def test_truncated_header(tmp_path):
    path = str(tmp_path / "temp.pgm")
    with open(path, "w") as f:
        f.write("P6")

    with pytest.raises(ValueError):
        with Image.open(path):
            pass


def test_neg_ppm():
    # Storage.c accepted negative values for xsize, ysize.  the
    # internal open_ppm function didn't check for sanity but it
    # has been removed. The default opener doesn't accept negative
    # sizes.

    with pytest.raises(OSError):
        with Image.open("Tests/images/negative_size.ppm"):
            pass


def test_mimetypes(tmp_path):
    path = str(tmp_path / "temp.pgm")

    with open(path, "w") as f:
        f.write("P4\n128 128\n255")
    with Image.open(path) as im:
        assert im.get_format_mimetype() == "image/x-portable-bitmap"

    with open(path, "w") as f:
        f.write("PyCMYK\n128 128\n255")
    with Image.open(path) as im:
        assert im.get_format_mimetype() == "image/x-portable-anymap"
