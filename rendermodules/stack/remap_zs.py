#!/usr/bin/env python
import renderapi

from rendermodules.module.render_module import (StackTransitionModule,
                                                RenderModuleException)
from rendermodules.stack.schemas import RemapZsParameters, RemapZsOutput


example_input = {
    "input_stack": "TEST_IMPORT_FROMMD",
    "output_stack": "TEST_remzs",
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
    "zValues": [0],
    "new_zValues": [10000],

}


class RemapZsModule(StackTransitionModule):
    default_schema = RemapZsParameters
    default_output_schema = RemapZsOutput

    @staticmethod
    def sectionId_from_z(z):
        return "{}.0".format(int(float(z)))

    def run(self):
        if len(self.zValues) != len(self.args['new_zValues']):
            raise RenderModuleException(
                "zValues with length {} cannot be mapped to "
                "zValues with length {}".format(
                    len(self.zValues), len(self.args['new_zValues'])))
        for z, newz in zip(self.zValues, self.args['new_zValues']):
            resolvedtiles = renderapi.resolvedtiles.get_resolved_tiles_from_z(
                self.input_stack, z, render=self.render)
            for ts in resolvedtiles.tilespecs:
                ts.z = newz
                if self.args.get('remap_sectionId'):
                    ts.layout.sectionId = self.sectionId_from_z(newz)
            self.output_tilespecs_to_stack(
                resolvedtiles.tilespecs,
                sharedTransforms=resolvedtiles.transforms,
                zValues=[z])
        self.output({
            "zValues": self.zValues,
            "output_stack": self.output_stack
        })


if __name__ == "__main__":
    mod = RemapZsModule(input_data=example_input)
    mod.run()
