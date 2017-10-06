from PIL import Image
import argparse
import os
from rendermodules.module.render_module import RenderModuleException

class CreateMipMapException(RenderModuleException):
    """Exception raised when there is a problem creating a mipmap"""

def create_mipmaps(inputImage, outputDirectory='.', mipmaplevels=[1, 2, 3],
                   outputformat='tif', convertTo8bit=True, force_redo=True):
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
    im = Image.open(inputImage)
    origsize = im.size
    if convertTo8bit:
        table = [i/256 for i in range(65536)]
        im = im.convert('I')
        im = im.point(table, 'L')

    for level in mipmaplevels:
        newsize = tuple(map(lambda x: x/(2**level), origsize))
        dwnImage = im.resize(newsize)

        outdir = os.path.join(outputDirectory, str(level),
                              os.path.dirname(inputImage[1:]))

        try:
            os.makedirs(outdir, 0775)
        except OSError as e:
            pass  # TODO better validation

        outpath = os.path.join(outputDirectory, str(level),
                               '{basename}.{fmt}'.format(
                                   basename=inputImage.lstrip(os.sep),
                                   fmt=outputformat))
        makeImage=True
        if os.path.isfile(outpath):
            if not force_redo:
                makeImage = False
        if makeImage:
            try:
                dwnImage.save(outpath)
            except KeyError, e:
                # unknown output format
                raise(CreateMipMapException('KeyError - "%s"' % str(e)))
            except IOError, e:
                # file cannot be written to disk
                raise(CreateMipMapException('IOError - "%s"' % str(e)))
