import concurrent.futures
import copy
import itertools

import numpy
import renderapi
import scipy.sparse

import bigfeta.bigfeta
from bigfeta import utils

import matplotlib.pyplot as plt
import collections
import time


def groupId_from_tilespec(ts):
    return ts.layout.sectionId

def mad(data, axis=None, side=None):
    '''Median Absolute Distance function with left and right side option.'''
    def get_sided(d, side, axis=None):
        # FIXME uses masked arrays for convenience, not for speed.
        if side == "l":
            m = d <= numpy.median(d, axis=axis)
        elif side == "r":
            m = d >= numpy.median(d, axis=axis)
        elif side is None:
            return d
        else:
            raise ValueError("ERROR: please enter 'l', 'r', or None")
        return numpy.ma.masked_array(d, m)
    d = get_sided(data, side, axis)
    res = numpy.ma.median(numpy.absolute(d - numpy.ma.median(d, axis)), axis)
    return (res.data if isinstance(res, numpy.ma.masked_array) else res)

# TODO is mad robust enough to ignore outliers?
def get_scale_statistics_mad(scales):
    rel_scales = scales[numpy.all(numpy.abs(scales.mean(axis=0) - scales) < scales.std(axis=0) * 3, axis=1)]
    return mad(rel_scales, axis=0)

SolveStats = collections.namedtuple("SolveStats", [
    "scale_mean", "scale_median", "scale_mins",
    "scale_maxs", "scale_stdevs", "scale_mads",
    "err_means", "err_stds", "error"])


def solve_with_regd_for_stats(draft_resolvedtiles, fr, reg_d):
    l_output_rts = copy.deepcopy(draft_resolvedtiles)
    l_reg = scipy.sparse.diags(
        [numpy.concatenate(
            [ts.tforms[-1].regularization(reg_d) for ts in draft_resolvedtiles.tilespecs])],
            [0], format="csr")
    l_sol = bigfeta.solve.solve(fr["A"], fr["weights"], l_reg, fr["x"], fr["rhs"])

    bigfeta.utils.update_tilespecs(l_output_rts, l_sol["x"])
    
    scales = numpy.array([ts.tforms[-1].scale for ts in l_output_rts.tilespecs])
    mean = numpy.mean(scales, axis=0)
    median = numpy.median(scales, axis=0)
    mins = numpy.min(scales, axis=0)
    maxs = numpy.max(scales, axis=0)
    stdevs = numpy.std(scales, axis=0)
    mads = get_scale_statistics_mad(scales)
    
    err_means = [e[0] for e in l_sol["err"]]
    err_stds = [e[1] for e in l_sol["err"]]
    errors = numpy.array(l_sol["error"]) / len(l_output_rts.tilespecs)
    
    return SolveStats(
        mean, median, mins,
        maxs, stdevs, mads,
        err_means, err_stds, errors)

render_connect = {
   "owner": "TEM",
    "project": "H19_06_356_2_2_1",
    "port": 8888,
    "host": "em-131db2.corp.alleninstitute.org",
    "client_scripts": ""
}
r = renderapi.connect(**render_connect)

input_stack = "20200930_onscope_lcorrected"
pm_collection = "default_point_matches"

z = 20345

rts = renderapi.resolvedtiles.get_resolved_tiles_from_z(input_stack, z, render=r)

sectionset = {groupId_from_tilespec(ts) for ts in rts.tilespecs}
groupid = list(sectionset)[0]

matches = renderapi.pointmatch.get_matches_from_group_to_group(pm_collection, groupid, groupid, render=r)

match_pIds, match_qIds = map(set, zip(*[(m["pId"], m["qId"]) for m in matches]))
match_tileIds = match_pIds | match_qIds

tId_to_tilespecs = {ts.tileId: ts for ts in rts.tilespecs}

rts.tilespecs = [tId_to_tilespecs[tId] for tId in tId_to_tilespecs.keys() & match_tileIds]

# affine solve

transform_name = "affine"
order = 2
pair_depth = [0]
fullsize = False
transform_apply = []
regularization_dict = {
    "translation_factor": 1.833e-5,
    "default_lambda": 1000.0,
    # "thinplate_factor": 1e-05,
    # "poly_factors": None
}
matrix_assembly_dict = {
    "choose_random": False,
    "depth": [0],
    "npts_max": 500,
    "inverse_dz": True,
    "npts_min": 5,
    "cross_pt_weight": 0.5,
    "explicit_weight_by_depth": None,
    "montage_pt_weight": 1.0
}

create_CSR_A_input = (
    rts, matches, transform_name,
    transform_apply, regularization_dict, matrix_assembly_dict, order, fullsize
)

fr, draft_resolvedtiles = bigfeta.bigfeta.create_CSR_A_fromobjects(*create_CSR_A_input, return_draft_resolvedtiles=True)

lambda_list = numpy.logspace(-1, 8, num=15)
transfac_list = numpy.logspace(-7, -3, num=15)

tic = time.time()
with concurrent.futures.ProcessPoolExecutor(max_workers=10) as e:
    fut_to_tup = {}
    for l, tfac in itertools.product(lambda_list, transfac_list):
        reg_d = dict(regularization_dict, **{
            "default_lambda": l,
            "translation_factor": tfac
        })
        
        fut_to_tup[e.submit(solve_with_regd_for_stats, draft_resolvedtiles, fr, reg_d)] = (l, tfac)
    
    tup_to_stats = {fut_to_tup[fut]: fut.result() for fut in concurrent.futures.as_completed(fut_to_tup.keys())}
    
print(time.time() - tic)

mad_cutoffs = 0.003, 0.003

scalemin_cutoff = 0.9, 0.9

candidates = []

for (l, tfac), ss in tup_to_stats.items():
    if ss.scale_mads[0] <= mad_cutoffs[0] and ss.scale_mads[1] <= mad_cutoffs[1]:
        err_param = numpy.linalg.norm(ss.error / ss.scale_mean)
        scale_param = numpy.linalg.norm(ss.scale_mean)
        if 1.4 < scale_param:
            if scalemin_cutoff[0] < ss.scale_mins[0] and scalemin_cutoff[1] < ss.scale_mins[1]:
                candidates.append((l, tfac, ss))
print(len(candidates))

sorted_tups = [i[:-1] for i in sorted(candidates, key=lambda x: numpy.linalg.norm(x[-1].error / x[-1].scale_mean))]

print([t for t in sorterd_tups])