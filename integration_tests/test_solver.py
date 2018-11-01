import pytest
import renderapi
import json
import os
from rendermodules.solver.solve import Solve_stack
from test_data import (render_params,
                       example_dir,
                       solver_montage_parameters)

FILE_RAW_TILES = os.path.join(example_dir, 'solver_raw_tiles_for_montage.json')
FILE_PMS = os.path.join(example_dir, 'solver_montage_pointmatches.json')


@pytest.fixture(scope='module')
def render():
    render_params['project'] = \
            solver_montage_parameters['input_stack']['project']
    render = renderapi.connect(**render_params)
    return render


@pytest.fixture(scope='module')
def raw_stack(render):
    test_raw_stack = 'solver_input_raw_stack'
    ts = []
    with open(FILE_RAW_TILES, 'r') as f:
        ts = json.load(f)

    tilespecs = [renderapi.tilespec.TileSpec(json=d) for d in ts]
    renderapi.stack.create_stack(test_raw_stack, render=render)
    renderapi.client.import_tilespecs(test_raw_stack, tilespecs, render=render)
    renderapi.stack.set_stack_state(test_raw_stack, 'COMPLETE', render=render)
    yield test_raw_stack
    renderapi.stack.delete_stack(test_raw_stack, render=render)


@pytest.fixture(scope='module')
def montage_pointmatches(render):
    test_montage_collection = 'montage_collection'
    pms_from_json = []
    with open(FILE_PMS, 'r') as f:
        pms_from_json = json.load(f)

    renderapi.pointmatch.import_matches(
            test_montage_collection, pms_from_json, render=render)
    yield test_montage_collection


def one_solve(parameters, precision=1e-7):
    mod = Solve_stack(input_data=parameters, args=[])
    mod.run()
    assert mod.module.results['precision'] < precision
    assert mod.module.results['error'] < 200
    with open(parameters['output_json'], 'r') as f:
        output_d = json.load(f)
    assert output_d['stack'] == parameters['output_stack']['name']


def test_solver_montage_test(render, montage_pointmatches, raw_stack, tmpdir):
    output_dir = str(tmpdir)
    parameters = dict(solver_montage_parameters)
    parameters['input_stack']['name'] = raw_stack
    parameters['pointmatch']['name'] = montage_pointmatches
    parameters['output_json'] = os.path.join(output_dir, "montage_solve.json")

    # affine half size
    parameters['transformation'] = "AffineModel"
    parameters['fullsize_transform'] = False
    one_solve(parameters)

    # try with affine_fullsize
    parameters['output_json'] = os.path.join(
            output_dir, "affine_fullsize.json")
    parameters['transformation'] = "AffineModel"
    parameters['fullsize_transform'] = True
    one_solve(parameters)

    # try with render interface
    parameters['output_json'] = os.path.join(
            output_dir, 'renderinterface.json')
    parameters['input_stack']['db_interface'] = 'render'
    parameters['pointmatch']['db_interface'] = 'render'
    one_solve(parameters)

    # try with similarity and polynomial
    parameters['transformation'] = "SimilarityModel"
    one_solve(parameters)

    parameters['transformation'] = "Polynomial2DTransform"
    parameters['poly_order'] = 2
    # for poly_order=2, similar regularizations work
    # for poly_order > 2, need to tweak regularization
    one_solve(parameters, precision=1e-3)

    parameters['transformation'] = "Polynomial2DTransform"
    parameters['poly_order'] = 2
    parameters['regularization']['poly_factors'] = [1e-5, 1.0, 1e6]
    one_solve(parameters, precision=1e-3)
