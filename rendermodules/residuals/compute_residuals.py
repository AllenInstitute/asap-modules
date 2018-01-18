import os
import sys
import numpy as np
import time
import renderapi
import json
import itertools as it
from functools import partial
import pathos.multiprocessing as mp


def compute_residuals_within_group(render, stack, matchCollectionOwner, matchCollection, z, min_points=1):
    #print(z)
    # get the sectionID which is the group ID in point match collection
    groupId = render.run(renderapi.stack.get_sectionId_for_z, stack, z)

    # get matches within the group for this section
    allmatches = render.run(
                    renderapi.pointmatch.get_matches_within_group,
                    matchCollection,
                    groupId,
                    owner=matchCollectionOwner)

    # get the tilespecs to extract the transformations
    tilespecs = render.run(renderapi.tilespec.get_tile_specs_from_z, stack, z)
    tforms = {ts.tileId:ts.tforms for ts in tilespecs}

    transformed_pts = np.zeros((1,2))
    tile_residuals = {key: np.empty((0,1)) for key in tforms.keys()}
    tile_rmse = {key: np.empty((0,1)) for key in tforms.keys()}
    pt_match_positions = {key: np.empty((0,2)) for key in tforms.keys()}

    statistics = {}
    for i, match in enumerate(allmatches):
        pts_p = np.array(match['matches']['p'])
        pts_q = np.array(match['matches']['q'])

        if pts_p.shape[1] < min_points:
            continue

        #print(match['pId'], match['qId'])
        if ((match['pId'] in tforms.keys()) and (match['qId'] in tforms.keys())):
            t_p = (tforms[match['pId']])[-1].tform(pts_p.T)
            t_q = (tforms[match['qId']])[-1].tform(pts_q.T)

            # find the mean spatial location of the point matches
            # needed for seam detection
            positions = [[(a[0]+b[0])/2, (a[1]+b[1])/2] for a,b in zip(t_p, t_q)]

            # tile based residual
            all_pts = np.concatenate([t_p, t_q], axis=1)

            # sqrt of residuals (this divided by len(all_pts) before sqrt will give RMSE)
            res = np.sqrt(np.sum(np.power(all_pts[:,0:2]-all_pts[:,2:4],2),axis=1))
            rmse = np.sqrt((np.sum(np.power(all_pts[:,0:2]-all_pts[:,2:4],2),axis=1))/len(all_pts))

            tile_residuals[match['pId']] = np.append(tile_residuals[match['pId']], res)
            tile_rmse[match['pId']] = np.append(tile_rmse[match['pId']], rmse)
            pt_match_positions[match['pId']] = np.append(pt_match_positions[match['pId']], positions, axis=0)

    # remove empty entries from these dicts
    empty_keys = [k for k in tile_residuals if tile_residuals[k].size == 0]
    for k in empty_keys:
        tile_residuals.pop(k)
        tile_rmse.pop(k)
        pt_match_positions.pop(k)
    

    statistics['tile_rmse'] = tile_rmse
    statistics['z'] = z
    statistics['tile_residuals'] = tile_residuals
    statistics['pt_match_positions'] = pt_match_positions
    return statistics


def compute_residuals_from_group_to_group(render, stack, matchCollectionOwner, matchCollection, Z, min_points=10):
    zp = Z[0]
    zq = Z[1]

    # get section ids for zp and zq
    pgroupId = render.run(renderapi.stack.get_sectionId_for_z, stack, zp)
    qgroupId = render.run(renderapi.stack.get_sectionId_for_z, stack, zq)

    allmatches = render.run(
                    renderapi.pointmatch.get_matches_from_group_to_group,
                    matchCollection,
                    pgroupId,
                    qgroupId,
                    owner=matchCollectionOwner)

    # tile specs are needed to extract the transformations
    tilespecs_p = render.run(renderapi.tilespec.get_tile_specs_from_z, stack, zp)
    tforms_p = {ts.tileId:ts.tforms for ts in tilespecs_p}

    # get tile ids for each z
    # avoid reading the same tilespecs if zp == zq
    tilespecs_q = []
    tile_ids_q = []
    tforms_q = []
    tile_ids_p = get_tile_ids(tilespecs_p)
    if zp == zq:
        tile_ids_q = tile_ids_p
        tilespecs_q = tilespecs_p
        tforms_q = tforms_p
    else:
        tilespecs_q = render.run(renderapi.tilespec.get_tile_specs_from_z, stack, zq)
        tforms_q = {ts.tileId:ts.tforms for ts in tilespecs_q}
        tile_ids_q = get_tile_ids(tilespecs_q)

    # filter and compute transformed points
    transformed_pts_p = np.zeros((1,2))
    transformed_pts_q = np.zeros((1,2))

    # initialize tile based residuals
    tile_residuals_p = {key: np.empty((0,1)) for key in tile_ids_p}
    tile_residuals_q = {key: np.empty((0,1)) for key in tile_ids_q}

    for i, match in enumerate(allmatches):
        pts_p = np.array(match['matches']['p'])
        pts_q = np.array(match['matches']['q'])

        if pts_p.shape[1] < min_points:
            continue

        if match['pId'] in tforms_p.keys() and match['qId'] in tforms_q.keys():
            t_p = (tforms_p[match['pId']])[-1].tform(pts_p.T)
            t_q = (tforms_q[match['qId']])[-1].tform(pts_q.T)

            # tile based residual
            all_pts = np.concatenate([t_p[1:,:], t_q[1:,:]], axis=1)

            # sqrt of residuals (this divided by len(all_pts) before sqrt will give RMSE)
            res = np.sqrt(np.sum(np.power(all_pts[:,0:2]-all_pts[:,2:4],2),axis=1))

            tile_residuals_p[match['pId']] = np.append(tile_residuals_p[match['pId']], res)
            tile_residuals_q[match['qId']] = np.append(tile_residuals_q[match['qId']], res)

    data = {}
    data['zp'] = zp
    data['zq'] = zq
    data['pGroupId'] = pGroupId
    data['qgroupId'] = qgroupId
    data['tile_residuals_p'] = tile_residuals_p
    data['tile_residuals_q'] = tile_residuals_q
    return data

def compute_min_max_tile_residuals(residuals):
    tile_max = {}
    tile_min = {}

    maxes = [np.nanmax(v) for v in residuals.values() if len(v) > 0]
    maximum = np.max(maxes)

    for key in residuals:
        if len(residuals[key]) == 0:
            tile_max[key] = maximum
            tile_min[key] = maximum
        else:
            tile_max[key] = np.nanmax(residuals[key])
            tile_min[key] = np.nanmin(residuals[key])
    return tile_min, tile_max


def compute_max_tile_residuals(residuals):
    tile_max = {}

    maxes = [np.nanmax(v) for v in residuals.values() if len(v) > 0]
    maximum = np.max(maxes)

    for key in residuals:
        if len(residuals[key]) == 0:
            tile_max[key] = maximum
        else:
            tile_max[key] = np.nanmax(residuals[key])
    return tile_max


def compute_min_tile_residuals(residuals):
    tile_min = {}

    maxes = [np.nanmax(v) for v in residuals.values() if len(v) > 0]
    maximum = np.max(maxes)

    for key in residuals:
        if len(residuals[key]) == 0:
            tile_min[key] = maximum
        else:
            tile_min[key] = np.nanmin(residuals[key])
    return tile_min


def compute_mean_tile_residuals(residuals):
    tile_mean = {}
    unconnected_tile_ids = []

    # loop over each tile and compute the mean residual for each tile
    # iteritems is specific to py2.7
    #print(residuals)
    maxes = [np.nanmean(v) for v in residuals.values() if len(v) > 0]
    #print(maxes)
    maximum = np.max(maxes)

    for key in residuals:
        if len(residuals[key]) == 0:
            #tile_mean[key] = np.nan
            tile_mean[key] = maximum
            unconnected_tile_ids.append(key)
        else:
            tile_mean[key] = np.nanmean(residuals[key])

    return tile_mean, unconnected_tile_ids


def compute_montage_statistics(render, stack, matchCollectionOwner, matchCollection, zstart=None, zend=None, cutoff=3, normalizer=1, pool_size=10):

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, stack)
    if zstart is None:
        zstart = min(zvalues)
    elif zstart < min(zvalues):
        zstart = min([zstart, min(zvalues)])

    if zend is None:
        zend = max(zvalues)
    elif zend > max(zvalues):
        zend = min([zend, max(zvalues)])

    stats = {}
    for z in range(zstart, zend+1):
        zz = z - zstart
        stats[zz] = {}
        stats[zz]['z'] = []
        stats[zz]['tile_residuals'] = []
        stats[zz]['group_mean'] = []
        stats[zz]['group_median'] = []
        stats[zz]['group_variance'] = []
        stats[zz]['outlier_counts'] = []
        stats[zz]['outlier_percent'] = []
        stats[zz]['unconnected_count'] = []
        stats[zz]['tile_residual_mean'] = []
        stats[zz]['unconnected_tile_ids'] = []
        stats[zz]['pt_match_positions'] = []

    opts = {'normalizer':normalizer, 'method': 'std', 'cutoff':cutoff, 'greater_than':True}

    mypartial = partial(compute_residuals_within_group, render, stack, matchCollectionOwner, matchCollection)
    zvalues = range(zstart, zend+1)


    with mp.ProcessingPool(pool_size) as pool:
        statistics = pool.map(mypartial, zvalues)

    for s in statistics:
        #print(s)
        zz = s['z'] - zstart
        stats[zz]['tile_residuals'] = s['tile_residuals']
        stats[zz]['pt_match_positions'] = s['pt_match_positions']
        stats[zz]['tile_rmse'] = s['tile_rmse']
        stats[zz]['tile_rmse_mean'], stats[zz]['unconnected_tile_ids'] = compute_mean_tile_residuals(s['tile_rmse'])
        stats[zz]['z'] = s['z']
        stats[zz]['tile_residual_mean'], stats[zz]['unconnected_tile_ids'] = compute_mean_tile_residuals(s['tile_residuals'])
        stats[zz]['tile_residual_min'], stats[zz]['tile_residual_max'] = compute_min_max_tile_residuals(s['tile_residuals'])
        #stats[zz]['tile_residual_max'] = compute_max_tile_residuals(s['tile_residuals'])
        #stats[zz]['tile_residual_min'] = compute_min_tile_residuals(s['tile_residuals'])
        stats[zz]['group_mean'] = np.nanmean(stats[zz]['tile_residual_mean'].values())
        stats[zz]['group_variance'] = np.nanvar(stats[zz]['tile_residual_mean'].values(), ddof=normalizer)
        stats[zz]['group_median'] = np.nanmedian(stats[zz]['tile_residual_mean'].values())
        stats[zz]['group_std_deviation'] = np.sqrt(stats[zz]['group_variance'])
        stats[zz]['group_rmse_mean'] = np.nanmean(stats[zz]['tile_rmse_mean'].values())
        stats[zz]['group_rmse_min'], stats[zz]['group_rmse_max'] = compute_min_max_tile_residuals(s['tile_rmse'])
        #stats[zz]['group_rmse_min'] = compute_min_tile_residuals(s['tile_rmse'])
        #stats[zz]['group_rmse_max'] = compute_max_tile_residuals(s['tile_rmse'])
        stats[zz]

    return stats

'''
def compute_cross_section_statistics(render, stack, matchCollectionOwner, matchCollection, zstart=None, zend=None, dz=2, pool_size=5):
    zvalues = render.run(renderapi.stack.get_z_values_for_stack, stack)
    if zstart is None:
        zstart = min(zvalues)
    elif zstart < min(zvalues):
        zstart = min([zstart, min(zvalues)])

    if zend is None:
        zend = max(zvalues)
    elif zend > max(zvalues):
        zend = min([zend, max(zvalues)])

    # get all possible combinations of zvalues in pairs
    combinations = list(it.combinations(zvalues, 2))
    combinations = [c for c in combinations if abs(c[0]-c[1]) < dz]

    mypartial = partial(compute_residuals_from_group_to_group, render, stack, matchCollectionOwner, matchCollection)

    with mp.ProcessingPool(pool_size) as pool:
        data = pool.map(mypartial, combinations)
'''