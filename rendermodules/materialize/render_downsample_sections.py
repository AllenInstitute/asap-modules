from functools import partial
import random
import time
import json
import numpy as np
import renderapi
import tempfile
from rendermodules.materialize.schemas import RenderSectionAtScaleParameters, RenderSectionAtScaleOutput
from ..module.render_module import RenderModule, RenderModuleException


example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "russelt",
        "project": "Reflections",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "input_stack": "Secs_1015_1099_5_reflections_mml6_montage",
    "image_directory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch",
    "imgformat":"png",
    "scale": 0.01,
    "minZ": 1015,
    "maxZ": 1016
}

example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "Tests",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "input_stack": "rough_test_montage_stack",
    "image_directory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch",
    "imgformat":"png",
    "scale": 0.1,
    "minZ": 1020,
    "maxZ": 1022
}

def check_stack_for_mipmaps(render, input_stack, zvalues):
    # this function checks for the mipmaplevels for the first section in the stack
    # Assumes that all the sections in the stack has mipmaps stored if the first section has mipmaps
    
    #z = random.choice(zvalues)
    z = zvalues [0]
    tilespecs = render.run(renderapi.tilespec.get_tile_specs_from_z,
                            input_stack,
                            z)
    for ts in tilespecs:
        m = ts.to_dict()
        m['mipmapLevels'] = dict(m['mipmapLevels'])
        if len(m['mipmapLevels'].keys()) > 1:
            return True

    return False

def create_tilespecs_without_mipmaps(render, montage_stack, level, z):
    ts = render.run(renderapi.tilespec.get_tile_specs_from_z, montage_stack, z)
    tilespecs = []
    for t in ts:
        m = t.to_dict()
        m['mipmapLevels'] = dict(m['mipmapLevels'])
        [m['mipmapLevels'].pop(k, 0) for k in m['mipmapLevels'].keys() if k != level]
        tilespecs.append(m)
    tempjson = tempfile.NamedTemporaryFile(suffix=".json", mode='w', delete=True)
    tempjson.close()
    with open(tempjson.name, 'w') as f:
        json.dump(tilespecs, f, indent=4)
        f.close()
    return tempjson.name


class RenderSectionAtScale(RenderModule):
    default_schema = RenderSectionAtScaleParameters
    default_output_schema = RenderSectionAtScaleOutput

    def run(self):

        zvalues1 = self.render.run(
            renderapi.stack.get_z_values_for_stack,
            self.args['input_stack'])

        if self.args['minZ'] == -1 or self.args['maxZ'] == -1:
            self.args['minZ'] = min(zvalues1)
            self.args['maxZ'] = max(zvalues1)
        elif self.args['minZ'] > self.args['maxZ']:
            raise RenderModuleException('Invalid Z range: {} > {}'.format(self.args['minZ'], self.args['maxZ']))
        
        zvalues1 = np.array(zvalues1)
        zrange = range(int(self.args['minZ']), int(self.args['maxZ'])+1)
        zvalues = list(set(zvalues1).intersection(set(zrange)))

        if not zvalues:
            raise RenderModuleException('No valid zvalues found in stack for given range {} - {}'.format(self.args['minZ'], self.args['maxZ']))

        self.args['temp_stack'] = self.args['input_stack']

        #intz = [int(z) for z in zvalues]

        stack_has_mipmaps = check_stack_for_mipmaps(self.render, self.args['input_stack'], zvalues)

        # check if there are mipmaps in this stack
        if stack_has_mipmaps:
            print("stack has mipmaps")
            # clone the input stack to a temporary one with level 1 mipmap alone
            temp_no_mipmap_stack = "{}_no_mml_t{}".format(self.args['input_stack'], time.strftime("%m%d%y_%H%M%S"))

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
            # this also sets the stack's state to COMPLETE
            self.render.run(renderapi.client.import_jsonfiles_parallel,
                        self.args['temp_stack'],
                        jsonfiles,
                        poolsize=self.args['pool_size'],
                        close_stack=True)


        self.render.run(renderapi.client.renderSectionClient,
                        self.args['temp_stack'],
                        self.args['image_directory'],
                        zvalues,
                        scale=self.args['scale'],
                        format=self.args['imgformat'],
                        doFilter=self.args['doFilter'],
                        fillWithNoise=self.args['fillWithNoise'])
        self.output({"image_directory": self.args['image_directory'],
                     "temp_stack": self.args['temp_stack']})

if __name__ == "__main__":
    mod = RenderSectionAtScale(input_data=example)
    mod.run()
