#!/usr/bin/env python
import renderapi
from ..module.render_module import RenderModule
from rendermodules.dataimport.schemas import (
    AddMipMapsToStackParameters, AddMipMapsToStackOutput)

if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.dataimport.apply_mipmaps_to_render"

example = {
    "render": {
        "host": "em-131fs",
        "port": 8998,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "input_stack": "mm2_acquire_8bit",
    "output_stack": "mm2_mipmap_test",
    "mipmap_dir": "/net/aidc-isi1-prd/scratch/aibs/scratch",
    "imgformat": "tif",
    "levels": 6,
    "zstart": 1015,
    "zend": 1015
}

class AddMipMapsToStack(RenderModule):
    default_schema = AddMipMapsToStackParameters
    default_output_schema = AddMipMapsToStackOutput

    def run(self):
        self.logger.debug('Applying mipmaps to stack')

        # get the list of z indices
        zvalues = self.render.run(
            renderapi.stack.get_z_values_for_stack, self.args['input_stack'])

        try:
            self.args['zstart'] and self.args['zend']
            zvalues1 = range(self.args['zstart'], self.args['zend']+1)
            zvalues = list(set(zvalues1).intersection(set(zvalues))) # extract only those z's that exist in the input stack
        except NameError:
            try:
                self.args['z']
                if self.args['z'] in zvalues:
                    zvalues = [self.args['z']]
            except NameError:
                self.logger.error('No z value given for mipmap generation')

        if len(zvalues) == 0:
            self.logger.error('No sections found for stack {}'.format(
                self.args['input_stack']))

        # add the tile spec to render stack
        try:
            self.args['output_stack']
        except NameError:
            self.logger.error("Need an output stack name for adding mipmaps")

        output_stack = (self.args['input_stack'] if
                        self.args['output_stack'] is None
                        else self.args['output_stack'])

        if output_stack not in self.render.run(
                renderapi.render.get_stacks_by_owner_project):
            # stack does not exist
            self.render.run(renderapi.stack.create_stack,
                            output_stack)

        if output_stack != self.args['input_stack']:
            renderapi.stack.clone_stack(self.args['input_stack'],
                            output_stack, zs=zvalues, close_stack=False, render=self.render)
        
        md = renderapi.stack.get_stack_metadata(self.args['input_stack'], self.render)
        md.mipmapPathBuilder = {
            "rootPath": self.args['mipmap_dir'],
            "numberOfLevels": self.args['level'],
            "extension": self.args['imgformat']
            }
        renderapi.stack.set_stack_metadata(output_stack, md, self.render)
        self.render.run(renderapi.stack.set_stack_state,
                        output_stack, 'LOADING')
        self.output({"output_stack": output_stack})


if __name__ == "__main__":
    # mod = AddMipMapsToStack(input_data=example)
    mod = AddMipMapsToStack(schema_type=AddMipMapsToStackParameters)
    mod.run()
