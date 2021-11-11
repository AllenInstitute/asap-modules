import io
import os

import numpy
import pathlib2 as pathlib
from six.moves import urllib
from skimage.measure import block_reduce

from asap.utilities.pillow_utils import Image
from asap.module.render_module import RenderModuleException
from asap.utilities import uri_utils

try:
    xrange
except NameError:
    xrange = range

PIL_filters = {
    "NEAREST": Image.NEAREST,
    "BOX": Image.BOX,
    "BILINEAR": Image.BILINEAR,
    "HAMMING": Image.HAMMING,
    "BICUBIC": Image.BICUBIC,
    "LANCZOS": Image.LANCZOS
    }

block_funcs = {
    'mean': numpy.mean,
    'median': numpy.median,
    'min': numpy.min
}


class CreateMipMapException(RenderModuleException):
    """Exception raised when there is a problem creating a mipmap"""
    pass


def writeImage(img, outpath, force_redo):
    if not force_redo:
        # FIXME uri_handler writebytes implementation allows force_redo....
        raise NotImplementedError(
            "toggling force_redo is not supported in this version. "
            "Mipmaps must be regenerated.")

    # TODO does this need a step to try to register the extension?
    imgfmt = Image.EXTENSION[os.path.splitext(
        urllib.parse.urlparse(outpath).path)[-1]]

    imgio = io.BytesIO()
    img.save(imgio, format=imgfmt)
    uri_utils.uri_writebytes(outpath, imgio.getvalue())


def mipmap_block_reduce(im, levels_file_map, block_func="mean",
                        force_redo=True, **kwargs):
    try:
        reduce_func = block_funcs[block_func]
    except KeyError as e:
        raise CreateMipMapException(
            "invalid block_reduce function {}".format(e))

    tempimg = numpy.array(im)
    target_dtype = tempimg.dtype
    lastlevel = 0
    for level, outpath in levels_file_map.items():
        for i in xrange(lastlevel, level):
            tempimg = block_reduce(tempimg, (2, 2), func=reduce_func).astype(
                target_dtype)

        # is it okay to do non-progressive downsampling (below)?
        # tempimg = block_reduce(
        #     tempimg, (2 * (level - lastlevel), 2 * (level - lastlevel)),
        #     func=reduce_func)
        lastlevel = level
        writeImage(Image.fromarray(tempimg), outpath, force_redo)


def mipmap_PIL(im, levels_file_map, ds_filter="NEAREST",
               force_redo=True, **kwargs):
    try:
        PIL_filter = PIL_filters[ds_filter]
    except KeyError as e:
        raise CreateMipMapException("invalid PIL filter {}".format(e))

    origsize = im.size
    for level, outpath in levels_file_map.items():
        newsize = tuple(map(lambda x: x//(2**level), origsize))
        dwnImage = im.resize(newsize, resample=PIL_filter)
        writeImage(dwnImage, outpath, force_redo)


method_funcs = {
    'PIL': mipmap_PIL,
    'block_reduce': mipmap_block_reduce
}


def create_mipmaps_uri(inputImage, outputDirectory=None, method="block_reduce",
                       mipmaplevels=[1, 2, 3], outputformat='tif',
                       convertTo8bit=True, force_redo=True,
                       **kwargs):
    """function to create downsampled images from an input image

    Parameters
    ==========
    inputImage: str
        path to input image
    outputDirectory: str
        path to save output images (default to current directory)
    mipmaplevels: list or tuple
        list or tuple of integers (default to (1,2,3))
    outputformat: str
        string representation of extension of image format (default tif)
    convertTo8bit: boolean
        whether to convert the image to 8 bit, dividing each value by 255
    force_redo: boolean
        whether to recreate mip map images if they already exist
    method: str
        string corresponding to downsampling method
    block_func: str
        string corresponding to function used by block_reduce
    ds_filter: str
        string corresponding to PIL downsample mode

    Returns
    =======
    list
        list of output images created in order of levels

    Raises
    ======
    MipMapException
        if an image cannot be created for some reason
    """
    # Need to check if the level 0 image exists
    # TODO this is for uri implementation
    inputImagepath = urllib.parse.urlparse(inputImage).path
    im = Image.open(io.BytesIO(uri_utils.uri_readbytes(inputImage)))
    if convertTo8bit:
        table = [i//256 for i in range(65536)]
        im = im.convert('I')
        im = im.point(table, 'L')

    levels_uri_map = {int(level): uri_utils.uri_join(
        outputDirectory, str(level), '{basename}.{fmt}'.format(
            basename=inputImagepath.lstrip("/"), fmt=outputformat))
                       for level in mipmaplevels}

    try:
        method_funcs[method](
            im, levels_uri_map, force_redo=force_redo, **kwargs)
    except KeyError as e:
        raise CreateMipMapException("invalid method {}".format(e))

    return levels_uri_map


def create_mipmaps_legacy(inputImage, outputDirectory='.', *args, **kwargs):
    """legacy create_mipmaps function"""

    outputDirectory_uri = pathlib.Path(outputDirectory).resolve().as_uri()
    inputImage_uri = pathlib.Path(inputImage).resolve().as_uri()
    levels_uri_map = create_mipmaps_uri(
        inputImage_uri, outputDirectory_uri, *args, **kwargs)

    levels_file_map = {
        lvl: urllib.parse.unquote(urllib.parse.urlparse(u).path)
        for lvl, u in levels_uri_map.items()}
    return levels_file_map


create_mipmaps = create_mipmaps_legacy
