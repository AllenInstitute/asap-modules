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
        return renderapi.image_pyramid.MipMap(
            pathlib.Path(os.path.join(
                d, os.path.basename(mmL.imageUrl))).as_uri(),
            mmL.maskUrl)

    def run(self):
        mmL_d_map = {i['level']: i['directory']
                     for i in
                     self.args['new_mipmap_directories']}
        zs = self.get_overlapping_inputstack_zvalues()
        for z in zs:
            resolvedtiles = renderapi.resolvedtiles.get_resolved_tiles_from_z(
                self.input_stack, z, render=self.render)
            tspecs = resolvedtiles.tilespecs
            tforms = resolvedtiles.transforms

            new_tspecs = []
            for ts in tspecs:
                ts_new = copy.copy(ts)
                for lvl, mm in ts_new.ip.iteritems():
                    ts_new[lvl] = (mm if (lvl not in mmL_d_map)
                                   else self.get_replacement_mmL(mm,
                                                                 mmL_d_map[lvl]))
                new_tspecs.append(ts_new)

            self.output_tilespecs_to_stack(
                new_tspecs, sharedTransforms=tforms, zValues=[z])

        self.output({
            "zValues": zs,
            "output_stack": self.output_stack
            })



if __name__ == "__main__":
    mod = RedirectMipMapsModule(input_data=example_input)
    mod.run()
