#!/usr/bin/env python

'''============================= import block =============================='''
import concurrent.futures
import copy
import numpy as np
import logging
import renderapi
import bigfeta.bigfeta
import bigfeta.utils
import bigfeta.solve
import collections
import argschema
from bigfeta.bigfeta import create_CSR_A_fromobjects as CSRA
from asap.module.render_module import RenderModuleException
from asap.rough_align.schemas import (FitMultipleSolvesSchema,
                                      FitMultipleSolvesOutputSchema)
# correct schema to use

if __name__ == "__main__" and __package__ is None:
    __package__ = "asap.rough_align.fit_multiple_solves"

# in the following example, just the keywords are important.
# everything else is most likely customizable unless stated otherwise.

example_render = {
    "owner": "TEM",  # use your custom owner name
    "project": "MN12_L2_1A",  # use your own project name
    "port": 8888,  # use your own port number
    "host": "http://em-131db2.corp.alleninstitute.org",
    # use your own render server
    "client_scripts": ("/allen/aibs/pipeline/image_processing/"
                       "volume_assembly/render-jars/production/scripts"
                       ),
    # use your own client-scripts
    "memGB": "2G"  # customizable, and optional.
    # Can be changed/added later in the code if necessary.
}
example = {
    "input_stack": dict(example_render, **{
        "name": "MN12_L2_1A_montscape_reord",  # use your own name
        "collection_type": "stack",
        "db_interface": "render"
    }),
    # remapped, downsampled montage scapes to rough align
    "pointmatch_collection": dict(example_render, **{
        "name": "MN12_L2_1A_rough_matches",  # use your own name
        "collection_type": "pointmatch",
        "db_interface": "render"
    }),  # pointmatched collection run on the input stack
    "rigid_output_stack": dict(example_render, **{
        "name": "MN12_L2_1A_rigid_rot_test",  # use your own name
        "collection_type": "stack",
        "db_interface": "render"
    }),  # output of rigid rotation
    "translation_output_stack": None,  # if using this, follow similar schema.
    # It is the output of rigid translation
    "affine_output_stack": dict(example_render, **{
        "name": "MN12_L2_1A_affine_test",  # use your own name
        "collection_type": "stack",
        "db_interface": "render"
    }),  # output of affine transform
    "thin_plate_output_stack": dict(example_render, **{
        "name": "Mn12_L2_1A_tps_test",  # use your own name
        "collection_type": "stack",
        "db_interface": "render"
    }),  # output of thin plate spline transform
    "minZ": 0,  # first remapped Z value as an integer
    "maxZ": 801,  # last remapped Z value as an integer
    "pool_size": 20,  # customizable. 20 is probably overkill.
    # Will be used in any inherent concurrency in the module.
    "close_stack": False,  # Must remain False to keep the stack open-
    # -so new ROI can be added.
    "output_json": "/path/to/output/json/files"  # required for proper-
    # -functioning of the module.
}

logger = logging.getLogger()


class ApplyMultipleSolvesException(RenderModuleException):

    """Raise exception by using try except blocks...."""


class TileException(RenderModuleException):
    """Raise this when unmatched tile ids exist or
    if multiple sections per z value exist"""


def create_resolved_tiles(render, pm_render, input_stack: str,
                          pm_collection: str, solve_range: tuple,
                          pool_size: int
                          ):
    # input_stack and pm_collection are names of the
    # (a) montage-scaped & Z-mapped stack, and
    # (b) pointmatch collection from render, respectively;
    # solve_range is a tuple of the minimum and maximum of the new_z values.
    # pool_size is the concurrency from  module input
    stack_zs = [z for z in renderapi.stack.get_z_values_for_stack(input_stack,
                render=render) if solve_range[0] <= z <= solve_range[-1]]
    num_threads = pool_size  # customizable
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as e:
        rtfut_to_z = {
            e.submit(renderapi.resolvedtiles.get_resolved_tiles_from_z,
                     input_stack, z, render=render): z for z in stack_zs
        }
        z_to_rts = {
            rtfut_to_z[fut]:
            fut.result() for fut in concurrent.futures.as_completed(rtfut_to_z)
        }

    matchgroups = {
        ts.layout.sectionId for ts in (i for l in (
            rts.tilespecs for rts in z_to_rts.values())
            for i in l)
    }
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as e:
        futs = [e.submit(renderapi.pointmatch.get_matches_with_group,
                pm_collection, g, render=pm_render) for g in matchgroups]
        allmatches = [i for l in (
            fut.result() for fut in concurrent.futures.as_completed(futs)
        ) for i in l]

    match_pIds, match_qIds = map(set,
                                 zip(*[(m["pId"], m["qId"]) for m in allmatches
                                       ]))
    match_tileIds = match_pIds | match_qIds
    all_tileIds = {ts.tileId for ts in (i for l in (
        rts.tilespecs for rts in z_to_rts.values()
    ) for i in l)}

    tIds_nomatch = all_tileIds - match_tileIds  # any tiles without matches
    
    return {'resolved_tiles': z_to_rts, 'matched_tiles': match_tileIds,
            'All_matches': allmatches, 'All_tiles': all_tileIds,
            'Unmatched_tiles': tIds_nomatch
            }


def nomatchz_counter(combined_rts, tIds_nomatch):
    nomatchz_count = collections.Counter(
        [combined_rts[tId].z for tId in tIds_nomatch]
    )  # should be nothing in it if everything works well
    if len(nomatchz_count) > 0:
        word = sorted({tId: combined_rts[tId].z for tId in tIds_nomatch})
        raise TileException(
            f'Unmatched TileIds Exist: {list(map(int, word))}')
    return None


def multiz_counter(combined_rts):
    multiz_count = {
        k: v for k, v in collections.Counter(
            [ts.z for ts in combined_rts.tilespecs]
        ).items() if v > 1
    }
    # should be nothing in it if everything works well
    if len(multiz_count) > 0:
        keys = list(multiz_count.keys())
        raise TileException(f'multiple sections in {keys}')
    return None


def get_ts_timestamp(ts):
    imgurl = ts.ip[0].imageUrl
    return imgurl.split("_")[-4]


def create_input_defaults(render, pm_render, input_stack: str,
                          pm_collection: str, solve_range: tuple,
                          pool_size: int, multiz=False):
    
    combine_resolvedtiles = renderapi.resolvedtiles.combine_resolvedtiles
    
    res_tiles = create_resolved_tiles(render, pm_render,
                                      input_stack=input_stack,
                                      pm_collection=pm_collection,
                                      solve_range=solve_range,
                                      pool_size=pool_size)
    
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
    rmt = res_tiles['matched_tiles']
    combined_rts.tilespecs = [
        tId_to_tilespecs[tId] for tId in tId_to_tilespecs.keys() & rmt
    ]
    nomatchz_counter(combined_rts, res_tiles['Unmatched_tiles'])
    if multiz:
        multiz_counter(combined_rts)
    return {'combined_tilespecs': combined_rts, 'new_matches': new_matches}


def rigid_solve(combined_rts, new_matches):
    rigid_transform_name = "RotationModel"
    rigid_order = 2
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
    rig_matches = renderapi.pointmatch.copy_matches_explicit(new_matches)
    rigid_create_CSR_A_input = (combined_rts, rig_matches,
                                rigid_transform_name,
                                rigid_transform_apply,
                                rigid_regularization_dict,
                                rigid_matrix_assembly_dict, rigid_order,
                                rigid_fullsize)
    return rigid_create_CSR_A_input


def translation_solve(rigid_result_rts, new_matches):
    translation_transform_name = "TranslationModel"
    translation_order = 2
    translation_fullsize = False
    translation_transform_apply = []
    translation_regularization_dict = {
        "translation_factor": 1e0,
        "default_lambda": 1e-5,
        "freeze_first_tile": False,
        "thinplate_factor": 5e7
    }
    translation_matrix_assembly_dict = {
        "choose_random": True,
        "depth": [1, 2, 3, 4],
        "npts_max": 500,
        "inverse_dz": True,
        "npts_min": 5,
        "cross_pt_weight": 0.5,
        "montage_pt_weight": 1.0
    }
    trans_matches = renderapi.pointmatch.copy_matches_explicit(new_matches)
    translation_create_CSR_A_input = (
        rigid_result_rts, trans_matches, translation_transform_name,
        translation_transform_apply, translation_regularization_dict,
        translation_matrix_assembly_dict,
        translation_order, translation_fullsize)
    
    return translation_create_CSR_A_input


def affine_solve(rigid_result_rts, new_matches):
    aff_transform_name = "AffineModel"
    aff_order = 2
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
    aff_matches = renderapi.pointmatch.copy_matches_explicit(new_matches)
    aff_create_CSR_A_input = (
        rigid_result_rts, aff_matches, aff_transform_name, aff_transform_apply,
        aff_regularization_dict, aff_matrix_assembly_dict, aff_order,
        aff_fullsize)
    return aff_create_CSR_A_input


def baseline_vertices(xmin, xmax, ymin, ymax, nx, ny):
    xt, yt = np.meshgrid(
        np.linspace(xmin, xmax, nx),
        np.linspace(ymin, ymax, ny)
    )
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


def thin_plate_spline_solve(aff_result_rts, new_matches):
    
    tpsadded_aff_result_rts = copy.deepcopy(aff_result_rts)
    for tspec in tpsadded_aff_result_rts.tilespecs:
        append_tps_tform(tspec, npts=5)
    
    tps_transform_name = "ThinPlateSplineTransform"
    tps_order = 2
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

    tps_matches = renderapi.pointmatch.copy_matches_explicit(new_matches)
    tps_create_CRS_A_input = (
        tpsadded_aff_result_rts, tps_matches, tps_transform_name,
        tps_transform_apply, tps_regularization_dict, tps_matrix_assembly_dict,
        tps_order, tps_fullsize)
    return tps_create_CRS_A_input


class FitMultipleSolves(argschema.ArgSchemaParser):
    default_schema = FitMultipleSolvesSchema
    default_output_schema = FitMultipleSolvesOutputSchema

    def apply_transform(self, new_matches, rts, app):
        app_solver = {'rigid': rigid_solve,
                      'translate': translation_solve,
                      'affine': affine_solve,
                      'tps': thin_plate_spline_solve}
        app_input = app_solver[app](rts, new_matches)
        app_fr, app_draft_resolvedtiles = CSRA(*app_input,
                                               return_draft_resolvedtiles=True)
        app_result_rts = copy.deepcopy(app_draft_resolvedtiles)
        app_sol = bigfeta.solve.solve(app_fr["A"], app_fr["weights"],
                                      app_fr["reg"], app_fr["x"], app_fr["rhs"]
                                      )
        bigfeta.utils.update_tilespecs(app_result_rts, app_sol["x"])
        return app_result_rts

    @staticmethod
    def save_transform(render, rts, outstack):
        renderapi.stack.create_stack(outstack, render=render)
        renderapi.resolvedtiles.put_tilespecs(outstack, rts, render=render)
        
    def run(self):
        r_in = renderapi.connect(**self.args['input_stack'])
        name_in = self.args['input_stack']['name'][0]

        r_pm = renderapi.connect(**self.args['pointmatch_collection'])
        name_pm = self.args['pointmatch_collection']['name'][0]

        r_rot = renderapi.connect(**self.args['rigid_output_stack'])
        name_rot = self.args["rigid_output_stack"]["name"][0]

        r_aff = renderapi.connect(**self.args['affine_output_stack'])
        name_aff = self.args["affine_output_stack"]["name"][0]

        r_tps = renderapi.connect(**self.args['thin_plate_output_stack'])
        name_tps = self.args["thin_plate_output_stack"]["name"][0]

        if self.args['translation_output_stack'] is not None:
            r_trans = renderapi.connect(**self.args['translation_output_stack'])
            name_trans = self.args["translation_output_stack"]["name"][0]
            do_translate = True
        else:
            do_translate = False

        allZ = [int(z) for z in renderapi.stack.get_z_values_for_stack(
            name_in, render=r_in)]
        
        minZ = (allZ[0] if self.args["minZ"] is None else max(self.args["minZ"],
                allZ[0]))
       
        maxZ = (allZ[-1] if self.args["maxZ"] is None else min(self.args["maxZ"],
                allZ[-1]))

        sol_range = (minZ, maxZ)

        in_default = create_input_defaults(
            render=r_in, pm_render=r_pm,
            input_stack=name_in,
            pm_collection=name_pm,
            solve_range=sol_range, pool_size=self.args['pool_size'],
            multiz=False
        )

        '''---------------------Rigid solve-------------------------'''
        rigid_result_rts = self.apply_transform(
            new_matches=in_default['new_matches'],
            rts=in_default['combined_tilespecs'], app='rigid')
        self.save_transform(r_rot, rigid_result_rts, name_rot)
        if do_translate:
            '''---------------Translation solve -------'''
            
            trans_result_rts = self.apply_transform(
                new_matches=in_default['new_matches'],
                rts=rigid_result_rts, app='translate')
            
            self.save_transform(r_trans, trans_result_rts,
                                name_trans)
            
            '''---------------Affine solve ------------'''
            
            aff_result_rts = self.apply_transform(
                new_matches=in_default['new_matches'],
                rts=trans_result_rts, app='affine')
        else:
            '''---------------Affine solve ------------'''

            aff_result_rts = self.apply_transform(
                new_matches=in_default['new_matches'],
                rts=rigid_result_rts, app='affine')
        self.save_transform(r_aff, aff_result_rts, name_aff)
            
        '''---------------Thin_plate_spline solve--------------------'''
        tps_result_rts = self.apply_transform(
            new_matches=in_default['new_matches'],
            rts=aff_result_rts, app='tps')
        self.save_transform(r_tps, tps_result_rts, name_tps)
        
        allZ_out = [
            int(z) for z in renderapi.stack.get_z_values_for_stack(
                name_rot, render=r_rot)
        ]

        out_dict = {
            'zs': allZ_out,
            'rigid_output_stack': self.args['rigid_output_stack'],
            'affine_output_stack': self.args['affine_output_stack'],
            'thin_plate_output_stack': self.args['thin_plate_output_stack']
        }

        if do_translate:
            out_dict['translation_output_stack'] = self.args[
                "translation_output_stack"]
        
        self.output(out_dict)


if __name__ == "__main__":
    mod = FitMultipleSolves()
    # Use input_data = example as an argument here for test runs.
    mod.run()
