import renderapi
import os
import json
import tempfile
import numpy as np
from functools import partial
from rendermodules.module.render_module import RenderModule, RenderModuleException
from rendermodules.dataimport.schemas import CloneStackWithNoMipmapsParameters, CloneStackWithNoMipmapsOutput



example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "russelt",
        "project": "Reflections",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "input_stack": "Secs_1015_1099_5_reflections_mml6_montage_1015",
    "output_stack": "Secs_1015_1099_5_reflections_module_test",
    "level_to_retain":1,
    "pool_size":20
}


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


class CloneStackWithNoMipmaps(RenderModule):
    default_schema = CloneStackWithNoMipmapsParameters
    default_output_schema = CloneStackWithNoMipmapsOutput

    def run(self):
        self.logger.debug('Clone stack with no mipmaps module')

        zvalues = self.render.run(renderapi.stack.get_z_values_for_stack,
                                  self.args['input_stack'])

        mypartial = partial(create_tilespecs,
                            self.render,
                            self.args['input_stack'],
                            self.args['level_to_retain'])

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            jsonfiles = pool.map(mypartial, zvalues)

        # create stack - overwrites existing one
        self.render.run(renderapi.stack.create_stack,
                    self.args['output_stack'])

        # set stack state to LOADING
        self.render.run(renderapi.stack.set_stack_state,
                    self.args['output_stack'],
                    state='LOADING')

        # import jsonfiles
        self.render.run(renderapi.client.import_jsonfiles_parallel,
                    self.args['output_stack'],
                    jsonfiles,
                    poolsize=self.args['pool_size'],
                    close_stack=True)

        self.output({'output_stack': self.args['output_stack']})


if __name__ == "__main__":
    mod = CloneStackWithNoMipmaps(input_data=example)
    mod.run()
