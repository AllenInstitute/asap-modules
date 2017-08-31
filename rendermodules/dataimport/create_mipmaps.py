from PIL import Image
import argparse
import os


def create_mipmaps(inputImage, outputDirectory='.', mipmaplevels=[1, 2, 3],
                   outputformat='tif', convertTo8bit=True, force_redo=True):
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

        if not os.path.isdir(outdir):
            os.makedirs(outdir, 0775)

        outpath = os.path.join(outputDirectory, str(level),
                               '{basename}.{fmt}'.format(
                                   basename=inputImage[1:], fmt=outputformat))

        print outpath
        try:
            dwnImage.save(outpath)
        except KeyError, e:
            # unknown output format
            print 'KeyError - "%s"' % str(e)
        except IndexError, e:
            # file cannot be written to disk
            print 'IndexError - "%s"' % str(e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=("Create downsampled images of the input "
                     "image at different mipmap levels"))

    parser.add_argument(
        '--inputImage', help="Path to the input image.")
    parser.add_argument(
        '--outputDirectory', help="Path to save midmap images", default=None)
    parser.add_argument(
        '--mipmaplevels', nargs='*', help="mipmaplevels to generate",
        default=[1, 2, 3], type=int)
    parser.add_argument(
        '--outputformat', help="format to save images", default='tiff')
    parser.add_argument(
        '--verbose', help="verbose output", default=False, action="store_true")

    args = parser.parse_args()

    print 'outdir', args.outputDirectory
    if args.outputDirectory is None:
        args.outputDirectory = os.path.split(args.inputImage)[0]
        if len(args.outputDirectory) == 0:
            args.outputDirectory = '.'

    create_mipmaps(args.inputImage, args.outputDirectory,
                   args.mipmaplevels, args.outputformat)

#     if not os.path.isdirf(args.outputDirectory):
#         os.makedirs(args.outputDirectory)

#     im = Image.open(args.inputImage)
#     print 'origmode',im.mode
#     origsize = im.size
#     table=[ i/256 for i in range(65536) ]
#     im = im.convert('I')
#     im = im.point(table,'L')
#     print 'new mode',im.mode
#     inputFileName = os.path.split(args.inputImage)[1]

#     for level in args.mipmaplevels:
#         newsize = tuple(map(lambda x: x/(2**level), origsize))
#         dwnImage = im.resize(newsize)
#         outpath = os.path.join(args.outputDirectory,inputFileName[0:-4]+'_mip%02d.'%level+args.outputformat)
#         dwnImage.save(outpath)
#         print outpath,level,newsize
