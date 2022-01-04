# Code logic borrowed from Russel Torres

import concurrent.futures
import json
import urllib
import uuid

import numpy 
import renderapi
import shapely.geometry
import shapely.ops
import shapely.affinity

from asap.module.render_module import (
        RenderModule, RenderModuleException, StackInputModule)


example = {
    "render": {
        "host": "em-131db2.corp.alleninstitute.org",
        "owner": "TEM",
        "port": 8888,
        "project": "21617_R1",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts"
    }, 
    "minZ": 10642,
    "maxZ": 10645,
    "rough_aligned_stack": "20210428_rmt_tps25_depth4",
    "rough_pm_collections": ["21617_R1_rough_20210426_downsampled_mapped"],
    "downsample_scale": 0.01,
    "pm_depth": 1,
    "radial_cutoff": 55
}

def get_ctrthreshold_filter(arr, threshold):
    return numpy.linalg.norm(arr - arr.mean(axis=0), axis=1) > threshold

def match_worldcoords_ts(ts, matcharr, sharedTransforms=[]):
    return renderapi.transform.utils.estimate_dstpts(
        ts.tforms, src=matcharr, reference_tforms=sharedTransforms)

# TODO include weights?
def residuals_from_ts(p_ts, q_ts, match, sharedTransforms=[]):
    p_matches = numpy.array(match["matches"]["p"]).T
    q_matches = numpy.array(match["matches"]["q"]).T
    
    p_tformed = renderapi.transform.utils.estimate_dstpts(
        p_ts.tforms, src=p_matches, reference_tforms=sharedTransforms)
    q_tformed = renderapi.transform.utils.estimate_dstpts(
        q_ts.tforms, src=q_matches, reference_tforms=sharedTransforms)
    return q_tformed - p_tformed

def angle_between_points(pts_a, pts_b, observer_pts=None):
    """get angle between points in NxM arrays with optional observer points
    where N is number of points and M is dimension of points
    """
    if observer_pts is None:
        observer_pts = numpy.zeros_like(pts_a)
    a = pts_a - observer_pts
    b = pts_b - observer_pts
    return numpy.arccos(
        numpy.einsum("ij,ij->i", a, b) /  # vectorized dot product
        numpy.linalg.norm(a, axis=1) /
        numpy.linalg.norm(b, axis=1))

def combine_resolvedtiles(rts_l):
    tforms = {i.transformId: i for l in (rts.transforms for rts in rts_l) for i in l}
    tspecs = list({ts.tileId: ts for l in (rts.tilespecs for rts in rts_l) for ts in l}.values())
    
    return renderapi.resolvedtiles.ResolvedTiles(transformList=tforms, tilespecs=tspecs)

def angle_convert(angles, inunit, outunit):
    if inunit == outunit:
        return angles
    else:
        try:
            new_angles = {
                ("degrees", "radians"): lambda x: numpy.radians(x),
                ("radians", "degrees"): lambda x: numpy.degrees(x)
            }[(inunit, outunit)](angles)
            return new_angles
        except KeyError as e:
            raise ValueError(f"cannot convert from {inunit} to {outunit}")


def mean_angles(angles, angle_unit="radians"):
    angles = angle_convert(angles, angle_unit, "radians")

    s = numpy.sin(angles)
    c = numpy.cos(angles)

    m = numpy.arctan2(numpy.nanmean(s), numpy.nanmean(c))

    return angle_convert(m, "radians", angle_unit)


def stdev_angles(angles, angle_unit="radians"):
    angles = angle_convert(angles, angle_unit, "radians")

    s = numpy.sin(angles)
    c = numpy.cos(angles)

    stdev = numpy.sqrt(-numpy.log((numpy.nanmean(s) ** 2) + (numpy.nanmean(c) ** 2)))

    return angle_convert(stdev, "radians", angle_unit)

def recursively_combine_dicts(lod):
    """
    combine list of dictionaries with highest priority for a
      key being first 
    """
    newd = {}
    for d in lod:
        for k in d.keys() - newd.keys():
            newd[k] = d[k]
    return newd
        

def group_matches_from_collections(matchgroups, pm_collections, r, num_threads=1):
    matches_lol = []
    for pm_collection in pm_collections:
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_threads) as e:
            futs = [e.submit(renderapi.pointmatch.get_matches_with_group, pm_collection, g, render=r) for g in matchgroups]
    
            matches_lol.append([i for l in (fut.result() for fut in concurrent.futures.as_completed(futs)) for i in l])
    
    # overwrite
    tupset_to_matches_list = [
        {frozenset((
            (m["pGroupId"], m["pId"]),
            (m["qGroupId"], m["qId"]))
        ): m for m in matches} for matches in matches_lol]
    
    d = recursively_combine_dicts(tupset_to_matches_list)
    return list(d.values())


class RoughAlignQCModule(RenderModule):
    def run(self):
        stack_zs = [z for z in renderapi.stack.get_z_values_for_stack(self.args['rough_aligned_stack'], render=self.render)]
        z_list = list(set(self.args['zValues']).intersection(stack_zs))
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.args['pool_size']) as e:
            rtfut_to_z = {e.submit(renderapi.resolvedtiles.get_resolved_tiles_from_z, self.args['rough_aligned_stack'], z, render=self.render): z for z in )}
        
        z_to_rts = {rtfut_to_z[fut]: fut.result() for fut in concurrent.futures.as_completed(rtfut_to_z)}

        matchgroups = {ts.layout.sectionId for ts in (i for l in (rts.tilespecs for rts in z_to_rts.values()) for i in l)}

        allmatches = group_matches_from_collections(matchgroups, self.args['rough_pm_collections'], self.render, self.args['pool_size'])

        tileId_to_tileId_match = {(m["pId"], m["qId"]): m for m in allmatches}
        combined_resolvedtiles = combine_resolvedtiles(z_to_rts.values())
        tileId_to_tilespecs = {ts.tileId: ts for ts in combined_resolvedtiles.tilespecs}
        tileId_to_z = {ts.tileId: ts.z for ts in combined_resolvedtiles.tilespecs}

        tileId_to_tileId_tformed_pts = {}
        for (pId, qId), match in tileId_to_tileId_match.items():
            try:
                p_ts = tileId_to_tilespecs[pId]
                q_ts = tileId_to_tilespecs[qId]
            except KeyError:
                continue
            p_matches = numpy.array(match["matches"]["p"]).T
            q_matches = numpy.array(match["matches"]["q"]).T

            tileId_to_tileId_tformed_pts[(pId, qId)] = (
                match_worldcoords_ts(p_ts, p_matches, combined_resolvedtiles.transforms),
                match_worldcoords_ts(q_ts, q_matches, combined_resolvedtiles.transforms)
            )

        # center of mass calculation
        tileId_to_tileId_residuals = {}
        tileId_to_tileId_angular_residuals = {}

        for (pId, qId), (p_pts, q_pts) in tileId_to_tileId_tformed_pts.items():
            p_ctr = p_pts.mean(axis=0)

            ang_residuals = angle_between_points(p_pts, q_pts, p_ctr)
            residuals = p_pts - q_pts

            tileId_to_tileId_residuals[(pId, qId)] = residuals
            



    