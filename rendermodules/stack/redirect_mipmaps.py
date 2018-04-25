#!/usr/bin/env python
"""
change storage directory of imageUrl in a given mipMapLevel
"""
import copy
import os
import pathlib

import renderapi

from rendermodules.module.render_module import StackTransitionModule
from rendermodules.stack.schemas import (RedirectMipMapsParameters,
                                         RedirectMipMapsOutput)

example_input = {
    "input_stack": "TEST_IMPORT_FROMMD",
    "output_stack": "TEST_redmml",
    "pool_size": 10,
    "render": {
        "host": "em-131fs",
        "port": 8080,
        "owner": "russelt",
        "project": "RENDERAPI_TEST",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts/"
    },
    "close_stack": False,
    "overwrite_zlayer": True,
    "z": 1,
    "new_mipmap_directories": [{
        "level": 0,
        "directory": "/allen/programs/celltypes/production/"
        }]
}


class RedirectMipMapsModule(StackTransitionModule):
    default_schema = RedirectMipMapsParameters
    default_output_schema = RedirectMipMapsOutput

    @staticmethod
    def get_replacement_mmL(mmL, d):
        return renderapi.image_pyramid.MipMapLevel(
            mmL.level,
            pathlib.Path(os.path.join(
                d, os.path.basename(mmL.imageUrl))).as_uri(),
            mmL.maskUrl)

    def run(self):
        mmL_d_map = {i['level']: i['directory']
                     for i in
                     self.args['new_mipmap_directories']}
        zs = self.get_overlapping_inputstack_zvalues()
        for z in zs:
            tspecs = renderapi.tilespec.get_tile_specs_from_z(
                self.input_stack, z, render=self.render)

            new_tspecs = []
            for ts in tspecs:
                ts_new = copy.copy(ts)
                ts_new.ip.mipMapLevels = [
                    (mmL if (mmL.level not in mmL_d_map)
                     else self.get_replacement_mmL(mmL, mmL_d_map[mmL.level]))
                    for mmL in ts_new.ip.mipMapLevels]
                new_tspecs.append(ts_new)

            self.output_tilespecs_to_stack(new_tspecs, zValues=[z])

        self.output({
            "zValues": zs,
            "output_stack": self.output_stack
            })



if __name__ == "__main__":
    mod = RedirectMipMapsModule(input_data=example_input)
    mod.run()
