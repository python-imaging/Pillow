#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "libImaging/Imaging.h"
#include "avif/avif.h"

#if AVIF_VERSION < 80300
#define AVIF_CHROMA_UPSAMPLING_AUTOMATIC AVIF_CHROMA_UPSAMPLING_BILINEAR
#define AVIF_CHROMA_UPSAMPLING_BEST_QUALITY AVIF_CHROMA_UPSAMPLING_BILINEAR
#define AVIF_CHROMA_UPSAMPLING_FASTEST AVIF_CHROMA_UPSAMPLING_NEAREST
#endif

typedef struct {
    avifPixelFormat subsampling;
    int qmin;
    int qmax;
    int speed;
    avifCodecChoice codec;
    avifRange range;
} avifEncOptions;

// Encoder type
typedef struct {
    PyObject_HEAD
    avifEncoder *encoder;
    avifImage *image;
    PyObject *icc_bytes;
    PyObject *exif_bytes;
    PyObject *xmp_bytes;
    int frame_index;
} AvifEncoderObject;

static PyTypeObject AvifEncoder_Type;

// Decoder type
typedef struct {
    PyObject_HEAD
    avifDecoder *decoder;
    PyObject *data;
    char *mode;
} AvifDecoderObject;

static PyTypeObject AvifDecoder_Type;

static int max_threads = 0;

static void
init_max_threads(void) {
    PyObject *os = NULL;
    PyObject *n = NULL;
    long num_cpus;

    os = PyImport_ImportModule("os");
    if (os == NULL) {
        goto error;
    }

    if (PyObject_HasAttrString(os, "sched_getaffinity")) {
        n = PyObject_CallMethod(os, "sched_getaffinity", "i", 0);
        if (n == NULL) {
            goto error;
        }
        num_cpus = PySet_Size(n);
    } else {
        n = PyObject_CallMethod(os, "cpu_count", NULL);
        if (n == NULL) {
            goto error;
        }
        num_cpus = PyLong_AsLong(n);
    }

    if (num_cpus < 1) {
        goto error;
    }

    max_threads = (int)num_cpus;

done:
    Py_XDECREF(os);
    Py_XDECREF(n);
    return;

error:
    if (PyErr_Occurred()) {
        PyErr_Clear();
    }
    PyErr_WarnEx(
        PyExc_RuntimeWarning, "could not get cpu count: using max_threads=1", 1);
    goto done;
}

static int
normalize_quantize_value(int qvalue) {
    if (qvalue < AVIF_QUANTIZER_BEST_QUALITY) {
        return AVIF_QUANTIZER_BEST_QUALITY;
    } else if (qvalue > AVIF_QUANTIZER_WORST_QUALITY) {
        return AVIF_QUANTIZER_WORST_QUALITY;
    } else {
        return qvalue;
    }
}

static PyObject *
exc_type_for_avif_result(avifResult result) {
    switch (result) {
        case AVIF_RESULT_INVALID_FTYP:
        case AVIF_RESULT_INVALID_EXIF_PAYLOAD:
            return PyExc_ValueError;
        case AVIF_RESULT_BMFF_PARSE_FAILED:
        case AVIF_RESULT_TRUNCATED_DATA:
        case AVIF_RESULT_NO_CONTENT:
            return PyExc_SyntaxError;
        default:
            return PyExc_RuntimeError;
    }
}

static int
_codec_available(const char *name, uint32_t flags) {
    avifCodecChoice codec = avifCodecChoiceFromName(name);
    if (codec == AVIF_CODEC_CHOICE_AUTO) {
        return 0;
    }
    const char *codec_name = avifCodecName(codec, flags);
    return (codec_name == NULL) ? 0 : 1;
}

PyObject *
_decoder_codec_available(PyObject *self, PyObject *args) {
    char *codec_name;
    if (!PyArg_ParseTuple(args, "s", &codec_name)) {
        return NULL;
    }
    int is_available = _codec_available(codec_name, AVIF_CODEC_FLAG_CAN_DECODE);
    return PyBool_FromLong(is_available);
}

PyObject *
_encoder_codec_available(PyObject *self, PyObject *args) {
    char *codec_name;
    if (!PyArg_ParseTuple(args, "s", &codec_name)) {
        return NULL;
    }
    int is_available = _codec_available(codec_name, AVIF_CODEC_FLAG_CAN_ENCODE);
    return PyBool_FromLong(is_available);
}

// Encoder functions
PyObject *
AvifEncoderNew(PyObject *self_, PyObject *args) {
    int width, height;
    avifEncOptions enc_options;
    AvifEncoderObject *self = NULL;
    avifEncoder *encoder = NULL;

    char *subsampling = "4:2:0";
    int qmin = AVIF_QUANTIZER_BEST_QUALITY;    // =0
    int qmax = 10;                             // "High Quality", but not lossless
    int speed = 8;
    PyObject *icc_bytes;
    PyObject *exif_bytes;
    PyObject *xmp_bytes;

    char *codec = "auto";
    char *range = "full";

    if (!PyArg_ParseTuple(
            args,
            "iisiiissSSS",
            &width,
            &height,
            &subsampling,
            &qmin,
            &qmax,
            &speed,
            &codec,
            &range,
            &icc_bytes,
            &exif_bytes,
            &xmp_bytes)) {
        return NULL;
    }

    if (strcmp(subsampling, "4:0:0") == 0) {
        enc_options.subsampling = AVIF_PIXEL_FORMAT_YUV400;
    } else if (strcmp(subsampling, "4:2:0") == 0) {
        enc_options.subsampling = AVIF_PIXEL_FORMAT_YUV420;
    } else if (strcmp(subsampling, "4:2:2") == 0) {
        enc_options.subsampling = AVIF_PIXEL_FORMAT_YUV422;
    } else if (strcmp(subsampling, "4:4:4") == 0) {
        enc_options.subsampling = AVIF_PIXEL_FORMAT_YUV444;
    } else {
        PyErr_Format(PyExc_ValueError, "Invalid subsampling: %s", subsampling);
        return NULL;
    }

    enc_options.qmin = normalize_quantize_value(qmin);
    enc_options.qmax = normalize_quantize_value(qmax);

    if (speed < AVIF_SPEED_SLOWEST) {
        speed = AVIF_SPEED_SLOWEST;
    } else if (speed > AVIF_SPEED_FASTEST) {
        speed = AVIF_SPEED_FASTEST;
    }
    enc_options.speed = speed;

    if (strcmp(codec, "auto") == 0) {
        enc_options.codec = AVIF_CODEC_CHOICE_AUTO;
    } else {
        enc_options.codec = avifCodecChoiceFromName(codec);
        if (enc_options.codec == AVIF_CODEC_CHOICE_AUTO) {
            PyErr_Format(PyExc_ValueError, "Invalid codec: %s", codec);
            return NULL;
        } else {
            const char *codec_name =
                avifCodecName(enc_options.codec, AVIF_CODEC_FLAG_CAN_ENCODE);
            if (codec_name == NULL) {
                PyErr_Format(PyExc_ValueError, "AV1 Codec cannot encode: %s", codec);
                return NULL;
            }
        }
    }

    if (strcmp(range, "full") == 0) {
        enc_options.range = AVIF_RANGE_FULL;
    } else if (strcmp(range, "limited") == 0) {
        enc_options.range = AVIF_RANGE_LIMITED;
    } else {
        PyErr_SetString(PyExc_ValueError, "Invalid range");
        return NULL;
    }

    // Validate canvas dimensions
    if (width <= 0 || height <= 0) {
        PyErr_SetString(PyExc_ValueError, "invalid canvas dimensions");
        return NULL;
    }

    // Create a new animation encoder and picture frame
    self = PyObject_New(AvifEncoderObject, &AvifEncoder_Type);
    if (self) {
        self->icc_bytes = NULL;
        self->exif_bytes = NULL;
        self->xmp_bytes = NULL;

        encoder = avifEncoderCreate();

        if (max_threads == 0) {
            init_max_threads();
        }

        encoder->maxThreads = max_threads;
        encoder->minQuantizer = enc_options.qmin;
        encoder->maxQuantizer = enc_options.qmax;
        encoder->codecChoice = enc_options.codec;
        encoder->speed = enc_options.speed;
        encoder->timescale = (uint64_t)1000;
        self->encoder = encoder;

        avifImage *image = avifImageCreateEmpty();
        // Set these in advance so any upcoming RGB -> YUV use the proper coefficients
        image->yuvRange = enc_options.range;
        image->yuvFormat = enc_options.subsampling;
        image->colorPrimaries = AVIF_COLOR_PRIMARIES_UNSPECIFIED;
        image->transferCharacteristics = AVIF_TRANSFER_CHARACTERISTICS_UNSPECIFIED;
        image->matrixCoefficients = AVIF_MATRIX_COEFFICIENTS_BT601;
        image->width = width;
        image->height = height;
        image->depth = 8;

        if (PyBytes_GET_SIZE(icc_bytes)) {
            self->icc_bytes = icc_bytes;
            Py_INCREF(icc_bytes);
            avifImageSetProfileICC(
                image,
                (uint8_t *)PyBytes_AS_STRING(icc_bytes),
                PyBytes_GET_SIZE(icc_bytes));
        } else {
            image->colorPrimaries = AVIF_COLOR_PRIMARIES_BT709;
            image->transferCharacteristics = AVIF_TRANSFER_CHARACTERISTICS_SRGB;
        }

        if (PyBytes_GET_SIZE(exif_bytes)) {
            self->exif_bytes = exif_bytes;
            Py_INCREF(exif_bytes);
            avifImageSetMetadataExif(
                image,
                (uint8_t *)PyBytes_AS_STRING(exif_bytes),
                PyBytes_GET_SIZE(exif_bytes));
        }
        if (PyBytes_GET_SIZE(xmp_bytes)) {
            self->xmp_bytes = xmp_bytes;
            Py_INCREF(xmp_bytes);
            avifImageSetMetadataXMP(
                image,
                (uint8_t *)PyBytes_AS_STRING(xmp_bytes),
                PyBytes_GET_SIZE(xmp_bytes));
        }

        self->image = image;
        self->frame_index = -1;

        return (PyObject *)self;
    }
    PyErr_SetString(PyExc_RuntimeError, "could not create encoder object");
    return NULL;
}

PyObject *
_encoder_dealloc(AvifEncoderObject *self) {
    if (self->encoder) {
        avifEncoderDestroy(self->encoder);
    }
    if (self->image) {
        avifImageDestroy(self->image);
    }
    Py_XDECREF(self->icc_bytes);
    Py_XDECREF(self->exif_bytes);
    Py_XDECREF(self->xmp_bytes);
    Py_RETURN_NONE;
}

PyObject *
_encoder_add(AvifEncoderObject *self, PyObject *args) {
    uint8_t *rgb_bytes;
    Py_ssize_t size;
    unsigned int duration;
    unsigned int width;
    unsigned int height;
    char *mode;
    PyObject *is_single_frame = NULL;
    PyObject *ret = Py_None;

    int is_first_frame;
    int channels;
    avifRGBImage rgb;
    avifResult result;

    avifEncoder *encoder = self->encoder;
    avifImage *image = self->image;
    avifImage *frame = NULL;

    if (!PyArg_ParseTuple(
            args,
            "z#IIIsO",
            (char **)&rgb_bytes,
            &size,
            &duration,
            &width,
            &height,
            &mode,
            &is_single_frame)) {
        return NULL;
    }

    is_first_frame = (self->frame_index == -1);

    if ((image->width != width) || (image->height != height)) {
        PyErr_Format(
            PyExc_ValueError,
            "Image sequence dimensions mismatch, %ux%u != %ux%u",
            image->width,
            image->height,
            width,
            height);
        return NULL;
    }

    if (is_first_frame) {
        // If we don't have an image populated with yuv planes, this is the first frame
        frame = image;
    } else {
        frame = avifImageCreateEmpty();

        frame->colorPrimaries = image->colorPrimaries;
        frame->transferCharacteristics = image->transferCharacteristics;
        frame->matrixCoefficients = image->matrixCoefficients;
        frame->yuvRange = image->yuvRange;
        frame->yuvFormat = image->yuvFormat;
        frame->depth = image->depth;
    }

    frame->width = width;
    frame->height = height;

    memset(&rgb, 0, sizeof(avifRGBImage));

    avifRGBImageSetDefaults(&rgb, frame);
    rgb.depth = 8;

    if (strcmp(mode, "RGBA") == 0) {
        rgb.format = AVIF_RGB_FORMAT_RGBA;
        channels = 4;
    } else {
        rgb.format = AVIF_RGB_FORMAT_RGB;
        channels = 3;
    }

    avifRGBImageAllocatePixels(&rgb);

    if (rgb.rowBytes * rgb.height != size) {
        PyErr_Format(
            PyExc_RuntimeError,
            "rgb data is incorrect size: %u * %u (%u) != %u",
            rgb.rowBytes,
            rgb.height,
            rgb.rowBytes * rgb.height,
            size);
        ret = NULL;
        goto end;
    }

    // rgb.pixels is safe for writes
    memcpy(rgb.pixels, rgb_bytes, size);

    Py_BEGIN_ALLOW_THREADS
    result = avifImageRGBToYUV(frame, &rgb);
    Py_END_ALLOW_THREADS

    if (result != AVIF_RESULT_OK) {
        PyErr_Format(
            exc_type_for_avif_result(result),
            "Conversion to YUV failed: %s",
            avifResultToString(result));
        ret = NULL;
        goto end;
    }

    uint32_t addImageFlags = AVIF_ADD_IMAGE_FLAG_NONE;
    if (PyObject_IsTrue(is_single_frame)) {
        addImageFlags |= AVIF_ADD_IMAGE_FLAG_SINGLE;
    }

    Py_BEGIN_ALLOW_THREADS
    result = avifEncoderAddImage(encoder, frame, duration, addImageFlags);
    Py_END_ALLOW_THREADS

    if (result != AVIF_RESULT_OK) {
        PyErr_Format(
            exc_type_for_avif_result(result),
            "Failed to encode image: %s",
            avifResultToString(result));
        ret = NULL;
        goto end;
    }

end:
    avifRGBImageFreePixels(&rgb);
    if (!is_first_frame) {
        avifImageDestroy(frame);
    }

    if (ret == Py_None) {
        self->frame_index++;
        Py_RETURN_NONE;
    } else {
        return ret;
    }
}

PyObject *
_encoder_finish(AvifEncoderObject *self) {
    avifEncoder *encoder = self->encoder;

    avifRWData raw = AVIF_DATA_EMPTY;
    avifResult result;
    PyObject *ret = NULL;

    Py_BEGIN_ALLOW_THREADS
    result = avifEncoderFinish(encoder, &raw);
    Py_END_ALLOW_THREADS

    if (result != AVIF_RESULT_OK) {
        PyErr_Format(
            exc_type_for_avif_result(result),
            "Failed to finish encoding: %s",
            avifResultToString(result));
        avifRWDataFree(&raw);
        return NULL;
    }

    ret = PyBytes_FromStringAndSize((char *)raw.data, raw.size);

    avifRWDataFree(&raw);

    return ret;
}

// Decoder functions
PyObject *
AvifDecoderNew(PyObject *self_, PyObject *args) {
    PyObject *avif_bytes;
    AvifDecoderObject *self = NULL;

    char *upsampling_str;
    char *codec_str;
    avifCodecChoice codec;
    avifChromaUpsampling upsampling;

    avifResult result;

    if (!PyArg_ParseTuple(args, "Sss", &avif_bytes, &codec_str, &upsampling_str)) {
        return NULL;
    }

    if (!strcmp(upsampling_str, "auto")) {
        upsampling = AVIF_CHROMA_UPSAMPLING_AUTOMATIC;
    } else if (!strcmp(upsampling_str, "fastest")) {
        upsampling = AVIF_CHROMA_UPSAMPLING_FASTEST;
    } else if (!strcmp(upsampling_str, "best")) {
        upsampling = AVIF_CHROMA_UPSAMPLING_BEST_QUALITY;
    } else if (!strcmp(upsampling_str, "nearest")) {
        upsampling = AVIF_CHROMA_UPSAMPLING_NEAREST;
    } else if (!strcmp(upsampling_str, "bilinear")) {
        upsampling = AVIF_CHROMA_UPSAMPLING_BILINEAR;
    } else {
        PyErr_Format(PyExc_ValueError, "Invalid upsampling option: %s", upsampling_str);
        return NULL;
    }

    if (strcmp(codec_str, "auto") == 0) {
        codec = AVIF_CODEC_CHOICE_AUTO;
    } else {
        codec = avifCodecChoiceFromName(codec_str);
        if (codec == AVIF_CODEC_CHOICE_AUTO) {
            PyErr_Format(PyExc_ValueError, "Invalid codec: %s", codec_str);
            return NULL;
        } else {
            const char *codec_name = avifCodecName(codec, AVIF_CODEC_FLAG_CAN_DECODE);
            if (codec_name == NULL) {
                PyErr_Format(
                    PyExc_ValueError, "AV1 Codec cannot decode: %s", codec_str);
                return NULL;
            }
        }
    }

    self = PyObject_New(AvifDecoderObject, &AvifDecoder_Type);
    if (!self) {
        PyErr_SetString(PyExc_RuntimeError, "could not create decoder object");
        return NULL;
    }
    self->decoder = NULL;

    Py_INCREF(avif_bytes);
    self->data = avif_bytes;

    self->decoder = avifDecoderCreate();
#if AVIF_VERSION >= 80400
    if (max_threads == 0) {
        init_max_threads();
    }
    self->decoder->maxThreads = max_threads;
#endif
    self->decoder->codecChoice = codec;

    avifDecoderSetIOMemory(
        self->decoder,
        (uint8_t *)PyBytes_AS_STRING(self->data),
        PyBytes_GET_SIZE(self->data));

    result = avifDecoderParse(self->decoder);

    if (result != AVIF_RESULT_OK) {
        PyErr_Format(
            exc_type_for_avif_result(result),
            "Failed to decode image: %s",
            avifResultToString(result));
        avifDecoderDestroy(self->decoder);
        self->decoder = NULL;
        Py_DECREF(self);
        return NULL;
    }

    if (self->decoder->alphaPresent) {
        self->mode = "RGBA";
    } else {
        self->mode = "RGB";
    }

    return (PyObject *)self;
}

PyObject *
_decoder_dealloc(AvifDecoderObject *self) {
    if (self->decoder) {
        avifDecoderDestroy(self->decoder);
    }
    Py_XDECREF(self->data);
    Py_RETURN_NONE;
}

PyObject *
_decoder_get_info(AvifDecoderObject *self) {
    avifDecoder *decoder = self->decoder;
    avifImage *image = decoder->image;

    PyObject *icc = NULL;
    PyObject *exif = NULL;
    PyObject *xmp = NULL;
    PyObject *ret = NULL;

    if (image->xmp.size) {
        xmp = PyBytes_FromStringAndSize((const char *)image->xmp.data, image->xmp.size);
    }

    if (image->exif.size) {
        exif =
            PyBytes_FromStringAndSize((const char *)image->exif.data, image->exif.size);
    }

    if (image->icc.size) {
        icc = PyBytes_FromStringAndSize((const char *)image->icc.data, image->icc.size);
    }

    ret = Py_BuildValue(
        "IIIsSSS",
        image->width,
        image->height,
        decoder->imageCount,
        self->mode,
        NULL == icc ? Py_None : icc,
        NULL == exif ? Py_None : exif,
        NULL == xmp ? Py_None : xmp);

    Py_XDECREF(xmp);
    Py_XDECREF(exif);
    Py_XDECREF(icc);

    return ret;
}

PyObject *
_decoder_get_frame(AvifDecoderObject *self, PyObject *args) {
    PyObject *bytes;
    PyObject *ret;
    Py_ssize_t size;
    avifResult result;
    avifRGBImage rgb;
    avifDecoder *decoder;
    avifImage *image;
    uint32_t frame_index;
    uint32_t row_bytes;

    decoder = self->decoder;

    if (!PyArg_ParseTuple(args, "I", &frame_index)) {
        return NULL;
    }

    result = avifDecoderNthImage(decoder, frame_index);

    if (result != AVIF_RESULT_OK) {
        PyErr_Format(
            exc_type_for_avif_result(result),
            "Failed to decode frame %u: %s",
            decoder->imageIndex + 1,
            avifResultToString(result));
        return NULL;
    }

    image = decoder->image;

    memset(&rgb, 0, sizeof(rgb));
    avifRGBImageSetDefaults(&rgb, image);

    rgb.depth = 8;

    if (decoder->alphaPresent) {
        rgb.format = AVIF_RGB_FORMAT_RGBA;
    } else {
        rgb.format = AVIF_RGB_FORMAT_RGB;
        rgb.ignoreAlpha = AVIF_TRUE;
    }

    row_bytes = rgb.width * avifRGBImagePixelSize(&rgb);

    if (rgb.height > PY_SSIZE_T_MAX / row_bytes) {
        PyErr_SetString(PyExc_MemoryError, "Integer overflow in pixel size");
        return NULL;
    }

    avifRGBImageAllocatePixels(&rgb);

    Py_BEGIN_ALLOW_THREADS
    result = avifImageYUVToRGB(image, &rgb);
    Py_END_ALLOW_THREADS

    if (result != AVIF_RESULT_OK) {
        PyErr_Format(
            exc_type_for_avif_result(result),
            "Conversion from YUV failed: %s",
            avifResultToString(result));
        avifRGBImageFreePixels(&rgb);
        return NULL;
    }

    size = rgb.rowBytes * rgb.height;

    bytes = PyBytes_FromStringAndSize((char *)rgb.pixels, size);
    avifRGBImageFreePixels(&rgb);

    ret = Py_BuildValue(
        "SKKK",
        bytes,
        decoder->timescale,
        decoder->imageTiming.ptsInTimescales,
        decoder->imageTiming.durationInTimescales);

    Py_DECREF(bytes);

    return ret;
}

/* -------------------------------------------------------------------- */
/* Type Definitions                                                     */
/* -------------------------------------------------------------------- */

// AvifEncoder methods
static struct PyMethodDef _encoder_methods[] = {
    {"add", (PyCFunction)_encoder_add, METH_VARARGS},
    {"finish", (PyCFunction)_encoder_finish, METH_NOARGS},
    {NULL, NULL} /* sentinel */
};

// AvifDecoder type definition
static PyTypeObject AvifEncoder_Type = {
    // clang-format off
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "AvifEncoder",
    // clang-format on
    .tp_basicsize = sizeof(AvifEncoderObject),
    .tp_dealloc = (destructor)_encoder_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_methods = _encoder_methods,
};

// AvifDecoder methods
static struct PyMethodDef _decoder_methods[] = {
    {"get_info", (PyCFunction)_decoder_get_info, METH_NOARGS},
    {"get_frame", (PyCFunction)_decoder_get_frame, METH_VARARGS},
    {NULL, NULL} /* sentinel */
};

// AvifDecoder type definition
static PyTypeObject AvifDecoder_Type = {
    // clang-format off
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "AvifDecoder",
    // clang-format on
    .tp_basicsize = sizeof(AvifDecoderObject),
    .tp_itemsize = 0,
    .tp_dealloc = (destructor)_decoder_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_methods = _decoder_methods,
};

PyObject *
AvifCodecVersions() {
    char codecVersions[256];
    avifCodecVersions(codecVersions);
    return PyUnicode_FromString(codecVersions);
}

/* -------------------------------------------------------------------- */
/* Module Setup                                                         */
/* -------------------------------------------------------------------- */

static PyMethodDef avifMethods[] = {
    {"AvifDecoder", AvifDecoderNew, METH_VARARGS},
    {"AvifEncoder", AvifEncoderNew, METH_VARARGS},
    {"AvifCodecVersions", AvifCodecVersions, METH_NOARGS},
    {"decoder_codec_available", _decoder_codec_available, METH_VARARGS},
    {"encoder_codec_available", _encoder_codec_available, METH_VARARGS},
    {NULL, NULL}};

static int
setup_module(PyObject *m) {
    PyObject *d = PyModule_GetDict(m);

    PyDict_SetItemString(d, "libavif_version", PyUnicode_FromString(avifVersion()));

    if (PyType_Ready(&AvifDecoder_Type) < 0 || PyType_Ready(&AvifEncoder_Type) < 0) {
        return -1;
    }
    return 0;
}

PyMODINIT_FUNC
PyInit__avif(void) {
    PyObject *m;

    static PyModuleDef module_def = {
        PyModuleDef_HEAD_INIT,
        .m_name = "_avif",
        .m_size = -1,
        .m_methods = avifMethods,
    };

    m = PyModule_Create(&module_def);
    if (setup_module(m) < 0) {
        return NULL;
    }

    return m;
}
