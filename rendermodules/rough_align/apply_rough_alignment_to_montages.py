
import os
import json
import renderapi
import glob
import numpy as np
from ..module.render_module import RenderModule, RenderModuleException
from rendermodules.rough_align.schemas import ApplyRoughAlignmentTransformParameters, ApplyRoughAlignmentOutputParameters
from rendermodules.stack.consolidate_transforms import consolidate_transforms
from functools import partial
import logging
import requests

if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.rough_align.apply_rough_alignment_to_montages"

example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "Tests",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "montage_stack": "rough_test_montage_stack",
    "prealigned_stack": "rough_test_montage_stack",
    "lowres_stack": "rough_test_downsample_rough_stack",
    "output_stack": "rough_test_rough_stack",
    "tilespec_directory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch/rough/jsonFiles",
    "set_new_z": "False",
    "consolidate_trasnforms": "True",
    "minZ": 1020,
    "maxZ": 1022,
    "scale": 0.1,
    "pool_size": 20
}

'''
# Another way is to use ConsolidateTransforms module
def consolidate_transforms(tforms, verbose=False, makePolyDegree=0):
    # Adapted from consolidate_transforms module

    tform_total = AffineModel()
    start_index = 0
    total_affines = 0
    new_tform_list = []

    for i,tform in enumerate(tforms):
        #print tform.className
        if 'AffineModel2D' in tform.className:
            total_affines+=1
            tform_total = tform.concatenate(tform_total)
            #tform_total.M=tform.M.dot(tform_total.M)
        else:
            if total_affines>0:
                if makePolyDegree>0:
                    polyTform = Polynomial2DTransform()._fromAffine(tform_total)
                    polyTform=polyTform.asorder(makePolyDegree)
                    new_tform_list.append(polyTform)
                else:
                    new_tform_list.append(tform_total)
                tform_total = AffineModel()
                total_affines =0
            new_tform_list.append(tform)
    if total_affines>0:
        if makePolyDegree>0:
            polyTform = Polynomial2DTransform()._fromAffine(tform_total)
            polyTform=polyTform.asorder(makePolyDegree)
            new_tform_list.append(polyTform)
        else:
            new_tform_list.append(tform_total)

    return new_tform_list
'''
logger = logging.getLogger()

def apply_rough_alignment(render,
                          input_stack,
                          prealigned_stack,
                          lowres_stack,
                          output_stack,
                          output_dir,
                          scale,
                          Z,
                          consolidateTransforms=True):
    z = Z[0]
    newz = Z[1]
    session=requests.session()
    try:
        # get lowres stack tile specs
        logger.debug('getting tilespecs from {} z={}'.format(lowres_stack,z))
        lowres_ts = render.run(
                            renderapi.tilespec.get_tile_specs_from_z,
                            lowres_stack,
                            z,
                            session=session)
        
        # get the lowres stack rough alignment transformation
        tforms = lowres_ts[0].tforms
        tf = tforms[-1]
        tf.M[0:2,0:2]*=scale
        
        stackbounds = render.run(
                            renderapi.stack.get_bounds_from_z,
                            input_stack,
                            z,
                            session=session)
        prestackbounds = render.run(
                            renderapi.stack.get_bounds_from_z,
                            prealigned_stack,
                            z,
                            session=session)
        
        tx = 0
        ty = 0
        if input_stack == prealigned_stack:
            tx =  -int(stackbounds['minX']) #- int(prestackbounds['minX'])
            ty =  -int(stackbounds['minY']) #- int(prestackbounds['minY'])
        else:
            tx = int(stackbounds['minX']) - int(prestackbounds['minX'])
            ty = int(stackbounds['minY']) - int(prestackbounds['minY'])
        
        translation_tform = renderapi.transform.AffineModel(B0=tx,B1=ty)     

        ftform = [translation_tform] + tforms
        logger.debug('getting tilespecs from {} z={}'.format(lowres_stack,z))

        highres_ts1 = render.run(
                            renderapi.tilespec.get_tile_specs_from_z,
                            input_stack,
                            z,session=session)

        for t in highres_ts1:
            for f in ftform:
                t.tforms.append(f)
            if consolidateTransforms:
                newt = consolidate_transforms(t.tforms)
                t.tforms = newt
            t.z = newz
        
        renderapi.client.import_tilespecs(output_stack,highres_ts1,render=render)
        session.close()
        return None
    except Exception as e:
        return e



class ApplyRoughAlignmentTransform(RenderModule):
    default_schema = ApplyRoughAlignmentTransformParameters
    default_output_schema = ApplyRoughAlignmentOutputParameters
    def run(self):
        if self.args['minZ'] >= self.args['maxZ']:
            raise RenderModuleException("First section z cannot be greater or equal to last section z")
        
        allzvalues = self.render.run(renderapi.stack.get_z_values_for_stack,
                                     self.args['montage_stack'])
        allzvalues = np.array(allzvalues)

        self.args['minZ'] = min(allzvalues) if self.args['minZ'] > min(allzvalues) else self.args['minZ']
        self.args['maxZ'] = max(allzvalues) if self.args['maxZ'] > max(allzvalues) else self.args['maxZ']
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
                        self.args['montage_stack'],
                        self.args['prealigned_stack'],
                        self.args['lowres_stack'],
                        self.args['output_stack'],
                        self.args['tilespec_directory'],
                        self.args['scale'],
                        consolidateTransforms=self.args['consolidate_transforms'])

        # Create the output stack if it doesn't exist
        if self.args['output_stack'] not in self.render.run(renderapi.render.get_stacks_by_owner_project):
            # stack does not exist
            self.render.run(
                renderapi.stack.create_stack,
                self.args['output_stack'])
        else: 
            # stack exists and has to be set to LOADING state
            self.render.run(renderapi.stack.set_stack_state,
                            self.args['output_stack'],
                            'LOADING')

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            results=pool.map(mypartial, Z)

        #raise an exception if all the z values to apply alignment were not 
        if not all([r is None for r in results]):
            failed_zs = [(result,z) for result,z in zip(results,Z) if result is not None]
            raise RenderModuleException("Failed to rough align z values {}".format(failed_zs))

        # set stack state to complete
        self.render.run(
            renderapi.stack.set_stack_state,
            self.args['output_stack'],
            state='COMPLETE')

        self.output(
            {
            'zs':np.array(Z),
            'output_stack':self.args['output_stack']
            }
        )

if __name__ == "__main__":
    mod = ApplyRoughAlignmentTransform(input_data=example)
    mod.run()
