import os
import renderapi
from ..module.render_module import RenderModule
from functools import partial
import glob
import random
import time
import numpy as np
from rendermodules.materialize.schemas import RenderSectionAtScaleParameters, RenderSectionAtScaleOutput
from rendermodules.dataimport.clone_stack_with_no_mipmaps import create_tilespecs_without_mipmaps


if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.materialize.render_downsample_sections"


example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "russelt",
        "project": "Reflections",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "input_stack": "Secs_1015_1099_5_reflections_mml6_montage_1015",
    "image_directory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch",
    "imgformat":"png",
    "scale": 0.01,
    "minZ": 1148,
    "maxZ": 1148
}

def check_stack_for_mipmaps(render, input_stack, zvalues):
    # this function checks for the mipmaplevels for the first section in the stack
    # Assumes that all the sections in the stack has mipmaps stored if the first section has mipmaps
    # Instead of reading all the tilespecs randomly pick a z and read its tilespecs for mipmap levels

    #zvalues = render.run(renderapi.stack.get_z_values_for_stack,
    #                        input_stack)

    z = random.choice(zvalues)
    tilespecs = render.run(renderapi.tilespec.get_tile_specs_from_z,
                            input_stack,
                            z)
    for ts in tilespecs:
        m = ts.to_dict()
        m['mipmapLevels'] = dict(m['mipmapLevels'])
        if len(m['mipmapLevels'].keys()) > 1:
            return True

    return False



class RenderSectionAtScale(RenderModule):
    #def __init__(self, schema_type=None, *args, **kwargs):
    #    if schema_type is None:
    #        schema_type = RenderSectionAtScaleParameters
    #    super(RenderSectionAtScale, self).__init__(
    #        schema_type=schema_type, *args, **kwargs)
    default_schema = RenderSectionAtScaleParameters
    default_output_schema = RenderSectionAtScaleOutput

    def run(self):

        zvalues = self.render.run(
            renderapi.stack.get_z_values_for_stack,
            self.args['input_stack'])

        if self.args['minZ'] == -1 or self.args['maxZ'] == -1:
            self.args['minZ'] = min(zvalues)
            self.args['maxZ'] = max(zvalues)
        elif self.args['minZ'] > self.args['maxZ']:
            self.logger.error('Invalid Z range: {} > {}'.format(self.args['minZ'], self.args['maxZ']))
        else:
            zvalues = np.array(zvalues)
            zvalues = list(zvalues[(zvalues >= self.args['minZ']) & (zvalues <= self.args['maxZ'])])

        if len(zvalues) == 0:
            self.logger.error('No valid zvalues found in stack for given range {} - {}'.format(self.args['minZ'], self.args['maxZ']))

        self.args['temp_stack'] = self.args['input_stack']

        #intz = [int(z) for z in zvalues]

        # check if there are mipmaps in this stack
        if check_stack_for_mipmaps(self.render, self.args['input_stack'], zvalues):
            # clone the input stack to a temporary one with level 1 mipmap alone
            temp_no_mipmap_stack = "{}_no_mml_t{}".format(self.args['input_stack'],
                                           time.strftime("%m%d%y_%H%M%S"))

            # set level of mipmap to retain as 1 (level 1)
            level = 1
            mypartial = partial(create_tilespecs_without_mipmaps,
                                self.render,
                                self.args['input_stack'],
                                level)

            with renderapi.client.WithPool(self.args['pool_size']) as pool:
                jsonfiles = pool.map(mypartial, zvalues)

            # set temp_stack as temp_no_mipmap_stack
            self.args['temp_stack'] = temp_no_mipmap_stack

            # create stack - overwrites existing one
            self.render.run(renderapi.stack.create_stack,
                        self.args['temp_stack'])

            # set stack state to LOADING
            self.render.run(renderapi.stack.set_stack_state,
                        self.args['temp_stack'],
                        state='LOADING')

            # import json files into temp_no_mipmap_stack
            self.render.run(renderapi.client.import_jsonfiles_parallel,
                        self.args['temp_stack'],
                        jsonfiles,
                        poolsize=self.args['pool_size'],
                        close_stack=True)


        self.render.run(renderapi.client.renderSectionClient,
                        self.args['temp_stack'],
                        self.args['image_directory'],
                        zvalues,
                        scale=str(self.args['scale']),
                        format=self.args['imgformat'],
                        doFilter=self.args['doFilter'],
                        fillWithNoise=self.args['fillWithNoise'])
        self.output({"image_directory": self.args['image_directory'],
                     "temp_stack": self.args['temp_stack']})

if __name__ == "__main__":
    mod = RenderSectionAtScale(input_data=example)
    mod.run()
