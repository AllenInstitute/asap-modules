'''
Test stack fusion by affine-based registration and transform interpolation
'''
import copy
import json
import os
import random

import numpy
import pytest
import renderapi
from six import viewkeys, iteritems

from test_data import (FUSION_TILESPEC_JSON, FUSION_TRANSFORM_JSON,
                       render_params, pool_size)
import asap.fusion.register_adjacent_stack
import asap.fusion.fuse_stacks

try:
    xrange
except NameError:
    xrange = range

rp = dict(render_params, **{'project': 'fusion_test'})


@pytest.fixture(scope='module')
def render():
    render = renderapi.connect(**rp)
    return render


@pytest.fixture(scope='module')
def test_tilespecs():
    return [renderapi.tilespec.TileSpec(json=d) for d in FUSION_TILESPEC_JSON]


@pytest.fixture(scope='module')
def test_tforms():
    return [renderapi.transform.load_transform_json(d)
            for d in FUSION_TRANSFORM_JSON]


@pytest.fixture(scope='module')
def validstack(test_tilespecs, test_tforms, render):
    """Stack defined by original tilespecs -- coordinates
    in fused stack should match this"""
    stackname = 'validstack_renderfusion'
    renderapi.stack.create_stack(stackname, render=render)
    renderapi.client.import_tilespecs_parallel(
        stackname, test_tilespecs, test_tforms,
        poolsize=pool_size, render=render)
    yield stackname
    renderapi.stack.delete_stack(stackname, render=render)


@pytest.fixture(scope='module')
def stack_DAG(test_tilespecs, test_tforms, render, root_index=2):
    """build randomly transformed overlapping stacks from the input jsons and
    yield a graph describing the relations of those stacks"""
    zs = sorted({ts.z for ts in test_tilespecs})
    # FIXME empirical -- make a little more intuitive for changing testdata
    pergroup = 4
    overlap = 2
    stackzs = [g for g in (zs[i:i+pergroup] for i in xrange(
        0, len(zs), pergroup-overlap)) if len(g) > overlap]

    nodes = [
        {'stack': 'stack_z{}_z{}'.format(
             int(float(min(groupzs))), int(float(max(groupzs)))),
         'transform': (renderapi.transform.AffineModel() if i == root_index
                       else get_random_rigid_tform()),
         'children': []} for i, groupzs in enumerate(stackzs)]

    def buildchildren(nodelist):
        childnode = None
        for nd in nodelist[::-1]:
            if childnode is not None:
                nd['children'].append(childnode)
            childnode = copy.copy(nd)
        return childnode

    # build DAG by generating children on either side of root node
    dag = nodes[root_index]
    forwardchild = buildchildren(nodes[root_index+1:])
    backwardchild = buildchildren(nodes[:root_index][::-1])
    print("root dag: {}".format(renderapi.utils.renderdumps(dag, indent=2)))

    if forwardchild is not None:
        dag['children'].append(forwardchild)
    if backwardchild is not None:
        dag['children'].append(backwardchild)

    print("full dag: {}".format(renderapi.utils.renderdumps(dag, indent=2)))

    # build stacks based on DAG relations
    def build_childstacks(nodelist, nodezs, tspecs, tforms, r):
        last_tform = renderapi.transform.AffineModel()
        for child, zs in zip(nodelist, nodezs):
            last_tform = child['transform'].invert().concatenate(last_tform)
            # last_tform = last_tform.concatenate(child['transform'].invert())
            ztspecs = [ts for ts in tspecs if ts.z in zs]
            renderapi.stack.create_stack(child['stack'], render=r)
            renderapi.client.import_tilespecs_parallel(
                child['stack'], ztspecs, tforms,
                poolsize=pool_size, close_stack=False, render=r)
            renderapi.client.transformSectionClient(
                child['stack'], '{}_tform'.format(child['stack']),
                last_tform.className, last_tform.dataString.replace(' ', ','),
                zValues=zs, render=r)
            renderapi.stack.set_stack_state(
                child['stack'], 'COMPLETE', render=r)

    build_childstacks(
        nodes[root_index+1:], stackzs[root_index+1:],
        test_tilespecs, test_tforms, render)
    build_childstacks(
        nodes[:root_index][::-1], stackzs[:root_index][::-1],
        test_tilespecs, test_tforms, render)

    # generate root stack
    renderapi.stack.create_stack(nodes[root_index]['stack'], render=render)
    renderapi.client.import_tilespecs_parallel(
        nodes[root_index]['stack'],
        [ts for ts in test_tilespecs if ts.z in stackzs[root_index]],
        test_tforms,
        poolsize=pool_size, render=render)

    yield dag

    # remove all stacks associated with DAG
    for nd in nodes:
        renderapi.stack.delete_stack(nd['stack'], render=render)


def get_random_rigid_tform(max_translation_tuple=(10, 10)):
    # random translation
    x, y = numpy.array(max_translation_tuple) * numpy.random.rand(2)
    translate_tform = renderapi.transform.AffineModel(B0=x, B1=y)
    # random-ish rotation
    theta = numpy.random.rand() * 2 * numpy.pi
    rotate_tform = renderapi.transform.AffineModel(
        M00=numpy.cos(theta), M01=-numpy.sin(theta),
        M10=numpy.sin(theta), M11=numpy.cos(theta))
    return translate_tform.concatenate(rotate_tform)


def test_register_first_stack(render, stack_DAG, tmpdir):
    RegisterSubvolumeModule = (
        asap.fusion.register_adjacent_stack.RegisterSubvolumeModule)
    example_parameters = (
        asap.fusion.register_adjacent_stack.example_parameters)

    parentstack = stack_DAG['stack']
    child = stack_DAG['children'][0]
    childstack = child['stack']
    tform = child['transform']

    test_input = dict(example_parameters, **{
        'render': render.make_kwargs(),
        'stack_a': parentstack,
        'stack_b': childstack})

    outputfn = os.path.join(str(tmpdir), 'register_stack_out.json')
    rms = RegisterSubvolumeModule(
        input_data=test_input,
        args=['--output_json', outputfn])
    rms.run()

    with open(rms.args['output_json'], 'r') as f:
        outd = json.load(f)

    estimated_tform = renderapi.transform.load_transform_json(
        outd['transform'])
    tspecs = renderapi.tilespec.get_tile_specs_from_stack(  # noqa: F841
        childstack, render=render)
    assert numpy.allclose(estimated_tform.M, tform.M)
    assert outd['stack_a'] == parentstack
    assert outd['stack_b'] == childstack


def test_register_all_stacks(render, stack_DAG):
    RegisterSubvolumeModule = (
        asap.fusion.register_adjacent_stack.RegisterSubvolumeModule)
    example_parameters = (
        asap.fusion.register_adjacent_stack.example_parameters)

    def registerchildrentest(node):
        for child in node['children']:
            parentstack = node['stack']
            childstack = child['stack']
            tform = child['transform']

            test_input = dict(example_parameters, **{
                'render': render.make_kwargs(),
                'stack_a': parentstack,
                'stack_b': childstack})
            rms = RegisterSubvolumeModule(
                input_data=test_input,
                args=['--output_json', 'register_stack_out.json'])
            rms.run()

            with open(rms.args['output_json'], 'r') as f:
                outd = json.load(f)

            estimated_tform = renderapi.transform.load_transform_json(
                outd['transform'])
            tspecs = renderapi.tilespec.get_tile_specs_from_stack(  # noqa: F841, E501
                childstack, render=render)

            assert outd['stack_a'] == parentstack
            assert outd['stack_b'] == childstack

            assert numpy.allclose(estimated_tform.M, tform.M)

            registerchildrentest(child)
    registerchildrentest(stack_DAG)


def compare_stacks_tilecenters(render, stack_hyp, stack_true,
                               distance_thres=1., testzs=None):
    validzs = set(renderapi.stack.get_z_values_for_stack(
        stack_true, render=render))
    zs = set(renderapi.stack.get_z_values_for_stack(
        stack_hyp, render=render))

    validzs = (validzs if testzs is None else set(
        testzs).intersection(validzs))

    # assure zs are shared
    assert not zs.symmetric_difference(validzs)

    for z in zs:
        created_tId_to_tile = {
            ts.tileId: ts for ts in
            renderapi.tilespec.get_tile_specs_from_z(
                stack_hyp, z, render=render)}

        valid_tId_to_tile = {
            ts.tileId: ts for ts in renderapi.tilespec.get_tile_specs_from_z(
                stack_true, z, render=render)}

        # assure all tiles are represented
        assert not (
            viewkeys(valid_tId_to_tile) ^ viewkeys(created_tId_to_tile))

        # assert that all tile centers are within distance threshold
        created_centerpoint_l2w_in = []
        valid_centerpoint_l2w_in = []
        for tileId, tile in iteritems(created_tId_to_tile):
            validtile = valid_tId_to_tile[tileId]

            created_centerpoint_l2w_in.append(
                {'tileId': tileId, 'visible': False,
                 'local': [tile.width // 2, tile.height // 2]})

            valid_centerpoint_l2w_in.append(
                {'tileId': tileId, 'visible': False,
                 'local': [validtile.width // 2, validtile.height // 2]})
        # using server-side batch coordinate processing
        wc_valid = renderapi.coordinate.local_to_world_coordinates_batch(
            stack_true, valid_centerpoint_l2w_in, z, number_of_threads=5,
            render=render)
        wc_created = renderapi.coordinate.local_to_world_coordinates_batch(
            stack_hyp, created_centerpoint_l2w_in, z, number_of_threads=5,
            render=render)

        validcoord = numpy.array([d['world'][:2] for d in wc_valid])
        createdcoord = numpy.array([d['world'][:2] for d in wc_created])

        print("comparing world coordinates for z{}".format(z))
        print(wc_valid[:5])
        print(wc_created[:5])
        assert (numpy.linalg.norm(
            validcoord - createdcoord, axis=1).max() < distance_thres)


def test_fuse_stacks(render, stack_DAG, validstack, tmpdir):
    FuseStacksModule = asap.fusion.fuse_stacks.FuseStacksModule
    example_parameters = asap.fusion.fuse_stacks.example_parameters

    distance_thres = 1.  # central distance threshold in pixels

    # stack_DAG uses render-python objects
    input_DAG = json.loads(renderapi.utils.renderdumps(stack_DAG))

    test_input = dict(example_parameters, **{
        'render': render.make_kwargs(),
        'stacks': input_DAG,
        'output_stack': 'fuse_stacks_test'})

    outputfn = os.path.join(str(tmpdir), "fuse_stack_out.json")
    fs = FuseStacksModule(input_data=test_input,
                          args=['--output_json', outputfn])
    fs.run()

    with open(fs.args['output_json'], 'r') as f:
        outd = json.load(f)

    compare_stacks_tilecenters(
        render, outd['stack'], validstack, distance_thres=distance_thres)


def test_skip_fusion(render, stack_DAG, validstack, tmpdir):
    # stack_DAG uses render-python objects
    input_DAG = json.loads(renderapi.utils.renderdumps(stack_DAG))

    test_input = dict(asap.fusion.fuse_stacks.example_parameters, **{
        'render': render.make_kwargs(),
        'stacks': input_DAG,
        'output_stack': 'fuse_stacks_skipping_test'})

    def getallnodes(dag):
        for n in dag['children']:
            yield n
            getallnodes(n)

    allnodes = [n for n in getallnodes(input_DAG)]

    skippednode = random.choice(allnodes)
    skippednode['fuse_stack'] = False

    skippedzs = set(renderapi.stack.get_z_values_for_stack(
        skippednode['stack'], render=render))
    allzs = set(renderapi.stack.get_z_values_for_stack(
        validstack, render=render))

    outputfn = os.path.join(str(tmpdir), "fuse_stack_skipout.json")
    fs = asap.fusion.fuse_stacks.FuseStacksModule(
        input_data=test_input, args=['--output_json', outputfn])
    fs.run()

    with open(fs.args['output_json'], 'r') as f:
        outd = json.load(f)

    outzs = set(renderapi.stack.get_z_values_for_stack(
        outd['stack'], render=render))
    assert not outzs & skippedzs

    compare_stacks_tilecenters(render, outd['stack'], validstack,
                               testzs=allzs.difference(skippedzs))
