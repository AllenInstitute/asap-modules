import os
import pytest
import logging
import renderapi
import json
import glob
import subprocess
import mock
from test_data import (RAW_STACK_INPUT_JSON,
                      log_dir,
                      render_params,
                      montage_project,
                      montage_z,
                      test_em_montage_parameters as solver_example,
                      test_pointmatch_parameters as pointmatch_example)

from rendermodules.montage.run_montage_job_for_section import  SolveMontageSectionModule
from rendermodules.pointmatch.create_tilepairs import TilePairClientModule
from rendermodules.pointmatch.generate_point_matches_spark import PointMatchClientModuleSpark
from rendermodules.pointmatch.generate_point_matches_qsub import PointMatchClientModuleQsub
from rendermodules.module.render_module import RenderModuleException
logger = renderapi.client.logger
logger.setLevel(logging.DEBUG)

@pytest.fixture(scope='module')
def render():
    render_params['project'] = montage_project
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
        "minZ": montage_z,
        "maxZ": montage_z,
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
def test_point_match_generation(render, test_create_montage_tile_pairs,tmpdir_factory):
    output_directory = str(tmpdir_factory.mktemp('output_json'))
    pointmatch_example['output_json']=os.path.join(output_directory,'output.json')
    pointmatch_example['pairJson'] = test_create_montage_tile_pairs
    mod = PointMatchClientModuleSpark(input_data=pointmatch_example,args=[])
    mod.run()
    with open(pointmatch_example['output_json'],'r') as fp:
        output_d = json.load(fp)
    assert (output_d['pairCount']>0)
    yield pointmatch_example['collection']

def mock_suprocess_qsub_call(cmd):
    print(cmd)
    raise subprocess.CalledProcessError('fake call failed')

@mock.patch('subprocess.check_call', side_effect=mocked_requests_get)
def test_point_match_generation_qsub(render, test_create_montage_tile_pairs, tmpdir_factory):
    output_directory = str(tmpdir_factory.mktemp('output_json'))

    pointmatch_example['output_json']=os.path.join(output_directory,'output.json')
    pointmatch_example['pairJson'] = test_create_montage_tile_pairs
    mod = PointMatchClientModuleQsub(input_data=pointmatch_example,args=[])
    mod.run()


def test_run_montage_job_for_section(render,
                                     raw_stack,
                                     test_point_match_generation,
                                     tmpdir_factory,
                                     output_stack=None):
    if output_stack is None:
        output_stack = '{}_Montage'.format(raw_stack)
    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_example['output_json']=os.path.join(output_directory,'output.json')
    solver_example['source_collection']['stack'] = raw_stack
    solver_example['target_collection']['stack'] = output_stack
    solver_example['source_point_match_collection']['match_collection'] = test_point_match_generation
    solver_example['z_value'] = montage_z

    mod = SolveMontageSectionModule(input_data=solver_example, args=[])
    mod.run()

    # check if z value exists
    zvalues = renderapi.stack.get_z_values_for_stack(output_stack, render=render)

    assert len(zvalues) == 1
    assert solver_example['z_value'] == zvalues[0]

    # check the number of tiles in the montage
    tilespecs = renderapi.tilespec.get_tile_specs_from_z(output_stack, solver_example['z_value'], render=render)
    assert len(tilespecs) == 4

def test_fail_montage_job_for_section(render,
                                     raw_stack,
                                     test_point_match_generation,
                                     tmpdir_factory,
                                     output_stack=None):
    if output_stack is None:
        output_stack = '{}_Montage'.format(raw_stack)
    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_example['output_json']=os.path.join(output_directory,'output.json')
    solver_example['source_collection']['stack'] = raw_stack
    solver_example['target_collection']['stack'] = output_stack
    solver_example['source_point_match_collection']['match_collection'] = 'notacollection'
    solver_example['z_value'] = montage_z
    with pytest.raises(RenderModuleException):
        mod = SolveMontageSectionModule(input_data=solver_example, args=[])
        mod.run()
