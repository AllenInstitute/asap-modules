# Distortion metric logic borrowed from Russel Torres


import concurrent.futures
import matplotlib.pyplot as plt
import seaborn as sns
import urllib
import numpy as np
import renderapi

from asap.module.render_module import (
    RenderModule, RenderModuleException)
from asap.em_montage_qc.schemas import DetectDistortionParameters, DetectDistortionParametersOutput

example = {
    "render": {
        "host": "em-131db2.corp.alleninstitute.org",
        "port": 8888,
        "owner": "TEM",
        "project": "render_test",
        "client_scripts": ""
    },
    "input_stacks": ["montage_stack"],
    "match_collections": ["render_test_pm_collection"],
    "zValues": [1028, 1029],
    "pool_size": 40,
    "threshold_cutoff": (0.005, 0.005)
}

def get_rts_fallthrough(stacks, *args, **kwargs):
    for stack in stacks:
        try:
            return renderapi.resolvedtiles.get_resolved_tiles_from_z(stack, *args, **kwargs)
        except Exception:
            pass
    raise ValueError("No resolved tiles found")

'''
def get_pmatches_group_to_group_fallthrough(collections, *args, **kwargs):
    for pm_collection in collections:
        pmatches = renderapi.pointmatch.get_matches_from_group_to_group(
            pm_collection, *args, **kwargs)
        if pmatches:
            return pmatches
    raise ValueError("No point matches found")


def get_z_scales(z, input_stacks,
                 pm_collections, render):
    rts = get_rts_fallthrough(input_stacks, z, render=render)
    groupid = sections_from_resolvedtiles(rts)[0]
    matches = get_pmatches_group_to_group_fallthrough(pm_collections, groupid, groupid, render=render)

    match_pIds, match_qIds = map(set, zip(*[(m["pId"], m["qId"]) for m in matches]))
    match_tileIds = match_pIds | match_qIds

    tId_to_tilespecs = {ts.tileId: ts for ts in rts.tilespecs}

    rts.tilespecs = [tId_to_tilespecs[tId] for tId in tId_to_tilespecs.keys() & match_tileIds]
    return np.array([ts.tforms[-1].scale for ts in rts.tilespecs])


def do_get_z_scales(*args, **kwargs):
    try:
        return get_z_scales(*args, **kwargs)
    except Exception:
        return



def plot_mad_stat(z_to_scalestats):
    fig = plt.figure()
    jp = sns.joinplot(
        x=[s[0] for z, s in z_to_scalestats.items()],
        y=[s[1] for z, s in z_to_scalestats.items()],
        kind="hist",
    )
    jp.ax_joint.set_xlabel("x statistic")
    jp.ax_joint.set_ylabel("y statistic")
    jp.ax_joint.axhline(y=0.005, c="r", lw=0.5)
    jp.ax_joint.axvline(x=0.005, c="r", lw=0.5)

    return jp


'''
def groupId_from_tilespec(ts):
    return ts.layout.sectionId

def sections_from_resolvedtiles(rts):
    return list({groupId_from_tilespec(ts) for ts in rts.tilespecs})


def get_scales_from_tilespecs(tilespecs):
    return np.array([ts.tforms[-1].scale for ts in tilespecs])


def get_z_scales_nopm(z, input_stacks, render):
    rts = get_rts_fallthrough(input_stacks, z, render=render)
    scales = np.array([ts.tforms[-1].scale for ts in rts.tilespecs])
    return scales[np.all(scales != [1, 1], axis=1)]

def do_get_z_scales_nopm(*args, **kwargs):
    try:
        return get_z_scales_nopm(*args, **kwargs)
    except Exception:
        return

def get_scale_statistics_std(scales):
    """get scale statistic for x and y"""
    # throw out outliers
    rel_scales = scales[np.all(np.abs(scales.mean(axis=0) - scales) < scales.std(axis=0) * 3, axis=1)]
    return rel_scales.std(axis=0)

def mad(data, axis=None, side=None):
    '''Median Absolute Distance function with left and right side option.'''
    def get_sided(d, side, axis=None):
        # FIXME uses masked arrays for convenience, not for speed.
        if side == "l":
            m = d <= np.median(d, axis=axis)
        elif side == "r":
            m = d >= np.median(d, axis=axis)
        elif side is None:
            return d
        else:
            raise ValueError("ERROR: please enter 'l', 'r', or None")
        return np.ma.masked_array(d, m)
    d = get_sided(data, side, axis)
    res = np.ma.median(np.absolute(d - np.ma.median(d, axis)), axis)
    return (res.data if isinstance(res, np.ma.masked_array) else res)

# TODO is mad robust enough to ignore outliers?
def get_scale_statistics_mad(scales):
    rel_scales = scales[np.all(np.abs(scales.mean(axis=0) - scales) < scales.std(axis=0) * 3, axis=1)]
    return mad(rel_scales, axis=0)

def get_scale_statistics_mad_sum(scales):
    rel_scales = scales[np.all(np.abs(scales.mean(axis=0) - scales) < scales.std(axis=0) * 3, axis=1)]
    return mad(rel_scales, axis=0, side="l") + mad(rel_scales, axis=0, side="r")

class DetectDistortedMontagesModule(RenderModule):
    default_output_schema = DetectDistortionParametersOutput
    default_schema = DetectDistortionParameters

    def run(self):
        zs = sorted(list({
            i for l in (renderapi.stack.get_z_values_for_stack(s, render=self.render) for s in self.args['input_stacks']) for i in l
        }))
        final_zs = list(set(zs).intersection(set(self.args['zValues'])))

        # get scale factor for each section
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.args['pool_size']) as e:
            fut_to_z = {
                e.submit(
                    do_get_z_scales_nopm,
                    z, self.args['input_stacks'], self.render): z
                for z in final_zs
            }
            z_to_scales = {fut_to_z[fut]: fut.result() for fut in concurrent.futures.as_completed(fut_to_z.keys())}

        # check if any scale is None
        zs = [z for z, scales in z_to_scales.items() if scales is None]
        for z in zs:
            z_to_scales[z] = get_z_scales_nopm(z, self.args['input_stacks'], self.render)
            
        # get the mad statistics
        z_to_scalestats = {z: get_scale_statistics_mad(scales) for z, scales in z_to_scales.items() if scales is not None}

        # find zs that fall outside cutoff
        badzs_cutoff = [z for z, s in z_to_scalestats.items() if s[0] > self.args['threshold_cutoff'][0] or s[1] > self.args['threshold_cutoff'][1]]

        self.output({'distorted_sections': badzs_cutoff})


if __name__ == '__main__':
    mod = DetectDistortedMontagesModule(input_data=example)
    mod.run()

'''
def detect_distortions(input_stacks, pm_collections, z_indices, render, cut_off=(0.005, 0.005), pool_size=20):
    zs = sorted(list({
        i for l in (renderapi.stack.get_z_values_for_stack(s, render=render) for s in input_stacks) for i in l
    }))
    final_zs = list(set(zs).intersection(set(z_indices)))

    # get scale factor for each section
    with concurrent.futures.ProcessPoolExecutor(max_workers=pool_size) as e:
        fut_to_z = {
            e.submit(
                do_get_z_scales_nopm,
                z, input_stacks, render): z
            for z in final_zs
        }
        z_to_scales = {fut_to_z[fut]: fut.result() for fut in concurrent.futures.as_completed(fut_to_z.keys())}

    # check if any scale is None
    zs = [z for z, scales in z_to_scales.items() if scales is None]
    for z in zs:
        z_to_scales[z] = get_z_scales_nopm(z, input_stacks, render)
        
    # get the mad statistics
    z_to_scalestats = {z: get_scale_statistics_mad(scales) for z, scales in z_to_scales.items() if scales is not None}

    # find zs that fall outside cutoff
    badzs_cutoff = [z for z, s in z_to_scalestats.items() if s[0] > cut_off[0] or s[1] > cut_off[1]]

    return badzs_cutoff
'''
