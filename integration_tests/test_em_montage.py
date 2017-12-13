import os
import pytest
import logging
import renderapi
import json
import glob
from test_data import (RAW_STACK_INPUT_JSON, MONTAGE_SOLVER_EXECUTABLE, log_dir, render_params)

from rendermodules.montage.run_montage_job_for_section import example as solver_example, SolveMontageSectionModule
from rendermodules.pointmatch.create_tilepairs import TilePairClientModule
from rendermodules.pointmatch.generate_point_matches_spark import PointMatchClientModuleSpark, example as pointmatch_example

logger = renderapi.client.logger
logger.setLevel(logging.DEBUG)

render_params['project'] = 'em_montage_test'

@pytest.fixture(scope='module')
def render():
    render = renderapi.connect(**render_params)
    return render

@pytest.fixture(scope='module')
def tspecs_from_json():
    tilespecs = [renderapi.tilespec.TileSpec(json=d)
                    for d in RAW_STACK_INPUT_JSON]
    return tilespecs

# raw stack with lens correction and intensity correction done
@pytest.fixture(scope='module')
def raw_stack(render, tspecs_from_json):
    test_raw_stack = 'input_raw_stack'
    renderapi.stack.create_stack(
                        test_raw_stack,
                        render=render)
    renderapi.client.import_tilespecs(
                        test_raw_stack,
                        tspecs_from_json,
                        render=render)
    renderapi.stack.set_stack_state(
                        test_raw_stack,
                        'COMPLETE',
                        render=render)
    yield test_raw_stack
    renderapi.stack.delete_stack(
                        test_raw_stack,
                        render=render)

@pytest.fixture(scope='module')
def test_create_montage_tile_pairs(render, raw_stack, tmpdir_factory):
    output_directory = str(tmpdir_factory.mktemp('Montage'))
    params = {
        "render": render_params,
        "zNeighborDistance": 0,
        "xyNeighborFactor": 0.9,
        "excludeCornerNeighbors": "true",
        "excludeSameLayerNeighbors": "false",
        "excludeCompletelyObscuredTiles": "true",
        "minZ": 1015,
        "maxZ": 1015,
        "output_dir": output_directory,
        "stack": raw_stack,
        "output_json": "out.json"
    }

    mod = TilePairClientModule(input_data=params, args=[])
    mod.run()

    # check if the file has been created
    tilepair_file = "tile_pairs_{}_z_{}_to_{}_dist_{}.json".format(
                        raw_stack,
                        params['minZ'],
                        params['maxZ'],
                        params['zNeighborDistance'])
    tilepair_file = os.path.join(output_directory, tilepair_file)

    assert(os.path.exists(tilepair_file) and os.path.getsize(tilepair_file) > 0)

    with open(tilepair_file, 'r') as f:
        js = json.load(f)
    npairs = js['neighborPairs']
    assert(len(npairs) > 0)
    yield tilepair_file

@pytest.fixture(scope='module')
def test_point_match_generation(render, test_create_montage_tile_pairs):
    pt_match_collection = 'montage_align_point_matches'
    jarfile = glob.glob('/shared/render/render-ws-spark-client/target/render-ws-spark-client*SNAPSHOT-standalone.jar')
    pointmatch_example['render'] = render_params
    pointmatch_example['pairJson'] = test_create_montage_tile_pairs
    pointmatch_example['owner'] = render_params['owner']
    pointmatch_example['collection'] = pt_match_collection
    pointmatch_example['sparkhome'] = os.environ['SPARK_HOME']
    pointmatch_example['masterUrl'] = os.environ['MASTER']
    pointmatch_example['jarfile'] = jarfile
    pointmatch_example['baseDataUrl'] = '{}:{}/render-ws/v1'.format(render_params['host'], render_params['port'])

    mod = PointMatchClientModuleSpark(input_data=pointmatch_example)
    mod.run()

    yield pt_match_collection

def test_run_montage_job_for_section(render, raw_stack, test_point_match_generation, tmpdir_factory, output_stack=None):
    if output_stack is None:
        output_stack = '{}_Montage'.format(raw_stack)

    scratch_directory = str(tmpdir_factory.mktemp('scratch'))
    solver_example['render'] = render_params
    solver_example['source_collection']['stack'] = raw_stack
    solver_example['target_collection']['stack'] = output_stack
    solver_example['source_point_match_collection']['match_collection'] = test_point_match_generation

    solver_example['temp_dir'] = scratch_directory
    solver_example['scratch'] = scratch_directory
    solver_example['z_value'] = 1015

    mod = SolveMontageSectionModule(input_data=solver_example, args=[])
    mod.run()

    # check if z value exists
    zvalues = renderapi.stack.get_z_values_for_stack(output_stack, render=render)

    assert len(zvalues) == 1
    assert solver_example['z_value'] == zvalues[0]

    # check the number of tiles in the montage
    tilespecs = renderapi.tilespec.get_tile_specs_from_z(output_stack, solver_example['z_value'], render=render)
    assert len(tilespecs) == 4
