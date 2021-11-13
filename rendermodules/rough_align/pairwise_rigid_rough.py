#!/usr/bin/env python
from functools import partial
import json

import numpy as np
import renderapi

from rendermodules.module.render_module import (
        StackTransitionModule,
        RenderModuleException)
from rendermodules.rough_align.schemas import (
        PairwiseRigidSchema,
        PairwiseRigidOutputSchema)


example = {
        "render": {
            "host": "em-131fs",
            "port": 8987,
            "owner": "TEM",
            "project": "17797_1R",
            "client_scripts": ("/allen/aibs/pipeline/image_processing/"
                               "volume_assembly/render-jars/production/scripts")
          },
        "input_stack": "em_2d_montage_solved_py_0_01_mapped",
        "anchor_stack": None,
        "output_stack": "test_pre_rigid_with_anchors_plus",
        "match_collection": "chunk_rough_align_point_matches",
        "close_stack": True,
        "minZ": 8500,
        "maxZ": 9000,
        "gap_file": "/allen/aibs/pipeline/image_processing/volume_assembly/rough_align_test_data/pairwise/gap_reasons.json",
        "pool_size": 20,
        "output_json": "test_output.json",
        "overwrite_zlayer": True,
        "translate_to_positive": True,
        "translation_buffer": [50, 50]
        }


def avg_residual(match, ptilespec, qtilespec):
    q = np.array(match['matches']['p']).transpose()
    p = np.array(match['matches']['q']).transpose()
    if match['pId'] == ptilespec.tileId:
        p = np.array(match['matches']['p']).transpose()
        q = np.array(match['matches']['q']).transpose()

    pt = ptilespec.tforms[0].tform(p)
    qt = qtilespec.tforms[0].tform(q)
    res = np.linalg.norm(pt - qt, axis=1)
    return res.mean()


def tspecjob(collection, render, tilespecs, estimate=True):
    result = {}
    result['tilespecs'] = tilespecs

    matches = renderapi.pointmatch.get_matches_from_tile_to_tile(
            collection,
            tilespecs[0].layout.sectionId,
            tilespecs[0].tileId,
            tilespecs[1].layout.sectionId,
            tilespecs[1].tileId,
            render=render)

    if len(matches) != 1:
        estr = "\n  expected 1 matching tile pair, found %d for" % (
                len(matches))
        estr += '\n  %s\n  group: %s\n  %s\n  group: %s' % (
            tilespecs[0].tileId,
            tilespecs[0].layout.sectionId,
            tilespecs[1].tileId,
            tilespecs[1].layout.sectionId)
        raise RenderModuleException(estr)

    match = matches[0]

    if estimate:
        tf = renderapi.transform.RigidModel()
        src = np.array(match['matches']['p']).transpose()
        dst = np.array(match['matches']['q']).transpose()
        if match['pGroupId'] == tilespecs[0].layout.sectionId:
            src = np.array(match['matches']['q']).transpose()
            dst = np.array(match['matches']['p']).transpose()

        ind = np.argwhere(
                np.isclose(
                    np.array(match['matches']['w']),
                    1.0)).flatten()
        tf.estimate(src[ind, :], dst[ind, :])
        result['transform'] = tf

    result['avg_residual'] = {
            'z0': tilespecs[0].z,
            'z1': tilespecs[1].z,
            'avg_residual': avg_residual(match, tilespecs[0], tilespecs[1])
            }

    return result


def get_zrange_with_skipped(gapfile, zin):
    if gapfile is None:
        return zin
    with open(gapfile, 'r') as f:
        j = json.load(f)
    skip_zs = [int(k) for k in j]
    zout = []
    for z in zin:
        if z not in skip_zs:
            zout.append(z)
    return zout


def translate_to_positive(tilespecs, translation_buffer):
    xymin = np.array([
        t.bbox_transformed(
            ndiv_inner=3).min(
                axis=0) for t in tilespecs]).min(axis=0)
    for t in tilespecs:
        t.tforms[0].M[0, 2] += \
            translation_buffer[0] - xymin[0]
        t.tforms[0].M[1, 2] += \
            translation_buffer[1] - xymin[1]
    return tilespecs


class PairwiseRigidRoughAlignment(StackTransitionModule):
    default_schema = PairwiseRigidSchema
    default_output_schema = PairwiseRigidOutputSchema

    def run(self):
        z_overlap = self.get_overlapping_inputstack_zvalues(
                zvalues=range(self.args['minZ'], self.args['maxZ'] + 1))
        self.args['zValues'] = np.array(get_zrange_with_skipped(
                self.args['gap_file'],
                z_overlap))

        if self.args['anchor_stack'] is None:
            anchor_specs = np.array(renderapi.tilespec.get_tile_specs_from_z(
                    self.args['input_stack'],
                    self.args['zValues'][0],
                    render=self.render))
        else:
            tspecs = renderapi.tilespec.get_tile_specs_from_stack(
                    self.args['anchor_stack'],
                    render=self.render)
            anchor_specs = np.array([
                    t for t in tspecs if t.z in self.args['zValues']])
        anchor_zs = np.array([a.z for a in anchor_specs])
        aind = np.argsort(anchor_zs)
        anchor_specs = anchor_specs[aind]
        clumps = []

        for i in range(anchor_specs.size):
            # backward looking
            zback = self.args['zValues'] < anchor_specs[i].z
            if i != 0:
                zback = zback & (self.args['zValues'] > anchor_specs[i - 1].z)
            clumps.append({
                "direction": -1,
                "z_values": np.sort(self.args['zValues'][zback])[::-1],
                "anchor": anchor_specs[i]})

            # forward looking
            zfor = self.args['zValues'] > anchor_specs[i].z
            if i != anchor_specs.size - 1:
                zfor = zfor & (self.args['zValues'] < anchor_specs[i + 1].z)
            clumps.append({
                "direction": 1,
                "z_values": np.sort((self.args['zValues'][zfor])),
                "anchor": anchor_specs[i]})

        new_specs = []
        for c in clumps:
            a = self.pairwise_estimate(c['anchor'], c['z_values'])
            new_specs += a

        nzs = np.array([n['spec'].z for n in new_specs])
        unzs = np.unique(nzs)

        averaged_new_specs = []
        for unz in unzs:
            ind = np.argwhere(nzs == unz).flatten()
            if ind.size == 1:
                averaged_new_specs.append(new_specs[ind[0]]['spec'])
            else:
                dsum = np.array([new_specs[i]['dist'] for i in ind]).sum()
                if dsum == 0:
                    averaged_new_specs.append(new_specs[ind[0]]['spec'])
                else:
                    M = np.zeros((3, 3))
                    for i in ind:
                        w = (dsum - new_specs[i]['dist']) / float(dsum)
                        M += w * new_specs[i]['spec'].tforms[0].M
                    averaged_new_specs.append(new_specs[ind[0]]['spec'])
                    averaged_new_specs[-1].tforms[0].M = M

        if self.args['translate_to_positive']:
            averaged_new_specs = translate_to_positive(
                    averaged_new_specs,
                    self.args['translation_buffer'])

        self.output_stack = self.args['output_stack'] + \
            '_zs%d_ze%d' % (self.args['minZ'], self.args['maxZ'])
        self.output_tilespecs_to_stack(averaged_new_specs)

        self.output(self.check_result())

    def check_result(self):
        tilespecs = renderapi.tilespec.get_tile_specs_from_stack(
                self.output_stack, render=self.render)

        check_func = partial(
                tspecjob,
                self.args['match_collection'],
                self.render,
                estimate=False)
        fargs = [[
                    tilespecs[i - 1],
                    tilespecs[i],
                    ] for i in range(1, len(tilespecs))]

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            result = {}
            result['residuals'] = []
            for r in pool.map(check_func, fargs):
                result['residuals'].append(r['avg_residual'])

        zall = np.arange(
                self.args['minZ'],
                self.args['maxZ'] + 1)
        z = np.array([t.z for t in tilespecs])
        result['missing'] = np.setdiff1d(zall, z).tolist()
        result['masked'] = [
                int(t.z) for t in tilespecs if t.ip[0].maskUrl is not None]
        result['output_stack'] = self.output_stack
        result['minZ'] = self.args['minZ']
        result['maxZ'] = self.args['maxZ']
        return result

    def pairwise_estimate(self, anchor_spec, z_values):
        tilespecs = [anchor_spec]
        for z in z_values:
            tilespecs += renderapi.tilespec.get_tile_specs_from_z(
                     self.args['input_stack'],
                     z,
                     render=self.render)

        # accumulate transforms (zs = Identity)
        estimate_func = partial(
                tspecjob,
                self.args['match_collection'],
                self.render,
                estimate=True)
        fargs = [[
                    tilespecs[i - 1],
                    tilespecs[i],
                    ] for i in range(1, len(tilespecs))]

        M = anchor_spec.tforms[0].M
        new_tilespecs = [{
            'spec': anchor_spec,
            'dist': 0}]
        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            for result in pool.map(estimate_func, fargs):
                M = M.dot(result['transform'].M)
                newtf = renderapi.transform.RigidModel()
                newtf.M = M
                ts = result['tilespecs'][1]
                ts.tforms = [newtf]
                new_tilespecs.append({
                    'spec': renderapi.tilespec.TileSpec(json=ts.to_dict()),
                    'dist': int(np.abs(ts.z - anchor_spec.z))})

        return new_tilespecs


if __name__ == '__main__':
    prmod = PairwiseRigidRoughAlignment()
    prmod.run()
