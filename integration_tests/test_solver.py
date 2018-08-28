import pytest
import renderapi
import json
import os
from EMaligner import EMaligner
from rendermodules.solver.solve import Solve_stack
from test_data import (render_params,
                       render_json_template,
                       example_env,
                       example_dir,
                       solver_montage_parameters)

#FILE_RAW_TILES = './integration_tests/test_files/solver_raw_tiles_for_montage.json'
#FILE_PMS = './integration_tests/test_files/solver_montage_pointmatches.json'

FILE_RAW_TILES = os.path.join(example_dir, 'solver_raw_tiles_for_montage.json')
FILE_PMS = os.path.join(example_dir, 'solver_montage_pointmatches.json')

@pytest.fixture(scope='module')
def render():
    render_params['project'] = solver_montage_parameters['input_stack']['project']
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

    renderapi.pointmatch.import_matches(test_montage_collection, pms_from_json, render=render)
    yield test_montage_collection

def test_solver_montage_test(render, montage_pointmatches, raw_stack, tmpdir):
    output_dir = str(tmpdir)
    solver_montage_parameters['input_stack']['name'] = raw_stack
    solver_montage_parameters['pointmatch']['name'] = montage_pointmatches

    montage_fn = os.path.join(output_dir, "montage_solve.json")
    mod = Solve_stack(input_data=solver_montage_parameters,
                      args=['--output_json', montage_fn])
    mod.run()
    assert mod.module.results['precision'] < 1e-7
    assert mod.module.results['error'] < 200

    # try with affine_fullsize
    afffull_fn = os.path.join(output_dir, "affine_fullsize.json")
    solver_montage_parameters['transformation'] = "affine_fullsize"
    mod = Solve_stack(input_data=solver_montage_parameters,
                      args=["--output_json", afffull_fn])
    mod.run()
    assert mod.module.results['precision'] < 1e-7
    assert mod.module.results['error'] < 200

    # try with render interface
    renderinterface_fn = os.path.join(output_dir, 'renderinterface.json')
    solver_montage_parameters['input_stack']['db_interface'] = 'render'
    solver_montage_parameters['pointmatch']['db_interface'] = 'render'
    mod = Solve_stack(input_data=solver_montage_parameters,
                      args=["--output_json", renderinterface_fn])
    mod.run()
    assert mod.module.results['precision'] < 1e-7
    assert mod.module.results['error'] < 200

    with open(renderinterface_fn, 'r') as f:
        output_d = json.load(f)
    assert output_d['stack'] == solver_montage_parameters['output_stack']['name']
    assert output_d['backup_stack'][0] == solver_montage_parameters['output_stack']['name']

    # run montaging again with clone section option
    solver_montage_parameters['clone_section'] = "True"
    solver_montage_parameters['overwrite_z'] = "False"

    mod = Solve_stack(input_data=solver_montage_parameters, args=["--output_json", renderinterface_fn])
    mod.run()

    with open(renderinterface_fn, "r") as f:
        output_d = json.load(f)
    assert not (output_d['stack'] == output_d['backup_stack'][0])

