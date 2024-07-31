#!/usr/bin/env python

'''============================== import block ==============================='''
import concurrent.futures
import copy
import os
import numpy as np
import logging
import renderapi
import scipy.sparse
import imageio
import bigfeta.bigfeta
import bigfeta.utils
import bigfeta.solve
import uri_handler.uri_functions
import collections
from asap.module.render_module import (RenderModule, RenderModuleException)
from asap.rough_align.schemas import (ApplyRoughAlignmentTransformParameters, ApplyRoughAlignmentOutputParameters) #correct schema to use

if __name__ == "__main__" and __package__ is None:
    __package__ = "asap.rough_align.fit_multiple_solves"

#in the following example, just the keywords are important. everything else is most likely customizable unless stated otherwise.
example = {
    "render": {
        "host": "http://em-131db2.corp.alleninstitute.org", #use your own render server
        "port": 8888, #use your own port
        "owner": "SidRath", #use your custom owner name
        "project": "asap_sing_demo", #use your own project name
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts", #use your own client-scripts
        "memGB": "2G" #customizable, and optional. Can be changed/added later in the code if necessary.
    },
    "montage_stack":"montage_scape_remappedz_stack", #Use your own
    "prealigned_stack": "montage_scape_remappedz_stack", #Use your own
    "lowres_stack": "montage_scape_remappedz_lowres_stack", #Use your own
    "pointmatch_collection":"pm_ra_collection", #Use your own, NEED TO ADD TO SCHEMA?
    "rigid_output_stack": "montage_scape_rigid_ra_stack", #customizable, NEED TO ADD TO SCHEMA?
    "affine_output_stack": "montage_scape_affine_ra_stack", #customizable, NEED TO ADD TO SCHEMA?
    "thin_plate_output_stack": "montage_scape_tps_ra_stack", #customizable, NEED TO ADD TO SCHEMA?
    "tilespec_directory": "/allen/programs/celltypes/workgroups/em-connectomics/sid/AWS_pipeline_project/scratch", #Use the directory where your tilesepcs are stored
    "map_z": "False",
    "new_z": [1, 2, 3], #use your own new_Z. must be a list of consecutive integers
    "remap_section_ids": "False",
    "consolidate_transforms": "True",
    "old_z": [1350, 1351, 1352], #use your own old_Z. must be a list of actual ROI Z values
    "scale": 0.1, #customizable. This will scale down the data to 10% of original size
    "apply_scale": "False", #customizable
    "pool_size": 20 #customizable. 20 is probably overkill.
} #example inout json not final

logger = logging.getLogger()

class ApplyMultipleSolvesException(RenderModuleException):
    """Raise exception by using try except blocks...."""
class TileException(RenderModuleException):
    """Raise this when unmatched tile ids exist or if multiple sections per z value exist"""

def create_resolved_tiles(render,input_stack: str,pm_collection: str,solve_range: tuple): #input_stack and pm_collection are names of the (a) montage-scaped & Z-mapped stack, and (b) pointmatch collection from render, respectively; solve_range is a tuple of the minimum and maximum of the new_z values.
    
    stack_zs = [z for z in renderapi.stack.get_z_values_for_stack(input_stack, render=render) if solve_range[0] <= z <= solve_range[-1]]
    
    num_threads = 35 #customizable
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as e:
        rtfut_to_z = {e.submit(renderapi.resolvedtiles.get_resolved_tiles_from_z, input_stack, z, render=render): z for z in stack_zs}
        z_to_rts = {rtfut_to_z[fut]: fut.result() for fut in concurrent.futures.as_completed(rtfut_to_z)}
    
    matchgroups = {ts.layout.sectionId for ts in (i for l in (rts.tilespecs for rts in z_to_rts.values()) for i in l)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as e:
        futs = [e.submit(renderapi.pointmatch.get_matches_with_group, pm_collection, g, render=r) for g in matchgroups]
        allmatches = [i for l in (fut.result() for fut in concurrent.futures.as_completed(futs)) for i in l]

    match_pIds, match_qIds = map(set, zip(*[(m["pId"], m["qId"]) for m in allmatches]))
    match_tileIds = match_pIds | match_qIds
    all_tileIds = {ts.tileId for ts in (i for l in (rts.tilespecs for rts in z_to_rts.values()) for i in l)}

    tIds_nomatch = all_tileIds - match_tileIds  # any tiles without matches
    
    return {'resolved_tiles': z_to_rts,'matched_tiles': match_tileIds,'All_matches': allmatches,'All_tiles': all_tileIds,'Unmatched_tiles': tIds_nomatch}

def multiz_unmatchz_counter(z_to_rts,combined_rts,tIds_nomatch):
    multiz_count = {k: v for k, v in collections.Counter([ts.z for ts in combined_rts.tilespecs]).items() if v > 1}#should be nothing in it if everything works well
    if len(multiz_count) > 0:
        raise TileException(f'multiple sections in {z}, tileIds: {rts.tilespecs[0].tileId}')
    #for z, rts in z_to_rts.items():
    #    if len(rts.tilespecs) > 1:
    #        print('fixing multiple section issues')
    #        rts.tilespecs = [sorted(rts.tilespecs, key=lambda x: x.ip[0].imageUrl)[-1]]
    #multiz_count = {k: v for k, v in collections.Counter([ts.z for ts in combined_rts.tilespecs]).items() if v > 1}#should be nothing in it if everything works well
    #if len(multiz_count) > 0:
    #    raise TileException(f'multiple sections in {z}, tileIds: {rts.tilespecs[0].tileId}')

    nomatchz_count = collections.Counter([tId_to_tilespecs[tId].z for tId in tIds_nomatch]) #should be nothing in it if everything works well
    if len(nomatchz_count) > 0:
        print(list(map(int, sorted({tId_to_tilespecs[tId].z for tId in tIds_nomatch}))))
    #    for z in sorted({tId_to_tilespecs[tId].z for tId in tIds_nomatch}):
    #        print(int(z))
        raise TileException('Unmatched TileIds Exist')
    else:
        print('no multiple z values found')
    return None

def get_ts_timestamp(ts):
    imgurl = ts.ip[0].imageUrl
    return imgurl.split("_")[-4]


def create_input_defaults(render,input_stack: str,pm_collection: str,solve_range: tuple):
    combine_resolvedtiles = renderapi.resolvedtiles.combine_resolvedtiles
    res_tiles = create_resolved_tiles(render=render,input_stack=input_stack,pm_collection=pm_collection,solve_range=solve_range)
    combined_rts = combine_resolvedtiles(res_tiles['resolved_tiles'].values())
    tId_to_tilespecs = {ts.tileId: ts for ts in combined_rts.tilespecs}
    swap_matchpair = renderapi.pointmatch.swap_matchpair
    new_matches = []
    for m in res_tiles['All_matches']:
        try:
            pz, qz = tId_to_tilespecs[m["pId"]].z, tId_to_tilespecs[m["qId"]].z
        except KeyError:
            continue
        if pz < qz:
            new_matches.append(m)
        else:
            new_matches.append(swap_matchpair(m))
    combined_rts.tilespecs = [tId_to_tilespecs[tId] for tId in tId_to_tilespecs.keys() & res_tiles['matched_tiles']]
    copy_matches = renderapi.pointmatch.copy_matches_explicit

    return {'combined_tilespecs': combined_rts,'new_matches': new_matches,'copied_matches': copy_matches}

def rigid_solve(combined_rts,new_matches):
    rigid_transform_name = "RotationModel"
    rigid_order = 2
    rigid_pair_depth = [1, 2, 3, 4, 5, 6]
    rigid_fullsize = False
    rigid_transform_apply = []
    rigid_regularization_dict = {
        "translation_factor": 1e-10,
        "default_lambda": 1e-12,
        "freeze_first_tile": False,
        "thinplate_factor": 5e7
    }
    rigid_matrix_assembly_dict = {
        "choose_random": True,
        "depth": [1, 2, 3, 4, 5, 6],
        "npts_max": 500,
        "inverse_dz": True,
        "npts_min": 5,
        "cross_pt_weight": 0.5,
        "montage_pt_weight": 1.0
    }
    rigid_create_CSR_A_input = (combined_rts, new_matches, rigid_transform_name,
    rigid_transform_apply, rigid_regularization_dict, rigid_matrix_assembly_dict, rigid_order, rigid_fullsize)
    return rigid_create_CSR_A_input,rigid_regularization_dict

def affine_solve(rigid_result_rts,new_matches):
    aff_transform_name = "AffineModel"
    aff_order = 2
    aff_pair_depth = [1, 2, 3, 4, 5, 6]
    aff_fullsize = False
    aff_transform_apply = []
    aff_regularization_dict = {
        "translation_factor": 1e-10,
        "default_lambda": 1e7,
        "freeze_first_tile": False,
        "thinplate_factor": 5e7
    }
    aff_matrix_assembly_dict = {
        "choose_random": True,
        "depth": [1, 2, 3, 4, 5, 6],
        "npts_max": 500,
        "inverse_dz": True,
        "npts_min": 5,
        "cross_pt_weight": 0.5,
        "montage_pt_weight": 1.0
    }

    aff_create_CSR_A_input = (
        rigid_result_rts, new_matches, aff_transform_name, aff_transform_apply,
        aff_regularization_dict, aff_matrix_assembly_dict, aff_order, aff_fullsize)
    return aff_create_CSR_A_input,aff_regularization_dict

def baseline_vertices(xmin, xmax, ymin, ymax, nx, ny):
    xt, yt = np.meshgrid(
            np.linspace(xmin, xmax, nx),
            np.linspace(ymin, ymax, ny))
    return np.vstack((xt.flatten(), yt.flatten())).transpose()


def tps_from_vertices(vertices):
    tf = renderapi.transform.ThinPlateSplineTransform()
    tf.ndims = 2
    tf.nLm = vertices.shape[0]
    tf.aMtx = np.array([[0.0, 0.0], [0.0, 0.0]])
    tf.bVec = np.array([0.0, 0.0])
    tf.srcPts = vertices.transpose()
    tf.dMtxDat = np.zeros_like(tf.srcPts)
    return tf


def append_tps_tform(tspec, npts=5, ext=0.05):
    bb = tspec.bbox_transformed()
    xmin, ymin = bb.min(axis=0)
    xmax, ymax = bb.max(axis=0)
    w, h = bb.ptp(axis=0)
    vert = baseline_vertices(
        xmin - ext * w,
        xmax + ext * w,
        ymin - ext * h,
        ymax + ext * h,
        npts, npts
    )
    tform = tps_from_vertices(vert)
    tspec.tforms.append(tform)

def thin_plate_spine_solve(aff_result_rts,new_matches):
    
    tpsadded_aff_result_rts = copy.deepcopy(aff_result_rts)
    for tspec in tpsadded_aff_result_rts.tilespecs:
        append_tps_tform(tspec, npts=5)
    
    tps_transform_name = "ThinPlateSplineTransform"
    tps_order = 2
    tps_pair_depth = 4
    tps_fullsize = False
    tps_transform_apply = [0]
    tps_regularization_dict = {
        "translation_factor": 1e-10,
        "default_lambda": 1e7,
        "freeze_first_tile": False,
        "thinplate_factor": 5e7
    }
    tps_matrix_assembly_dict = {
        "choose_random": True,
        "depth": 3,
        "npts_max": 500,
        "inverse_dz": True,
        "npts_min": 5,
        "cross_pt_weight": 0.5,
        "montage_pt_weight": 1.0
    }

    tps_matches = copy_matches(new_matches)  # any transform_apply modifies matches.... bummer.

    tps_create_CRS_A_input = (
        tpsadded_aff_result_rts, tps_matches, tps_transform_name,
        tps_transform_apply, tps_regularization_dict, tps_matrix_assembly_dict, tps_order, tps_fullsize)
    return tps_create_CRS_A_input,tps_regularization_dict


class FitMultipleSolves(RenderModule):
    default_schema = ApplyRoughAlignmentTransformParameters
    default_output_schema = ApplyRoughAlignmentOutputParameters
    
    def run(self):
        r = self.render #probably incorrect or unnecessary? need Russel's input.
        allzvalues = np.array(self.render.run(renderapi.stack.get_z_values_for_stack,self.args['prealigned_stack']))
        Z = [{'o':a,'n':b} for a,b in zip(self.args['old_z'],self.args['new_z']) if a in allzvalues]
        sol_range = (Z[0]['n'],Z[-1]['n'])
        in_default = create_input_defaults(render=r,input_stack=self.args['prealigned_stack'],pm_collection=self.args['pointmatch_collection'],solve_range=sol_range)

        '''---------------------starting rigid solve-------------------------'''
        rigid_input,rigid_reg_dict = rigid_solve(in_default['combined_tilespecs'],in_default['new_matches'])
        rigid_fr, rigid_draft_resolvedtiles = bigfeta.bigfeta.create_CSR_A_fromobjects(*rigid_input, return_draft_resolvedtiles=True)
        rigid_result_rts = copy.deepcopy(rigid_draft_resolvedtiles)
        rigid_reg = scipy.sparse.diags(
            [numpy.concatenate([ts.tforms[-1].regularization(rigid_reg_dict) for ts in rigid_draft_resolvedtiles.tilespecs])],
            [0], format="csr")
        rigid_sol = bigfeta.solve.solve(rigid_fr["A"], rigid_fr["weights"], rigid_reg, rigid_fr["x"], rigid_fr["rhs"])
        bigfeta.utils.update_tilespecs(rigid_result_rts, rigid_sol["x"])

        '''---------------------saving rigid solve results-------------------'''
        rig_outstack = self.args['rigid_output_stack']
        if rig_outstack not in self.render.run(renderapi.render.get_stacks_by_owner_project):
            self.render.run(renderapi.stack.create_stack,rig_outstack)
            self.render.run(renderapi.resolvedtiles.put_tilespecs,rig_outstack, rigid_result_rts))
        else:
            self.render.run(renderapi.stack.set_stack_state,rig_outstack,'LOADING')

        '''---------------------starting affine solve-------------------------'''
        aff_input,aff_reg_dict = affine_solve(rigid_result_rts,in_default['new_matches'])
        aff_fr, aff_draft_resolvedtiles = bigfeta.bigfeta.create_CSR_A_fromobjects(*aff_input, return_draft_resolvedtiles=True)
        aff_result_rts = copy.deepcopy(aff_draft_resolvedtiles)
        aff_reg = scipy.sparse.diags(
            [numpy.concatenate([ts.tforms[-1].regularization(aff_reg_dict) for ts in aff_draft_resolvedtiles.tilespecs])],
            [0], format="csr")
        aff_sol = bigfeta.solve.solve(aff_fr["A"], aff_fr["weights"], aff_reg, aff_fr["x"], aff_fr["rhs"])
        bigfeta.utils.update_tilespecs(aff_result_rts, aff_sol["x"])
        
        '''---------------------saving affine solve results-------------------'''
        aff_outstack = self.args['affine_output_stack']
        if aff_outstack not in self.render.run(renderapi.render.get_stacks_by_owner_project):
            self.render.run(renderapi.stack.create_stack,aff_outstack)
            self.render.run(renderapi.resolvedtiles.put_tilespecs,aff_outstack, aff_result_rts)
        else:
            self.render.run(renderapi.stack.set_stack_state,aff_outstack,'LOADING')

        '''---------------starting thin_plate_spline solve--------------------'''
        tps_input,tps_reg_dict = thin_plate_spine_solve(aff_result_rts,in_default['new_matches'])
        tps_fr, tps_draft_resolvedtiles = bigfeta.bigfeta.create_CSR_A_fromobjects(*tps_input, return_draft_resolvedtiles=True)
        tps_result_rts = copy.deepcopy(tps_draft_resolvedtiles)
        tps_reg = scipy.sparse.diags(
            [numpy.concatenate([ts.tforms[-1].regularization(tps_reg_dict) for ts in tps_draft_resolvedtiles.tilespecs])],
            [0], format="csr")
        tps_sol = bigfeta.solve.solve(tps_fr["A"], tps_fr["weights"], tps_reg, tps_fr["x"], tps_fr["rhs"])
        bigfeta.utils.update_tilespecs(tps_result_rts, tps_sol["x"])

        '''------------saving thin_plate_spline solve results----------------'''
        tps_outstack = self.args['thin_plate_output_stack']
        if tps_outstack not in self.render.run(renderapi.render.get_stacks_by_owner_project):
            self.render.run(renderapi.stack.create_stack,tps_outstack)
            self.render.run(renderapi.resolvedtiles.put_tilespecs,tps_outstack, tps_result_rts)
        else:
            self.render.run(renderapi.stack.set_stack_state,tps_outstack,'LOADING')

        self.output({
            'zs': np.array([Z[i]['n'] for i in range(len(Z))]),
            'rigid_output_stack': rig_outstack,
            'affine_output_stack': aff_outstack,
            'thin_plate_output_stack':tps_outstack})


if __name__ == "__main__":
        mod = FitMultipleSolves()
        mod.run()