#!/usr/bin/env python

from functools import partial
import os

import numpy as np
import renderapi
from six.moves import urllib
import tifffile

from rendermodules.module.render_module import StackTransitionModule
from rendermodules.module.render_module import RenderModuleException
from rendermodules.intensity_correction.schemas import MultIntensityCorrParams

if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.intensity_correction.apply_muliplicative_correction"

example_input = {
    "render": {
        "host": "10.128.24.33",
        "port": 80,
        "owner": "multchan",
        "project": "M335503_Ai139_smallvol",
        "client_scripts": '/shared/render/render-ws-java-client/src/main/scripts'
    },
    "input_stack": "TESTAcquisition_Session1",
    "correction_stack": "TESTMedian_Session1",
    "output_stack": "TESTFlatfield_Session1",
    "output_directory": "/nas2/data/M335503_Ai139_smallvol/processed/TESTFlatfield",
    "z": 501,
    "pool_size": 20
}


def intensity_corr(img, ff, clip, scale_factor, clip_min, clip_max):
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


def getImage(ts, channel=None):
    """Simple function to get the level 0 image of this tilespec
    as a numpy array

    Parameters
    ==========
    ts: renderapi.tilespec.TileSpec
        tilespec to get images from
        (presently assumes this is a tiff image whose URL can be
        read with tifffile)
    channel: str
        channel name to get image of, default=None which will
        default to the non channel image pyramid
    Returns
    =======
    numpy.array
        2d numpy array of this image
    """
    if channel is None:
        mml = ts.ip[0]
    else:
        if ts.channels is None:
            raise RenderModuleException(
                'No channels exist for this tilespec (ts.tileId={}'.format(
                    ts.tileId))
        else:
            try:
                chan = next(ch for ch in ts.channels if ch.name == channel)
                mml = chan.ip[0]
            except StopIteration:
                raise RenderModuleException(
                    'Tilespec {} does not contain channel {}'.format(
                        ts.tileId, channel))

    url = urllib.parse.unquote(urllib.parse.urlparse(
        str(mml.imageUrl)).path)
    img0 = tifffile.imread(url)
    (N, M) = img0.shape
    return N, M, img0


def write_image(dirout, orig_imageurl, Res, stackname, z):
    [head, tail] = os.path.split(orig_imageurl)
    outImage = os.path.join("%s" % dirout, "%s_%04d_%s" %
                            (stackname, z, tail))
    tifffile.imsave(outImage, Res)
    return outImage


def process_tile(C, dirout, stackname, clip, scale_factor, clip_min, clip_max,
                 input_ts, corr_dict=None):
    """function to correct each tile in the input_ts with the matrix C,
    and potentially move the original tiles to a new location.abs

    Parameters
    ==========
    C: numpy.array
        a 2d numpy array of uint16 or uint8 that represents the
        correction to apply
    corr_dict: dict or None
        a dictionary with keys of strings of channel names and values
        of corrections (as with C).
        If None, C will be applied to each channel, if they exist.
    dirout: str
        the path to the directory to save all corrected images
    input_ts: renderapi.tilespec.TileSpec
        the tilespec with the tiles to be corrected
    """
    [N1, M1, I] = getImage(input_ts)
    Res = intensity_corr(I, C, clip, scale_factor, clip_min, clip_max)
    outImage = write_image(
        dirout, input_ts.ip[0].imageUrl, Res, stackname, input_ts.z)

    output_ts = input_ts
    mm = renderapi.image_pyramid.MipMap(imageUrl=outImage)
    output_ts.ip = renderapi.image_pyramid.ImagePyramid()
    output_ts.ip[0] = mm

    if output_ts.channels is not None:
        for chan in output_ts.channels:
            [N1, M1, I] = getImage(output_ts, chan.name)
            if corr_dict:
                CC = corr_dict[chan.name]
            else:
                CC = C
            CRes = intensity_corr(
                I, CC, clip, scale_factor, clip_min, clip_max)
            chan_outImage = write_image(
                dirout, chan.ip[0].imageUrl, CRes, stackname, input_ts.z)
            mm = renderapi.image_pyramid.MipMap(imageUrl=chan_outImage)
            chan.ip = renderapi.image_pyramid.ImagePyramid()
            chan.ip[0] = mm

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
        corr_ts = corr_tilespecs[0]

        N, M, C = getImage(corr_ts)

        # construct a dictionary with the correction factors
        corr_dict = {}
        if corr_ts.channels is not None:
            for chan in corr_ts.channels:
                Nc, Mc, CC = getImage(corr_ts, chan.name)
                corr_dict[chan.name] = CC

        mypartial = partial(
            process_tile,
            C,
            self.args['output_directory'],
            self.args['output_stack'],
            self.args['clip'],
            self.args['scale_factor'],
            self.args['clip_min'],
            self.args['clip_max'],
            corr_dict=corr_dict)
        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            output_tilespecs = pool.map(mypartial, inp_tilespecs)

        # upload to render
        renderapi.stack.create_stack(
            self.args['output_stack'], cycleNumber=self.args['cycle_number'],
            cycleStepNumber=self.args['cycle_step_number'], render=self.render)

        if self.args['overwrite_zlayer']:
            try:
                renderapi.stack.delete_section(
                    self.args['output_stack'], self.zValues[0],
                    render=self.render)
            except renderapi.errors.RenderError as e:
                self.logger.error(e)

        renderapi.client.import_tilespecs_parallel(
            self.args['output_stack'], output_tilespecs,
            poolsize=self.args['pool_size'],
            render=self.render, close_stack=self.args['close_stack'])


if __name__ == "__main__":
    mod = MultIntensityCorr()
    mod.run()
