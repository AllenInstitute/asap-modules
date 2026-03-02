#!/usr/bin/env python
import argschema
import dataclasses

import numpy
import renderapi
import scipy.sparse

import bigfeta.bigfeta
import bigfeta.solve
import bigfeta.utils

import asap.em_montage_qc.detect_montage_defects
from asap.solver.schemas import BigFetaOutputSchema

np = numpy

# input_example = {
#     'zValues': 1985,
#     'render': {
#         'memGB': '5G'
#         },
#     'transformation' : 'Polynomial2DTransform',
#     'order' : 2,
#     'fullsize' : False,
#     'regularization': {
#         'translation_factor' : 1,
#         'default_lambda' : 1,
#         'poly_factors' : [1.0e25, 1.0e25, 1]
#         },
#     'matrix_assembly': {
#             "npts_min": 5,  # minimum correspondences between tiles to consider
#             "npts_max": 500,  # maximum correspondences between tiles
#             "choose_random": True,  # do not randomly sample from correspondences when reducing to maximum points
#             "depth": [0],  # montage stitching considers intra-section matches
#             "montage_pt_weight": 1.0  # base weight for intra-section matches
#             }
#     'pointmatch': {
#         'name' : 'montage_pointmatch',
#         'render': {
#             'owner' :'TEM'
#             }
#         },
#     'input_affine_stack' : 'montage_aff_regsweep_results',
#     'output_poly_stack' : 'montage_poly_solved',
#     'output_fixedtiles_stack' : 'montage_fixedtiles_poly_solved'
#     }

@dataclasses.dataclass
class SolveResult:
    sol: dict
    rts: renderapi.resolvedtiles.ResolvedTiles


def tilespecs_regularization_from_reg_d(tilespecs, reg_d, tId_to_reg_d=None):
    tId_to_reg_d = tId_to_reg_d or {}
    return scipy.sparse.diags(
        [np.concatenate(
            [ts.tforms[-1].regularization(
                tId_to_reg_d.get(ts.tileId, reg_d))
             for ts in tilespecs])],
        [0], format="csr")


def get_area_distorted_tIds(rts, orig_rts, meshcellsize=512):
    polygons = asap.em_montage_qc.detect_montage_defects.polygons_from_rts(
        rts, meshcellsize=meshcellsize)
    orig_polygons = asap.em_montage_qc.detect_montage_defects.polygons_from_rts(
        orig_rts, meshcellsize=meshcellsize)

    tIds = numpy.array([ts.tileId for ts in rts.tilespecs])

    area_fractions = (
        numpy.array([p.area for p in polygons]) /
        numpy.array([p.area for p in orig_polygons])
    )

    include_thresh = 2 * numpy.std(area_fractions)
    center = numpy.mean(area_fractions)
    include_range = (center - include_thresh, center + include_thresh)

    outliers_mask = (area_fractions < include_range[0]) | (area_fractions > include_range[1])
    return tIds[outliers_mask].tolist()


def do_solve_fixed_tiles(rts, matches, transform_name,
                         matrix_assembly_dict, order, fullsize,
                         transform_apply=None, regularization_dict=None,
                         fixed_reg_d=None,
                         to_fix_method=get_area_distorted_tIds,
                         to_fix_kwargs=None):
    to_fix_kwargs = to_fix_kwargs or {}

    create_CSR_A_input = (
        rts, matches, transform_name,
        ([] if transform_apply is None else transform_apply),
        ({} if regularization_dict is None else regularization_dict),
        matrix_assembly_dict, order, fullsize)

    fr, draft_resolvedtiles = bigfeta.bigfeta.create_CSR_A_fromobjects(
        *create_CSR_A_input, return_draft_resolvedtiles=True)
    fixed_draft_resolvedtiles = bigfeta.utils.copy_resolvedtiles(draft_resolvedtiles)
    sol = bigfeta.solve.solve(
        fr["A"], fr["weights"], fr["reg"], fr["x"], fr["rhs"])
    bigfeta.utils.update_tilespecs(draft_resolvedtiles, sol["x"])

    tIds_to_fix = to_fix_method(draft_resolvedtiles, rts, **to_fix_kwargs)
    fixed_reg = tilespecs_regularization_from_reg_d(
        fixed_draft_resolvedtiles.tilespecs,
        ({} if regularization_dict is None else regularization_dict),
        {tId: fixed_reg_d for tId in tIds_to_fix}
    )

    fixed_sol = bigfeta.solve.solve(
        fr["A"], fr["weights"], fixed_reg, fr["x"], fr["rhs"])
    bigfeta.utils.update_tilespecs(fixed_draft_resolvedtiles, fixed_sol["x"])

    return (
        SolveResult(sol, draft_resolvedtiles),
        SolveResult(fixed_sol, fixed_draft_resolvedtiles)
    )


def polynomial_reg_d(reg_d: dict = None):
    # regularization dict with defined parameters.
    #   It can be necessary to sweep across these parameters to find an optimal
    #   configuration based on the montage and correspondence characteristics
    if reg_d is None:
        regularization_dict = {
            "translation_factor": 1,
            "default_lambda": 1,
            "poly_factors": [1e25, 1e25, 1]
        }
    else:
        regularization_dict = reg_d

    polysolve_regs = {
        'regularization_dict': regularization_dict,
        'fixed_regularization_dict': {
            **regularization_dict,
            **{"poly_factors": [1e25, 1e25, 1e25]}
        }
    }

    return polysolve_regs

class DualPolyDefaultOutputSchema(BigFetaOutputSchema):
    from argschema.fields import Nested, Str

    polynomial_stack = Str(
        required=True,
        description='first pass of polynomial solve montaging')
    fixedtiles_stack = Str(
        required=True,
        description='second pass of polynomial solve montaging with chosen fixed tiles')

class Dual_polysolve(argschema.ArgSchemaParser):
    default_output_schema = DualPolyDefaultOutputSchema

    def run(self):
        # connect to render servers
        rconn = self.args['render']
        r = renderapi.connect(**rconn)
        rconn_p = {**self.args['render'], **self.args['pointmatch']['render']}
        rp = renderapi.connect(**rconn_p)

        # initialize parameters
        transform_name = self.args['transformation']
        order = self.args['order']
        fullsize = self.args['fullsize']
        transform_apply = self.args['transform_apply']

        matrix_assembly_dict = self.args['matrix_assembly']

        regs = polynomial_reg_d(self.args['regularization'])
        regularization_dict = regs['regularization_dict']
        fixed_regularization_dict = regs['fixed_regularization_dict']

        aff_stack = self.args['input_affine_stack']
        std_stack = self.args['output_poly_stack']
        fixed_stack = self.args['output_fixedtiles_stack']
        z = self.args['zValues']

        # solve
        a_rts = renderapi.resolvedtiles.get_resolved_tiles_from_z(aff_stack, int(z), render=r)
        matches = renderapi.pointmatch.get_matches_within_group(
            self.args['pointmatch']['name'], a_rts.tilespecs[0].layout.sectionId, render=rp)
        sr, sr_fixed = do_solve_fixed_tiles(
            a_rts, matches, transform_name, matrix_assembly_dict, order, fullsize,
            transform_apply, regularization_dict, fixed_regularization_dict)
        renderapi.resolvedtiles.put_tilespecs(std_stack, resolved_tiles=sr.rts, render=r)
        renderapi.resolvedtiles.put_tilespecs(fixed_stack, resolved_tiles=sr_fixed.rts, render=r)

        self.output({"polynomial_stack": std_stack, "fixedtiles_stack": fixed_stack})


if __name__ == "__main__":
    module = Dual_polysolve()
    module.run()