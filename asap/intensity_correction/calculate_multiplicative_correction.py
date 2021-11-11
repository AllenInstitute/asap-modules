#!/usr/bin/env python

from functools import partial
import os

import numpy as np
import renderapi
from scipy.ndimage.filters import gaussian_filter
import tifffile

from asap.intensity_correction.apply_multiplicative_correction import getImage
from asap.intensity_correction.schemas import MakeMedianParams
from asap.module.render_module import (
    RenderModule, RenderModuleException)

if __name__ == "__main__" and __package__ is None:
    __package__ = "asap.intensity_correction.calculate_multiplicative_correction"

example_input = {
    "render": {
        "host": "10.128.24.33",
        "port": 80,
        "owner": "multchan",
        "project": "M335503_Ai139_smallvol",
        "client_scripts": '/shared/render/render-ws-java-client/src/main/scripts'
    },
    "input_stack": "ACQ_Session1",
    "file_prefix": "Median",
    "output_stack": "TESTMedian_Session1",
    "output_directory": "/nas2/data/M335503_Ai139_smallvol/processed/TESTMedians",
    "minZ": 500,
    "maxZ": 524,
    "pool_size": 20,
    "close_stack": True
}


def getImageFromTilespecs(alltilespecs, index, channel=None):
    N, M, img = getImage(alltilespecs[index], channel)
    return img


def randomly_subsample_tilespecs(alltilespecs, numtiles):
    np.random.shuffle(alltilespecs)
    return alltilespecs[:numtiles]

# if multichannel stack
    # loop over each channel
    # calculate median image
    # construct a channel
    # make a tilespec for each z with each of these channels

# make a conventional median stack
    # calculate a median image
    # make a tilespec for each z with median image as default image pyramid


def make_median_image(alltilespecs, numtiles, outImage, pool_size,
                      chan=None, gauss_size=10):
    # read images and create stack
    N, M, img0 = getImage(alltilespecs[0], channel=chan)
    stack = np.zeros((N, M, numtiles), dtype=img0.dtype)
    mypartial = partial(getImageFromTilespecs, alltilespecs, channel=chan)
    indexes = range(0, numtiles)
    with renderapi.client.WithPool(pool_size) as pool:
        images = pool.map(mypartial, indexes)

    # calculate median
    for i in range(0, len(images)):
        stack[:, :, i] = images[i]
    np.median(stack, axis=2, overwrite_input=True)
    (A, B, C) = stack.shape
    if (numtiles % 2 == 0):
        med1 = stack[:, :, numtiles // 2 - 1]
        med2 = stack[:, :, numtiles // 2 + 1]
        med = (med1 + med2) // 2
    else:
        med = stack[:, :, (numtiles - 1) // 2]
    med = gaussian_filter(med, gauss_size)

    tifffile.imsave(outImage, med)


class MakeMedian(RenderModule):
    default_schema = MakeMedianParams

    def run(self):

        # inits
        alltilespecs = []
        numtiles = 0
        firstts = []
        outtilespecs = []
        ind = 0

        # get tilespecs for z

        for z in range(self.args['minZ'], self.args['maxZ'] + 1):
            tilespecs = self.render.run(
                renderapi.tilespec.get_tile_specs_from_z,
                self.args['input_stack'], z)
            alltilespecs.extend(tilespecs)
            # used for easy creation of tilespecs for output stack
            firstts.append(tilespecs[0])
            numtiles += len(tilespecs)
        # subsample in the case where the number of tiles is too large
        if self.args['num_images'] > 0:
            alltilespecs = randomly_subsample_tilespecs(
                alltilespecs, self.args['num_images'])

        stackInfo = renderapi.stack.get_full_stack_metadata(
            self.args['input_stack'], render=self.render)
        channel_names = stackInfo['stats'].get('channelNames', [])
        # Quick fix to have the empty channel logic work when channelNames=[]
        if len(channel_names) == 0:
            channel_names = [None]

        # figure out which of our channels is the default channel
        if channel_names[0] is not None:
            try:
                default_chan = next((
                    ch.name for ch in firstts[0].channels
                    if ch.ip[0].imageUrl == firstts[0].ip[0].imageUrl))
            except StopIteration:
                raise RenderModuleException(
                    "default channel doesn't match any channel")

        outdir = self.args['output_directory']
        if not os.path.exists(outdir):
            os.makedirs(outdir)
        out_images = []
        for chan_name in channel_names:
            chan_str = chan_name if chan_name is not None else ""
            outImage = outdir + \
                "/%s_%s_%s_%d-%d.tif" % (self.args['file_prefix'],
                                         self.args['output_stack'],
                                         chan_str,
                                         self.args['minZ'],
                                         self.args['maxZ'])
            make_median_image(alltilespecs,
                              numtiles,
                              outImage,
                              self.args['pool_size'],
                              chan=chan_name)
            out_images.append(outImage)

        for ind, z in enumerate(range(
                self.args['minZ'], self.args['maxZ'] + 1)):
            # want many variations on this tilespec so making a
            #   copy by serializing/deserializing
            ts = renderapi.tilespec.TileSpec(json=firstts[ind].to_dict())
            # want a different z for each one
            ts.z = z
            if channel_names[0] is None:
                mml_o = ts.ip[0]
                mml = renderapi.image_pyramid.MipMap(
                    imageUrl=out_images[0],
                    maskUrl=mml_o.maskUrl)
                ts.ip[0] = mml
            else:
                channels = []
                for chan_name, out_image in zip(channel_names, out_images):
                    chan_orig = next((
                        ch for ch in ts.channels if ch.name == chan_name))
                    mml = renderapi.image_pyramid.MipMap(
                        imageUrl=out_image)
                    ip = renderapi.image_pyramid.ImagePyramid()
                    ip[0] = mml
                    chan_orig.ip = ip
                    channels.append(chan_orig)
                # we want the default_chan median to be the
                #   default image pyramid
                ts.ip = next((
                    med_ch.ip for med_ch in channels
                    if med_ch.name == default_chan))
                ts.channels = channels
            outtilespecs.append(ts)

        # upload to render
        renderapi.stack.create_stack(
            self.args['output_stack'], cycleNumber=2, cycleStepNumber=1,
            render=self.render)
        renderapi.stack.set_stack_state(
            self.args['output_stack'], "LOADING", render=self.render)
        renderapi.client.import_tilespecs_parallel(
            self.args['output_stack'], outtilespecs,
            poolsize=self.args['pool_size'], render=self.render,
            close_stack=self.args['close_stack'])


if __name__ == "__main__":
    mod = MakeMedian()
    mod.run()
