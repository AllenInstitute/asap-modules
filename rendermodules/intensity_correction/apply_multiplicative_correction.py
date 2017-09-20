if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.intensity_correction.apply_muliplicative_correction"
import json
import os
import renderapi
from ..module.render_module import RenderModule, RenderParameters
from argschema.fields import InputFile, InputDir, Str, Float, Int, Bool, OutputDir
from functools import partial
import numpy as np
from PIL import Image
import tifffile
import re

example_input = {
    "render": {
        "host": "ibs-forrestc-ux1",
        "port": 8080,
        "owner": "M246930_Scnn1a",
        "project": "M246930_Scnn1a_4",
        "client_scripts": "/var/www/render/render-ws-java-client/src/main/scripts"
    },
    "input_stack": "Acquisition_DAPI_1",
    "correction_stack": "Median_TEST_DAPI_1",
    "output_stack": "Flatfield_TEST_DAPI_1",
    "output_directory": "/nas/data/M246930_Scnn1a_4/processed/FlatfieldTEST",
    "z_index": 102,
    "pool_size": 20
}


class MultIntensityCorrParams(RenderParameters):
    input_stack = Str(required=True,
                      description="Input stack")
    output_stack = Str(required=True,
                       description='Output stack')
    correction_stack = Str(required=True,
                           description='Correction stack (usually median stack for AT data)')
    output_directory = OutputDir(required=True,
                                 description='Directory for storing Images')
    z_index = Int(required=True,
                  description='z value for section')
    pool_size = Int(required=False, default=20,
                    description='size of pool for parallel processing (default=20)')
    move_input = Bool(required=False, default=False,
                      description="whether to move input tiles to new location")
    move_input_regex_find = Str(required=False,
                                default="",
                                description="regex string to find in input filenames")
    move_input_regex_replace = Str(required=False,
                                   default="",
                                   description="regex string to replace in input filenames")


def intensity_corr(img, ff):
    """utility function to correct an image with a flatfield correction
    will take img and return 
    img_out = img * max(ff) / (ff + .0001)
    converted back to the original type of img

    Parameters
    ==========
    img: numpy.array
        N,M array to correct, could be any type
    ff: numpy.array
        N,M array of flatfield correction, could be of any type

    Returns
    =======
    numpy.array
        N,M  numpy array of the same type as img but now corrected
    """
    img_type = img.dtype
    img = img.astype(float)
    ff = ff.astype(float)
    num = np.ones((ff.shape[0], ff.shape[1]))
    fac = np.divide(num * np.amax(ff), ff + 0.0001)
    result = np.multiply(img, fac)
    result = np.multiply(result, np.mean(img) / np.mean(result))
    # convert back to original type
    result_int = result.astype(img_type)
    return result_int


def getImage(ts):
    """Simple function to get the level 0 image of this tilespec 
    as a numpy array

    Parameters
    ==========
    ts: renderapi.tilespec.TileSpec
        tilespec to get images from 
        (presently assumes this is a tiff image whose URL can be read with tifffile)

    Returns
    =======
    numpy.array
        2d numpy array of this image
    """
    d = ts.to_dict()
    mml = ts.ip.get(0)
    img0 = tifffile.imread(mml['imageUrl'])
    (N, M) = img0.shape
    return N, M, img0


def process_tile(C, dirout, stackname, input_ts, regex_pattern=None,
                 regex_replace=None):
    """function to correct each tile in the input_ts with the matrix C,
    and potentially move the original tiles to a new location.abs

    Parameters
    ==========
    C: numpy.array
        a 2d numpy array of uint16 or uint8 that represents the correction to apply
    dirout: str
        the path to the directory to save all corrected images
    input_ts: renderapi.tilespec.TileSpec
        the tilespec with the tiles to be corrected
    regex_pattern: re.Pattern or None
        if not None this is the regex pattern to find in the input_ts path when saving
        the original image file to a new location. If None the input file will not be moved
    regex_replace:
        this is the string to replace the regex pattern with in the input_ts path when
        saving the original image file to a new location
    """
    [N1, M1, I] = getImage(input_ts)
    Res = intensity_corr(I, C)
    if not os.path.exists(dirout):
        os.makedirs(dirout)
    [head, tail] = os.path.split(input_ts.ip.get(0).imageUrl)
    outImage = os.path.join("%s" % dirout, "%s_%04d_%s" %
                            (stackname, input_ts.z, tail))
    tifffile.imsave(outImage, I)

    d = input_ts.to_dict()
    for i in range(1, len(d['mipmapLevels'])):
        del d['mipmapLevels'][i]
    d['mipmapLevels'][0]['imageUrl'] = outImage
    output_ts = renderapi.tilespec.TileSpec(json=d)
    return input_ts, output_ts


class MultIntensityCorr(RenderModule):
    default_schema = MultIntensityCorrParams

    def run(self):

        if self.args['move_input']:
            assert(len(self.args['move_input_regex_find']) > 0)
            assert(len(self.args['move_input_regex_replace']) > 0)
            regex_pattern = re.compile(self.args['move_input_regex_find'])
            regex_replace = self.args['move_input_regex_replace']
        else:
            regex_replace = None
            regex_pattern = None

        # get tilespecs
        Z = self.args['z_index']
        inp_tilespecs = renderapi.tilespec.get_tile_specs_from_z(
            self.args['input_stack'], Z, render=self.render)
        corr_tilespecs = renderapi.tilespec.get_tile_specs_from_z(
            self.args['correction_stack'], Z, render=self.render)
        print inp_tilespecs
        # mult intensity correct each tilespecs and return tilespecs
        render = self.render
        C = getImage(corr_tilespecs[0])
        mypartial = partial(
            process_tile, C, self.args['output_directory'], self.args['output_stack'],
            regex_pattern=regex_pattern, regex_replace=regex_replace)
        # with renderapi.client.WithPool(self.args['pool_size']) as pool:
        #    tilespecs = pool.map(mypartial, inp_tilespecs)
        tilespecs = map(mypartial, inp_tilespecs)

        output_tilespecs = [ts[1] for ts in tilespecs]
        new_input_tilespecs = [ts[0] for ts in tilespecs]

        # upload to render
        renderapi.stack.create_stack(
            self.args['output_stack'], cycleNumber=2, cycleStepNumber=1, render=self.render)
        renderapi.client.import_tilespecs(
            self.args['output_stack'], output_tilespecs, render=self.render)
        renderapi.stack.set_stack_state(
            self.args['output_stack'], "COMPLETE", render=self.render)

        # upload new input tilespecs
        if regex_pattern is not None:
            renderapi.client.import_tilespecs(
                self.args['input_stack'],
                new_input_tilespecs, render=self.render)
            renderapi.stack.set_stack_state(
                self.args['input_stack'], "COMPLETE", render=self.render)


if __name__ == "__main__":
    mod = MultIntensityCorr(input_data=example_input)
    mod.run()
