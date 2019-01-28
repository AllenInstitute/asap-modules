import renderapi
import numpy as np
from rendermodules.module.render_module import (
        StackInputModule)
from rendermodules.rough_align.schemas import (
        RoughSlicerSchema)
from functools import partial
import json
import time
import tifffile
import os


example = {
        "render": {
            "host": "em-131fs",
            "port": 8987,
            "owner": "TEM",
            "project": "17797_1R",
            "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts"
          },
        "input_stack": "20190123_manual_reg_ds",
        "bounds_from_stack": None,
        "minZ": 14500,
        "maxZ": 15800,
        "pool_size": 7,
        "output_dir": "/allen/programs/celltypes/workgroups/em-connectomics/danielk/pre_align_rigid/slices",
        "output_json": "test_output.json",
        "x_slice_locs": [0.4, 0.5, 0.6],
        "y_slice_locs": [0.4, 0.5, 0.6],
        "slice_locs_as_pixels": False
        }


def create_empty_images(bounds, xlocs, ylocs, zValues):
    results = []
    nz = zValues.ptp() + 1
    nx = int(bounds['maxX'] - bounds['minX'] + 1)
    ny = int(bounds['maxY'] - bounds['minY'] + 1)
    for xl in xlocs:
        result = {}
        result['slice'] = 'x'
        result['val'] = xl
        result['minZ'] = zValues.min()
        result['maxZ'] = zValues.max()
        result['image'] = np.zeros((nz, ny)).astype('uint8')
        results.append(result)
    for yl in ylocs:
        result = {}
        result['slice'] = 'y'
        result['val'] = yl
        result['minZ'] = zValues.min()
        result['maxZ'] = zValues.max()
        result['image'] = np.zeros((nz, nx)).astype('uint8')
        results.append(result)
    return results

def zjob(fargs):
    [z, input_stack, render, bounds] = fargs
    tilespec = renderapi.tilespec.get_tile_specs_from_z(
            input_stack,
            z,
            render=render)
    if len(tilespec) != 1:
        return None
    tilespec = tilespec[0]
    im = renderapi.client.render_tilespec(
            tilespec,
            x=bounds['minX'],
            y=bounds['minY'],
            width=int(bounds['maxX'] - bounds['minX'] + 1),
            height=int(bounds['maxY'] - bounds['minY'] + 1),
            render=render)
    return z, im[:, :, 0]


class RoughSlicer(StackInputModule):
    default_schema = RoughSlicerSchema

    def run(self):
        self.render = renderapi.connect(**self.args['render'])

        bstack = self.args['input_stack']
        if self.args['bounds_from_stack'] is not None:
            bstack = self.args['bounds_from_stack']
        bounds = renderapi.stack.get_stack_bounds(
                bstack,
                render=self.render)

        if not self.args['slice_locs_as_pixels']:
            xlocs = np.uint(np.array(self.args['x_slice_locs']) * \
                    (bounds['maxX'] - bounds['minX']) + \
                    bounds['minX'])
            ylocs = np.uint(np.array(self.args['y_slice_locs']) * \
                    (bounds['maxY'] - bounds['minY']) + \
                    bounds['minY'])
        else:
            xlocs = np.uint(self.args['x_slice_locs'])
            ylocs = np.uint(self.args['y_slice_locs'])

        self.images = create_empty_images(
                bounds,
                xlocs,
                ylocs,
                np.array(self.args['zValues']))

        zs = self.get_overlapping_inputstack_zvalues()

        fargs = []
        for z in zs:
            fargs.append([z, self.args['input_stack'], self.render, bounds])

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            for z, im in pool.map(zjob, fargs):
                t0 = time.time()
                zind = self.args['zValues'].index(z)
                self.slice_image(im, zind)
                del im

        for im in self.images:
            fname = self.args['input_stack'] + \
                    '_%s' % im['slice'] + \
                    '_%d' % im['val'] + \
                    '_zs%d_ze%d' % (self.args['minZ'], self.args['maxZ']) + \
                    '.tiff'
            outname = os.path.join(
                    self.args['output_dir'],
                    fname)
            tifffile.imsave(outname, im['image'])


    def slice_image(self, im, zind):
        for myslice in self.images:
            if myslice['slice'] == 'x':
                myslice['image'][zind, :] = im[:, myslice['val']]
            elif myslice['slice'] == 'y':
                myslice['image'][zind, :] = im[myslice['val'], :]


if __name__ == '__main__':
    rmod = RoughSlicer(input_data=example)
    rmod.run()
