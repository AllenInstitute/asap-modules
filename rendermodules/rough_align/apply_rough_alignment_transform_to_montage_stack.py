
import os
import json
import renderapi
import glob
import numpy as np
from argschema import InputFile, InputDir, OutputDir
import marshmallow as mm
from ..module.render_module import RenderModule, RenderParameters
from functools import partial

example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8998,
        "owner": "gayathri",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "montage_stack": "mm2_acquire_8bit_Montage",
    "prealigned_stack": "mm2_acquire_8bit_Montage",
    "lowres_stack": "mm2_montage_scape_test",
    "output_stack": "mm2_rough_aligned_test",
    "set_new_z": "False",
    "minZ": 1015,
    "maxZ": 1040,
    "scale": 0.01,
    "pool_size": 10
}


def apply_rough_alignment(render, input_stack, prealigned_stack, lowres_stack, scale, Z):
    z = Z[0]
    newz = Z[1]

    try:
        # get lowres stack tile specs
        lowres_ts = render.run(renderapi.tilespec.get_tile_specs_from_z, lowres_stack, newz)

        # get input stack tile specs (for the first tile)
        highres_ts = render.run(renderapi.tilespec.get_tile_specs_from_z, input_stack, z)[0]

        # get the section bounding box
        sectionbounds = render.run(renderapi.stack.get_bounds_from_z, prealigned_stack, z)

        # get the lowres stack rough alignment transformation
        tforms = lowres_ts[0].tforms

        d = tforms[0].to_dict()
        dsList = d['datastring'].split()




class ApplyRoughAlignmentTransformParameters(RenderParameters):
    montage_stack = mm.fields.Str(
        required=True,
        metadata={'description':'stack to make a downsample version of'})
    prealigned_stack = mm.fields.Str(
        required=False,default=montage_stack,
        metadata={'description':'stack with dropped tiles corrected for stitching errors'})
    lowres_stack = mm.fields.Str(
        required=True,
        metadata={'description':'montage scape stack with rough aligned transform'})
    output_stack = mm.fields.Str(
        required=True,
        metadata={'description':'output high resolution rough aligned stack'})
    set_new_z = mm.fields.Boolean(
        required=False,
        metadata={'description':'set to assign new z values starting from 0 (default - False)'})
    scale = mm.fields.Float(
        required=True,
        metadata={'description':'scale of montage scapes'})
    pool_size = mm.fields.Int(
        require=False,
        default=5,
        metadata={'description':'pool size for parallel processing'})
    minZ = mm.fields.Int(
        required=True,
        metadata={'description':'Minimum Z value'})
    maxZ = mm.fields.Int(
        required=True,
        metadata={'description':'Maximum Z value'})


class ApplyRoughAlignmentTransform(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = ApplyRoughAlignmentTransformParameters
        super(ApplyRoughAlignmentTransform, self).__init__(
            schema_type=schema_type, *args, **kwargs)


    def run(self):
        allzvalues = self.render.run(
            renderapi.stack.get_z_values_for_stack,
            self.args['input_stack'])
        allzvalues = np.array(allzvalues)
        zvalues = allzvalues[(allzvalues >= self.args['minZ']) & (allzvalues <= self.args['maxZ'])]

        if self.args['set_new_z']:
            newzvalues = range(0, len(zvalues))
        else:
            newzvalues = zvalues

        # the old and new z values are required for the AT team
        Z = [[a,b] for a,b in zip(zvalues, newzvalues)]

        mypartial = partial(
                        apply_rough_alignment,
                        self.render,
                        self.args['input_stack'],
                        self.args['prealigned_stack'],
                        self.args['lowres_stack'],
                        self.args['scale'])

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            jsonfiles = pool.map(mypartial, Z)

        # Create the output stack if it doesn't exist
        if self.args['output_stack'] not in self.render.run(renderapi.render.get_stacks_by_owner_project):
            # stack does not exist
            self.render.run(
                renderapi.stack.create_stack,
                self.args['output_stack'])

        # import tilespecs to render
        self.render.run(
            renderapi.client.import_jsonfiles_parallel,
            self.args['output_stack'],
            jsonfiles)

        # set stack state to complete
        self.render.run(
            renderapi.stack.set_stack_state,
            self.args['output_stack'],
            state='COMPLETE')


if __name__ == "__main__":
    mod = ApplyRoughAlignmentTransform(input_data=example)
    #mod = ApplyRoughAlignmentTransform(schema_type=ApplyRoughAlignmentTransformParameters)
    mod.run()
