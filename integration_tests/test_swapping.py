import pytest
import renderapi

from test_data import (render_params,
                       swap_z_tspecs1,
                       swap_z_tspecs2,
                       swap_pt_matches1,
                       swap_pt_matches2)
from rendermodules.module.render_module import RenderModuleException
from rendermodules.stack import swap_zs
from rendermodules.pointmatch.swap_point_match_collections import (
    SwapPointMatchesModule)


@pytest.fixture(scope='module')
def render():
    render_params['project'] = 'swapping_test'
    render = renderapi.connect(**render_params)
    return render


@pytest.fixture(scope='module')
def source_tspecs():
    source_ts = [renderapi.tilespec.TileSpec(json=d)
                 for d in swap_z_tspecs1]
    return source_ts


@pytest.fixture(scope='module')
def target_tspecs():
    target_ts = [renderapi.tilespec.TileSpec(json=d)
                 for d in swap_z_tspecs2]
    return target_ts


@pytest.fixture(scope='module')
def source_stack(render, source_tspecs):
    source_stack_name = "source_stack"
    renderapi.stack.create_stack(source_stack_name, render=render)
    renderapi.client.import_tilespecs(
        source_stack_name, source_tspecs, render=render)
    renderapi.stack.set_stack_state(
        source_stack_name, 'COMPLETE', render=render)

    yield source_stack_name
    render.run(renderapi.stack.delete_stack, source_stack_name)


@pytest.fixture(scope='module')
def target_stack(render, target_tspecs):
    target_stack_name = "target_stack"
    renderapi.stack.create_stack(target_stack_name, render=render)
    renderapi.client.import_tilespecs(
        target_stack_name, target_tspecs, render=render)
    renderapi.stack.set_stack_state(
        target_stack_name, 'COMPLETE', render=render)

    yield target_stack_name
    render.run(renderapi.stack.delete_stack, target_stack_name)


@pytest.fixture(scope='module')
def pt_matches1(render):
    match_collection1 = "collection1"
    pt_matches = [d for d in swap_pt_matches1]
    renderapi.pointmatch.import_matches(match_collection1,
                                        pt_matches,
                                        render=render)
    yield match_collection1
    render.run(renderapi.pointmatch.delete_collection, match_collection1)


@pytest.fixture(scope='module')
def pt_matches2(render):
    match_collection2 = "collection2"
    pt_matches = [d for d in swap_pt_matches2]
    renderapi.pointmatch.import_matches(match_collection2,
                                        pt_matches,
                                        render=render)
    yield match_collection2
    render.run(renderapi.pointmatch.delete_collection, match_collection2)


def test_swap_z_module(
        render, source_stack, target_stack, source_tspecs, target_tspecs):
    ex = {
        "render": render_params,
        "source_stack": [source_stack],
        "target_stack": [target_stack],
        "zValues": [[1015]],
        "delete_source_stack": "False"
    }

    mod = swap_zs.SwapZsModule(
        input_data=ex, args=['--output_json', 'output.json'])
    mod.run()

    # assert that both the stack exist
    list_of_stacks = renderapi.render.get_stacks_by_owner_project(
        host=render.DEFAULT_HOST,
        port=render.DEFAULT_PORT,
        owner=render.DEFAULT_OWNER,
        project=render.DEFAULT_PROJECT,
        render=render)

    assert(source_stack in list_of_stacks and target_stack in list_of_stacks)

    source_tileids = [ts.tileId for ts in source_tspecs]
    target_tileids = [ts.tileId for ts in target_tspecs]

    tspecs1 = renderapi.stack.get_stack_tileIds(source_stack, render=render)
    tspecs2 = renderapi.stack.get_stack_tileIds(target_stack, render=render)

    assert(ts.tileId in target_tileids for ts in tspecs1)
    assert(ts.tileId in source_tileids for ts in tspecs2)

    ex['source_stack'] = [source_stack, target_stack]
    ex['target_stack'] = [target_stack]

    mod = swap_zs.SwapZsModule(
        input_data=ex, args=['--output_json', 'output.json'])

    # check if the number of source_stacks and # of
    #   target_stacks match for swapping
    with pytest.raises(RenderModuleException):
        mod.run()

    ex['target_stack'] = [target_stack, source_stack]
    ex['zValues'] = [[1015], [1015]]
    ex['complete_source_stack'] = "True"
    ex['complete_target_stack'] = "True"

    mod = swap_zs.SwapZsModule(
        input_data=ex, args=['--output_json', 'output.json'])
    mod.run()

    assert(ts.tileId in source_tileids for ts in tspecs1)
    assert(ts.tileId in target_tileids for ts in tspecs2)


def test_swap_pt_matches_module(render, pt_matches1, pt_matches2):
    example = {
        "render": render_params,
        "match_owner": render.DEFAULT_OWNER,
        "source_collection": pt_matches1,
        "target_collection": pt_matches2,
        "zValues": [1015]
    }

    sgroupIds = renderapi.pointmatch.get_match_groupIds(
        pt_matches1,
        owner=example['match_owner'],
        render=render)
    tgroupIds = renderapi.pointmatch.get_match_groupIds(
        pt_matches2,
        owner=example['match_owner'],
        render=render)

    source_pIds = []
    target_pIds = []
    for sg in sgroupIds:
        matches = renderapi.pointmatch.get_matches_with_group(
            pt_matches1,
            sg,
            owner=example['match_owner'],
            render=render)
        for m in matches:
            source_pIds.append(m['pId'])

    for tg in tgroupIds:
        matches = renderapi.pointmatch.get_matches_with_group(
            pt_matches2,
            tg,
            owner=example['match_owner'],
            render=render)
        for m in matches:
            target_pIds.append(m['pId'])

    mod = SwapPointMatchesModule(
        input_data=example, args=['--output_json', 'out.json'])
    mod.run()

    # get pIds from swapped collections
    new_source_pIds = []
    new_target_pIds = []

    matches = renderapi.pointmatch.get_matches_with_group(
        pt_matches1, '1015.0', owner=example['match_owner'], render=render)
    new_source_pIds = [m['pId'] for m in matches]

    matches = renderapi.pointmatch.get_matches_with_group(
        pt_matches2, '1015.0', owner=example['match_owner'], render=render)
    new_target_pIds = [m['pId'] for m in matches]

    assert([spId in new_target_pIds for spId in source_pIds])
    assert([tpId in new_source_pIds for tpId in target_pIds])
