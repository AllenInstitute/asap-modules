if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.intensity_correction.apply_muliplicative_correction"
import os
import renderapi
from functools import partial
import numpy as np
import tifffile
from ..module.render_module import RenderModule
from ..module.render_module import StackTransitionModule
from rendermodules.intensity_correction.schemas import MultIntensityCorrParams
import urllib
import urlparse

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
    "z": 102,
    "pool_size": 20
}


def intensity_corr(img, ff,clip,scale_factor,clip_min,clip_max):
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
    # add clipping or scaling
    result = result/scale_factor
    if (clip):
        np.clip(result, clip_min, clip_max, out=result)
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
    mml = ts.ip[0]
    url = urllib.unquote(urlparse.urlparse(
        str(mml.imageUrl)).path)
    img0 = tifffile.imread(url)
    (N, M) = img0.shape
    return N, M, img0


def process_tile(C, dirout, stackname, clip,scale_factor,clip_min,clip_max,input_ts):
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
    """
    [N1, M1, I] = getImage(input_ts)
    Res = intensity_corr(I, C, clip, scale_factor, clip_min, clip_max)

    [head, tail] = os.path.split(input_ts.ip[0].imageUrl)
    outImage = os.path.join("%s" % dirout, "%s_%04d_%s" %
                            (stackname, input_ts.z, tail))
    tifffile.imsave(outImage, Res)

    output_ts = input_ts
    mm = renderapi.image_pyramid.MipMap(imageUrl=outImage)

    output_ts.ip = renderapi.image_pyramid.ImagePyramid()
    output_ts.ip[0] = mm

    return output_ts


class MultIntensityCorr(StackTransitionModule):
    default_schema = MultIntensityCorrParams

    def run(self):
        # get tilespecs
        # Z = self.args['z_index']
        Z = self.zValues[0]
        inp_tilespecs = renderapi.tilespec.get_tile_specs_from_z(
            self.args['input_stack'], Z, render=self.render)
        corr_tilespecs = renderapi.tilespec.get_tile_specs_from_z(
            self.args['correction_stack'], Z, render=self.render)
        # mult intensity correct each tilespecs and return tilespecs
        N, M, C = getImage(corr_tilespecs[0])
        mypartial = partial(
            process_tile, C, self.args['output_directory'], self.args['output_stack'],self.args['clip'],self.args['scale_factor'],self.args['clip_min'],self.args['clip_max'])
        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            output_tilespecs = pool.map(mypartial, inp_tilespecs)

        # upload to render
        renderapi.stack.create_stack(
            self.args['output_stack'], cycleNumber=self.args['cycle_number'],
            cycleStepNumber=self.args['cycle_step_number'], render=self.render)

        if self.args['overwrite_zlayer']:
            try:
                renderapi.stack.delete_section(
                    self.args['output_stack'], self.zValues[0],  # self.args['z_index'],
                    render=self.render)
            except renderapi.errors.RenderError as e:
                self.logger.error(e)

        renderapi.client.import_tilespecs_parallel(
            self.args['output_stack'], output_tilespecs,
            poolsize = self.args['pool_size'],render=self.render,close_stack=self.args['close_stack'])


if __name__ == "__main__":
    mod = MultIntensityCorr(input_data=example_input)
    mod.run()
