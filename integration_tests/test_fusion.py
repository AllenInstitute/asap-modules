'''
Test stack fusion by affine-based registration and transform interpolation
'''
import json
import numpy
import renderapi
import logging
import pytest
from test_data import FUSION_JSON, render_params

render_params['project'] = 'fusion_test'

logger = renderapi.client.logger
logger.setLevel(logging.DEBUG)


@pytest.fixture(scope='module')
def render():
    render = renderapi.connect(**render_params)
    return render


@pytest.fixture(scope='module')
def test_tilespecs():
    return [renderapi.tilespec.TileSpec(json=d) for d in FUSION_JSON]


@pytest.fixture(scope='module')
def validstack(test_tilespecs, render):
    """Stack defined by original tilespecs -- coordinates
    in fused stack should match this"""
    stackname = 'validstack_renderfusion'
    renderapi.stack.create_stack(stackname, render=render)
    renderapi.client.import_tilespecs_parallel(
        stackname, test_tilespecs, render=render)
    yield stackname
    renderapi.stack.delete_stack(stackname, render=render)


@pytest.fixture(scope='module')
def stack_DAG(test_tilespecs, render, root_index=2):
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
            childnode = nd['children']
        return childnode

    # build DAG by generating children on either side of root node
    dag = nodes[root_index]
    forwardchild = buildchildren(nodes[root_index+1:])
    backwardchild = buildchildren(nodes[:root_index][::-1])

    if forwardchild is not None:
        dag['children'].append(forwardchild)
    if backwardchild is not None:
        dag['children'].append(backwardchild)

    # build stacks based on DAG relations
    def build_childstacks(nodelist, nodezs, tspecs, r):
        last_tform = renderapi.transform.AffineModel()
        for child, zs in zip(nodelist, nodezs):
            last_tform = last_tform.concatenate(child['transform'])
            ztspecs = [ts for ts in tspecs if ts.z in zs]
            renderapi.stack.create_stack(child['stack'], render=r)
            renderapi.client.import_tilespecs_parallel(
                child['stack'], ztspecs, close_stack=False, render=r)
            renderapi.client.transformSectionClient(
                child['stack'], '{}_tform'.format(child['stack']),
                last_tform.className, last_tform.dataString.replace(' ', ','),
                zValues=zs, render=r)
            renderapi.stack.set_stack_state(
                child['stack'], 'COMPLETE', render=r)

    build_childstacks(
        nodes[root_index+1:], stackzs[root_index+1:], test_tilespecs, render)
    build_childstacks(
        nodes[:root_index][::-1], stackzs[:root_index][::-1],
        test_tilespecs, render)

    yield dag

    # remove all stacks associated with DAG
    for nd in nodes:
        renderapi.stack.delete_stack(nd['stack'], render=render)


def get_random_rigid_tform(max_translation_tuple=(10000, 20000)):
    # random translation
    x, y = numpy.array(max_translation_tuple) * numpy.random.rand(2)
    translate_tform = renderapi.transform.AffineModel(B0=x, B1=y)
    # random rotation
    theta = numpy.random.rand() * 2 * numpy.pi
    rotate_tform = renderapi.transform.AffineModel(
        M00=numpy.cos(theta), M01=-numpy.sin(theta),
        M10=numpy.sin(theta), M11=numpy.cos(theta))
    return translate_tform.concatenate(rotate_tform)


def test_register_stacks(render, stack_DAG):
    from rendermodules.fusion.register_adjacent_stack import (
        RegisterSubvolumeModule, example_parameters)

    parentstack = stack_DAG['stack']
    child = stack_DAG['children'][0]
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

    with open(rms.output_json, 'r') as f:
        outd = json.load(f)

    estimated_tform = renderapi.transform.load_transform_json(
        outd['transform'])
    assert numpy.allclose(estimated_tform.M, tform.M)
    assert outd['stack_a'] == parentstack
    assert outd['stack_b'] == childstack


def test_fuse_stacks(render, stack_DAG, validstack):
    from rendermodules.fusion.fuse_stacks import (
        FuseStacksModule, example_parameters)
    distance_thres = 5  # central distance threshold in pixels

    # stack_DAG uses render-python objects
    input_DAG = json.loads(renderapi.utils.renderdumps(stack_DAG))

    test_input = dict(example_parameters, **{
        'render': render.make_kwargs(),
        'stacks': input_DAG,
        'output_stack': 'fuse_stacks_test'})
    fs = FuseStacksModule(input_data=test_input,
                          args=['--output_json', 'fuse_stack_out.json'])
    fs.run()

    with open(fs.output_json, 'r') as f:
        outd = json.load(f)

    validzs = set(renderapi.stack.get_z_values_for_stack(
        validstack, render=render))
    zs = set(renderapi.stack.get_z_values_for_stack(
        outd['stack'], render=render))

    # assure zs are shared
    assert not zs.symmetric_difference(validzs)

    for z in zs:
        created_tId_to_tile = {
            ts.tileId: ts for ts in
            renderapi.tilespec.get_tile_specs_from_z(
                outd['stack'], z, render=render)}

        valid_tId_to_tile = {
            ts.tileId: ts for ts in renderapi.tilespec.get_tile_specs_from_z(
                validstack, z, render=render)}

        # assure all tiles are represented
        assert not (
            valid_tId_to_tile.viewkeys() ^ created_tId_to_tile.viewkeys())

        # assert that all tile centers are within distance threshold
        created_centerpoint_l2w_in = []
        valid_centerpoint_l2w_in = []
        for tileId, tile in created_tId_to_tile.iteritems():
            validtile = valid_tId_to_tile[tileId]

            created_centerpoint_l2w_in.append(
                {'tileId': tileId, 'visible': False,
                 'local': [tile.width // 2, tile.height // 2]})

            valid_centerpoint_l2w_in.append(
                {'tileId': tileId, 'visible': False,
                 'local': [validtile.width // 2, validtile.height // 2]})
        wc_valid = renderapi.coordinate.local_to_world_coordinates_batch(
            validstack, valid_centerpoint_l2w_in, z, number_of_threads=5,
            render=render)
        wc_created = renderapi.coordinate.local_to_world_coordinates_batch(
            outd['stack'], created_centerpoint_l2w_in, z, number_of_threads=5,
            render=render)

        validcoord = numpy.array([d['world'][:2] for d in wc_valid])
        createdcoord = numpy.array(d['world'][:2] for d in wc_created)

        assert (numpy.linalg.norm(
            validcoord - createdcoord, axis=1).max() < distance_thres)
