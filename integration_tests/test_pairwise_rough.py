import os
import pytest
import renderapi
import json
from test_data import TEST_DATA_ROOT, render_params
from rendermodules.module.render_module import RenderModuleException
from rendermodules.rough_align.pairwise_rigid_rough import \
        PairwiseRigidRoughAlignment
from rendermodules.rough_align.make_anchor_stack import \
        MakeAnchorStack
import numpy as np


ROUGH_RESOLVED = os.path.join(
        TEST_DATA_ROOT,
        "rough_align_test_data",
        "pairwise",
        "rough_resolved.json")

PAIRWISE_MATCHES = os.path.join(
        TEST_DATA_ROOT,
        "rough_align_test_data",
        "pairwise",
        "pairwise_matches.json")

ANCHOR_XML = os.path.join(
        TEST_DATA_ROOT,
        "rough_align_test_data",
        "pairwise",
        "minnie_plus.xml")

GAP_FILE = os.path.join(
        TEST_DATA_ROOT,
        "rough_align_test_data",
        "pairwise",
        "gap_reasons.json")


@pytest.fixture(scope='module')
def render():
    render_params['project'] = 'rough_align_test'
    render = renderapi.connect(**render_params)
    return render


@pytest.fixture(scope='module')
def pairwise_matches(render):
    with open(PAIRWISE_MATCHES, 'r') as f:
        j = json.load(f)
    pmname = 'pw_matches'
    renderapi.pointmatch.import_matches(pmname, j, render=render)
    yield pmname
    renderapi.pointmatch.delete_collection(pmname, render=render)


@pytest.fixture(scope='module')
def pairwise_starting_stack(render):
    with open(ROUGH_RESOLVED, 'r') as f:
        r = renderapi.resolvedtiles.ResolvedTiles(json=json.load(f))
    sname = "pw_start"
    renderapi.stack.create_stack(sname, render=render)
    renderapi.client.import_tilespecs(sname, r.tilespecs, render=render)
    renderapi.stack.set_stack_state(sname, state='COMPLETE', render=render)
    yield sname
    renderapi.stack.delete_stack(sname, render=render)


@pytest.fixture(scope='function')
def output_stack_name(render):
    name = 'pairwise_output_stack'
    yield name
    renderapi.stack.delete_stack(name, render=render)


def test_make_anchor_stack(
        render,
        pairwise_starting_stack,
        output_stack_name,
        tmpdir_factory):
    ex = {
            "render": dict(render_params),
            "input_stack": pairwise_starting_stack,
            "output_stack": output_stack_name,
            "transform_xml": ANCHOR_XML,
            "close_stack": True
            }
    mmod = MakeAnchorStack(input_data=ex, args=[])
    mmod.run()


def test_multitile_exception(
        render,
        pairwise_starting_stack,
        output_stack_name):
    ex = {
            "render": dict(render_params),
            "input_stack": pairwise_starting_stack,
            "output_stack": "will_not_get_made",
            "transform_xml": ANCHOR_XML,
            "close_stack": True
            }
    renderapi.stack.clone_stack(
            pairwise_starting_stack,
            output_stack_name,
            render=render)
    tspecs = renderapi.tilespec.get_tile_specs_from_stack(
            output_stack_name, render=render)
    t = tspecs[0]
    t.tileId = 'something_unique'
    renderapi.client.import_tilespecs(output_stack_name, [t], render=render)
    ex['input_stack'] = output_stack_name
    mmod = MakeAnchorStack(input_data=ex, args=[])
    with pytest.raises(RenderModuleException):
        mmod.run()


def calc_residuals(tspecs, matches):
    tids = np.array([t.tileId for t in tspecs])
    res = []
    for m in matches:
        pind = np.argwhere(tids == m['pId']).flatten()[0]
        qind = np.argwhere(tids == m['qId']).flatten()[0]
        p = np.array(m['matches']['p']).transpose()
        q = np.array(m['matches']['q']).transpose()
        for tf in tspecs[pind].tforms:
                p = tf.tform(p)
        for tf in tspecs[qind].tforms:
                q = tf.tform(q)
        res += np.linalg.norm(p - q, axis=1).tolist()
    return res


def test_pairwise_results(render, tmpdir_factory):
    render_params['project'] = 'rough_align_test'
    # ground truth tilespecs, some gradual rotation and translation
    nz = 10
    z = np.arange(nz)
    theta = np.arange(nz) * 0.002
    dx = np.arange(nz) * 100 + 245
    dy = np.arange(nz) * -200 - 356
    ground_truth = [renderapi.tilespec.TileSpec() for i in np.arange(nz)]
    downsample = [renderapi.tilespec.TileSpec() for i in np.arange(nz)]
    # downsample stack will have default affine
    for i in range(nz):
        c, s = np.cos(theta[i]), np.sin(theta[i])
        tf = renderapi.transform.AffineModel(
                M00=c, M01=-s, M10=s, M11=c, B0=dx[i], B1=dy[i])
        ground_truth[i].tforms = [
                renderapi.transform.AffineModel(json=tf.to_dict())]
        downsample[i].tforms = [renderapi.transform.AffineModel()]
        for tspec in [ground_truth[i], downsample[i]]:
            tspec.ip['0'] = renderapi.image_pyramid.MipMap()
            tspec.z = z[i]
            tspec.layout.sectionId = str(float(z[i]))
            tspec.tileId = '%d' % z[i]
            tspec.width = 1500
            tspec.height = 1500

    # point matches are image-based, i.e. ground truth
    # for pairwise rigid, we need them between the ground truth pairs
    matches = []
    for i in range(nz - 1):
        src = np.random.rand(10, 2) * 1500
        p = ground_truth[i].tforms[0].inverse_tform(src)
        q = ground_truth[i + 1].tforms[0].inverse_tform(src)
        w = [1.0] * 10
        matches.append({
            "pGroupId": ground_truth[i].layout.sectionId,
            "qGroupId": ground_truth[i + 1].layout.sectionId,
            "pId": ground_truth[i].tileId,
            "qId": ground_truth[i + 1].tileId,
            "matches": {
                "w": w,
                "p": p.transpose().tolist(),
                "q": q.transpose().tolist()}})

    # make the downsample stack and collection
    ds_stack = "pw_downsample_stack"
    ds_coll = "pw_downsample_collection"
    renderapi.stack.create_stack(ds_stack, render=render)
    renderapi.client.import_tilespecs(ds_stack, downsample, render=render)
    renderapi.stack.set_stack_state(ds_stack, state='COMPLETE', render=render)
    renderapi.pointmatch.import_matches(ds_coll, matches, render=render)

    # a human determines the true relative transforms for 2 sections
    transforms = {}
    transforms['%d_blah' % z[2]] = ground_truth[2].tforms[0].to_dict()
    transforms['%d_blah' % z[-1]] = ground_truth[-1].tforms[0].to_dict()
    output_directory = str(tmpdir_factory.mktemp('pairwise'))
    tjson_path = os.path.join(output_directory, 'human_made_transforms.json')
    with open(tjson_path, 'w') as f:
        json.dump(transforms, f, indent=2)

    # make an anchor stack from that
    anchor_stack = "an_anchor_stack"
    ex = {
            "render": dict(render_params),
            "input_stack": ds_stack,
            "output_stack": anchor_stack,
            "transform_json": tjson_path,
            "close_stack": True
            }
    mmod = MakeAnchorStack(input_data=ex, args=[])
    mmod.run()

    aligned_stack = "aligned_stack"
    pw_example = {
            "render": dict(render_params),
            "input_stack": ds_stack,
            "output_stack": aligned_stack,
            "anchor_stack": anchor_stack,
            "match_collection": ds_coll,
            "close_stack": True,
            "minZ": z[0],
            "maxZ": z[-1],
            "gap_file": None,
            "pool_size": 2,
            "output_json": os.path.join(output_directory, 'output.json'),
            "overwrite_zlayer": True,
            "translate_to_positive": True,
            "translation_buffer": [50, 50]
            }
    pwmod = PairwiseRigidRoughAlignment(input_data=dict(pw_example), args=[])
    pwmod.run()

    with open(pwmod.args['output_json'], 'r') as f:
        pwout = json.load(f)

    # check the residuals
    new_specs = renderapi.tilespec.get_tile_specs_from_stack(
            pwout['output_stack'], render=render)
    res_new = calc_residuals(new_specs, matches)
    assert np.all(np.array(res_new) < 1.0)

    # everything rotated correctly?
    assert np.all(np.isclose(
        theta,
        np.array([t.tforms[0].rotation for t in new_specs])))

    # in this artificial example, the ground truth is changing
    # in a smooth linear way, we can check the results are
    # weighted linear averages of the anchors
    for i in range(2, 9):
        assert np.all(
                np.isclose(
                    new_specs[i].tforms[0].M,
                    (new_specs[2].tforms[0].M * (7 - np.abs(2 - i)) +
                        new_specs[9].tforms[0].M * (7 - np.abs(9 - i))) / 7,
                    1e-3))

    # the module gives good residuals without an anchor stack
    # one should just be careful doing this over long stretches
    # as it may lead to some undesired, unphysical long-range drift
    # in the solution
    pw_example['anchor_stack'] = None
    pwmod = PairwiseRigidRoughAlignment(input_data=dict(pw_example), args=[])
    pwmod.run()
    with open(pwmod.args['output_json'], 'r') as f:
        pwout = json.load(f)
    # check the residuals
    new_specs = renderapi.tilespec.get_tile_specs_from_stack(
            pwout['output_stack'], render=render)
    res_new = calc_residuals(new_specs, matches)
    assert np.all(np.array(res_new) < 1.0)

    # this method requires matches between neighboring groups
    renderapi.pointmatch.delete_point_matches_between_groups(
            ds_coll, "3.0", "4.0", render=render)
    with pytest.raises(RenderModuleException):
        pwmod = PairwiseRigidRoughAlignment(
                input_data=dict(pw_example), args=[])
        pwmod.run()

    # delete the render things
    renderapi.stack.delete_stack(ds_stack, render=render)
    renderapi.stack.delete_stack(anchor_stack, render=render)
    renderapi.stack.delete_stack(pwout['output_stack'], render=render)
    renderapi.pointmatch.delete_collection(ds_coll, render=render)


def test_pairwise_rigid_alignment_coverage(
        render,
        pairwise_starting_stack,
        pairwise_matches,
        output_stack_name,
        tmpdir_factory):

    output_directory = str(tmpdir_factory.mktemp('pwr_output_json'))

    example = {
            "render": dict(render_params),
            "input_stack": pairwise_starting_stack,
            "output_stack": output_stack_name,
            "match_collection": pairwise_matches,
            "close_stack": True,
            "minZ": 8500,
            "maxZ": 8700,
            "gap_file": None,
            "pool_size": 2,
            "output_json": os.path.join(output_directory, 'output.json'),
            "overwrite_zlayer": True,
            "translate_to_positive": True,
            "translation_buffer": [50, 50]
            }

    # normal
    ex = dict(example)
    pwmod = PairwiseRigidRoughAlignment(input_data=ex, args=[])
    pwmod.run()
    with open(ex['output_json'], 'r') as f:
        outj = json.load(f)

    assert(outj['masked'] == [])
    assert(outj['missing'] == [8595])
    assert(len(outj['residuals']) == 199)
    os.remove(ex['output_json'])
    renderapi.stack.delete_stack(outj['output_stack'], render=render)

    # gap file
    ex = dict(example)
    ex['gap_file'] = GAP_FILE
    pwmod = PairwiseRigidRoughAlignment(input_data=ex, args=[])
    pwmod.run()
    with open(ex['output_json'], 'r') as f:
        outj = json.load(f)
    assert(outj['masked'] == [])
    assert(outj['missing'] == [8595])
    assert(len(outj['residuals']) == 199)
    os.remove(ex['output_json'])
    renderapi.stack.delete_stack(outj['output_stack'], render=render)
