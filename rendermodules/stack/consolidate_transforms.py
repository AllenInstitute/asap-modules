import numpy as np
from renderapi.transform import AffineModel, Polynomial2DTransform
from functools import partial
import os
import renderapi
from rendermodules.module.render_module import RenderModule, RenderParameters
from argschema.fields import InputFile, InputDir, Str, Int, Slice, Float
import marshmallow as mm

example_json = {
    "render": {
        "host": "http://ibs-forrestc-ux1",
        "port": 80,
        "owner": "Forrest",
        "project": "M247514_Rorb_1",
        "client_scripts": "/pipeline/render/render-ws-java-client/src/main/scripts"
    },
    "stack": "ROUGHALIGN_LENS_DAPI_1_deconvnew",
    "output_stack" : "ROUGHALIGN_LENS_DAPI_1_deconvnew_CONS",
    "transforms_slice" : ":",
    "pool_size": 10,
}

class ConsolidateTransformsParameters(RenderParameters):
    stack = Str(required=True,
                description='stack to consolidate')
    postfix = Str(required=False, default="_CONS",
                  description='postfix to add to stack name on saving if no output defined (default _CONS)')
    transforms_slice = Slice(required=True,
                             description="a string representing a slice describing \
                             the set of transforms to be consolidated (i.e. 1:)")
    output_stack = Str(required=False,
                       description='name of output stack (default to adding postfix to input)')
    pool_size = Int(required=False, default=10,
                    description='name of output stack (default to adding postfix to input)')
    minZ = Float(required=False,
                 description="""minimum z to consolidate in read in from stack and write to output_stack\
                 default to minimum z in stack""")
    maxZ = Float(required=False,
                 description="""minimaximummum z to consolidate in read in from stack and write to output_stack\
                 default to maximum z in stack""")

class ConsolidateTransformsOutputParameters(mm.Schema):
    output_stack = Str(required=True,description = "name of output stack")
    numZ = Int(required=True,description="Number of z values processed")
    
def consolidate_transforms(tforms, logger, makePolyDegree=0):
    tform_total = AffineModel()
    start_index = 0
    total_affines = 0
    new_tform_list = []

    for i, tform in enumerate(tforms):
        if 'AffineModel2D' in tform.className:
            total_affines += 1
            tform_total = tform.concatenate(tform_total)
            # tform_total.M=tform.M.dot(tform_total.M)
        else:
            logger.debug('consolidate_transforms: non affine {}'.format(tform))
            if total_affines > 0:
                if makePolyDegree > 0:
                    polyTform = Polynomial2DTransform().fromAffine(tform_total)
                    polyTform = polyTform.asorder(makePolyDegree)
                    new_tform_list.append(polyTform)
                else:
                    new_tform_list.append(tform_total)
                tform_total = AffineModel()
                total_affines = 0
            new_tform_list.append(tform)
    if total_affines > 0:
        if makePolyDegree > 0:
            polyTform = Polynomial2DTransform().fromAffine(tform_total)
            polyTform = polyTform.asorder(makePolyDegree)
            new_tform_list.append(polyTform)
        else:
            new_tform_list.append(tform_total)
    return new_tform_list
    

def process_z(render, logger, stack, outstack, transform_slice,z):
    tilespecs = renderapi.tilespec.get_tile_specs_from_z(
        stack, z, render=render)
    for ts in tilespecs:
        logger.debug('process_z_make_json: tileId {}'.format(ts.tileId))
        ts.tforms[transform_slice] = consolidate_transforms(ts.tforms[transform_slice], logger)
        logger.debug('consolatedate tformlist {}'.format(ts.tforms[0]))

    logger.debug("tileid:{} transforms:{}".format(
        tilespecs[0].tileId, tilespecs[0].tforms))
    json_filepath=renderapi.utils.renderdump_temp(tilespecs)
    return json_filepath


class ConsolidateTransforms(RenderModule):
    default_schema = ConsolidateTransformsParameters
    default_output_schema = ConsolidateTransformsOutputParameters
    def run(self):
        stack = self.args['stack']
        outstack = self.args.get('output_stack', None)
        if outstack is None:
            outstack = stack + self.args['postfix']

        #get z values in z value range specified or dynamically
        #choose
        zvalues = np.array(self.render.run(
            renderapi.stack.get_z_values_for_stack, stack))
        minZ = self.args.get('minZ',np.min(zvalues))
        maxZ = self.args.get('maxZ',np.max(zvalues))
        zvalues = zvalues[zvalues>=minZ]
        zvalues = zvalues[zvalues<=maxZ]

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            json_files = pool.map(partial(
                                  process_z,
                                  self.render,
                                  stack,
                                  outstack,
                                  self.logger,
                                  self.args['transforms_slice']), zvalues)

        self.render.run(renderapi.stack.create_stack, outstack)
        self.render.run(
            renderapi.client.import_jsonfiles_parallel, outstack, json_files)

        output_d = {
            "output_stack":outstack,
            "numZ":len(zvalues)
        }
        self.output(output_d)


if __name__ == "__main__":
    mod = ConsolidateTransforms(input_data = example_json)
    mod.run()