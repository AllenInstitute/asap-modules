import os
import pytest
import renderapi
import json

import mock
import numpy as np
from test_data import (
    RAW_STACK_INPUT_JSON,
    render_params,
    montage_z,
    solver_montage_parameters,
    test_pointmatch_parameters as pointmatch_example,
    test_pointmatch_parameters_qsub as pointmatch_example_qsub)

from asap.solver.solve import Solve_stack
from asap.pointmatch.create_tilepairs import TilePairClientModule
from asap.pointmatch.generate_point_matches_spark import (
    PointMatchClientModuleSpark)
from asap.pointmatch.generate_point_matches_qsub import (
    PointMatchClientModuleQsub)


@pytest.fixture(scope='module')
def render():
    render_params['project'] = solver_montage_parameters[
        'input_stack']['project']
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
    with open(params['output_json'], 'r') as fp:
        out_d = json.load(fp)
    tilepair_file = out_d['tile_pair_file']

    assert(os.path.exists(tilepair_file) and
           os.path.getsize(tilepair_file) > 0)

    with open(tilepair_file, 'r') as f:
        js = json.load(f)
    npairs = js['neighborPairs']
    assert(len(npairs) == 4)
    yield tilepair_file


def test_create_montage_tile_pairs_no_z(render, raw_stack, tmpdir):
    output_directory = str(tmpdir.join('Montage'))
    params = {
        "render": render_params,
        "zNeighborDistance": 0,
        "xyNeighborFactor": 0.9,
        "excludeCornerNeighbors": "true",
        "excludeSameLayerNeighbors": "false",
        "excludeCompletelyObscuredTiles": "true",
        "output_dir": output_directory,
        "stack": raw_stack,
        "output_json": "out.json"
    }

    mod = TilePairClientModule(input_data=params, args=[])
    mod.run()

    # check if the file has been created
    with open(params['output_json'], 'r') as fp:
        out_d = json.load(fp)
    tilepair_file = out_d['tile_pair_file']

    assert(os.path.exists(tilepair_file) and
           os.path.getsize(tilepair_file) > 0)

    with open(tilepair_file, 'r') as f:
        js = json.load(f)
    npairs = js['neighborPairs']
    assert(len(npairs) == 4)


@pytest.fixture(scope='module')
def test_point_match_generation(
        render, test_create_montage_tile_pairs, tmpdir_factory):
    output_directory = str(tmpdir_factory.mktemp('output_json'))
    pointmatch_example['output_json'] = os.path.join(
        output_directory, 'output.json')
    pointmatch_example['pairJson'] = test_create_montage_tile_pairs
    mod = PointMatchClientModuleSpark(input_data=pointmatch_example, args=[])
    mod.run()
    with open(pointmatch_example['output_json'], 'r') as fp:
        output_d = json.load(fp)
    assert (output_d['pairCount'] > 0)
    yield pointmatch_example['collection']


class MockSubprocessException(Exception):
    pass


def mock_suprocess_qsub_call(cmd):
    print(cmd)
    raise MockSubprocessException('fake subprocess call')


@mock.patch('subprocess.check_call', side_effect=mock_suprocess_qsub_call)
def test_point_match_generation_qsub(
        render, test_create_montage_tile_pairs, tmpdir_factory):
    output_directory = str(tmpdir_factory.mktemp('output_json'))

    pointmatch_example_qsub['output_json'] = os.path.join(
        output_directory, 'output.json')
    pointmatch_example_qsub['pairJson'] = test_create_montage_tile_pairs
    mod = PointMatchClientModuleQsub(
        input_data=pointmatch_example_qsub, args=[])
    with pytest.raises(MockSubprocessException):
        mod.run()


def test_montage_solver(
        render, raw_stack, test_point_match_generation, tmpdir_factory):
    output_directory = str(tmpdir_factory.mktemp('output_json'))

    parameters = dict(solver_montage_parameters)
    parameters['input_stack']['name'] = raw_stack
    parameters['pointmatch']['name'] = test_point_match_generation
    parameters['pointmatch']['db_interface'] = 'render'
    parameters['input_stack']['db_interface'] = 'render'
    parameters['output_json'] = os.path.join(
        output_directory, "montage_solve.json")

    # affine half size
    parameters['transformation'] = "AffineModel"
    parameters['fullsize_transform'] = False

    mod = Solve_stack(input_data=parameters, args=[])
    mod.run()

    precision = 1e-7
    assert np.all(np.array(mod.module.results['precision']) < precision)
    assert np.all(np.array(mod.module.results['error'])) < 200
    with open(parameters['output_json'], 'r') as f:
        output_d = json.load(f)

    assert parameters['output_stack']['name'][0] == output_d['stack']
