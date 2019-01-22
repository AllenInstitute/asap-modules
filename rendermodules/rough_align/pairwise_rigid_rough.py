import renderapi
import numpy as np
import json
from rendermodules.module.render_module import (
        StackInputModule,
        StackOutputModule)
from rendermodules.rough_align.schemas import (
        PairwiseRigidSchema,
        PairwiseRigidOutputSchema)
from functools import partial


example = {
        "render": {
            "host": "em-131fs",
            "port": 8987,
            "owner": "TEM",
            "project": "17797_1R",
            "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts"
          },
        "input_stack": "em_2d_montage_solved_py_0_01_mapped",
        "output_stack": "test_pairwise_rigid",
        "match_collection": "chunk_rough_align_point_matches",
        "close_stack": True,
        "minZ": 14725,
        "maxZ": 14755,
        "gap_file": "/allen/programs/celltypes/workgroups/em-connectomics/danielk/pre_align_rigid/gap_reasons.json",
        "pool_size": 7,
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

    try:
        assert(len(matches) == 1)
    except AssertionError as e:
        estr = "\n  expected 1 matching tile pair, found %d for" % (
                len(matches))
        estr += '\n  %s\n  group: %s\n  %s\n  group: %s' % (
            tilespecs[0].tileId,
            tilespecs[0].layout.sectionId,
            tilespecs[1].tileId,
            tilespecs[1].layout.sectionId)
        e.args += (estr, )
        raise

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


class PairwiseRigidRoughAlignment(StackInputModule, StackOutputModule):
    default_schema = PairwiseRigidSchema
    default_output_schema = PairwiseRigidOutputSchema

    def run(self):
        self.render = renderapi.connect(**self.args['render'])

        self.args['zValues'] = self.get_inputstack_zs()
        self.args['zValues'] = get_zrange_with_skipped(
                self.args['gap_file'],
                self.args['zValues'])

        tilespecs = []
        for z in self.args['zValues']:
            tilespecs += renderapi.tilespec.get_tile_specs_from_z(
                    self.args['input_stack'],
                    z,
                    render=self.render)

        new_tilespecs = self.pairwise_estimate(tilespecs)

        if self.args['translate_to_positive']:
            new_tilespecs = translate_to_positive(
                    new_tilespecs,
                    self.args['translation_buffer'])

        self.output_stack = self.args['output_stack'] + \
            '_zs%d_ze%d' % (self.args['minZ'], self.args['maxZ'])
        self.output_tilespecs_to_stack(new_tilespecs)

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

    def pairwise_estimate(self, tilespecs):
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
        M = np.eye(3)
        newtf = renderapi.transform.RigidModel()
        newtf.M = M
        new_tilespecs = [tilespecs[0]]
        new_tilespecs[-1].tforms = [newtf]

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            for result in pool.map(estimate_func, fargs):
                M = M.dot(result['transform'].M)
                newtf = renderapi.transform.RigidModel()
                newtf.M = M
                new_tilespecs.append(result['tilespecs'][1])
                new_tilespecs[-1].tforms = [newtf]

        return new_tilespecs


if __name__ == '__main__':
    prmod = PairwiseRigidRoughAlignment(input_data=example)
    prmod.run()
