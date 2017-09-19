import renderapi
from rendermodules.stack.consolidate_transforms import ConsolidateTransforms, process_z
from test_data import render_host,render_port,client_script_location, tilespec_file, tform_file
import pytest
import numpy as np
import json
import logging

EPSILON = .001
render_params = {
    "host":render_host,
    "port":render_port,
    "owner":"test",
    "project":"consolidate_test",
    "client_scripts":client_script_location
}


@pytest.fixture(scope='module')
def render():
    render = renderapi.connect(**render_params)
    return render

@pytest.fixture(scope='module')
def render_example_tilespec_and_transforms():
    with open(tilespec_file, 'r') as f:
        ts_json = json.load(f)
    with open(tform_file, 'r') as f:
        tform_json = json.load(f)

    tilespecs = [renderapi.tilespec.TileSpec(json=ts) for ts in ts_json]
    tforms = [renderapi.transform.load_transform_json(td) for td in tform_json]
    print tforms
    return (tilespecs, tforms)

@pytest.fixture(scope='module')
def test_stack(render,render_example_tilespec_and_transforms):
    (tilespecs, tforms) = render_example_tilespec_and_transforms
    new_affine = renderapi.transform.AffineModel(3.0,0.0,0.0,3.0,0,0)
    [ts.tforms.append(new_affine) for ts in tilespecs]
    stack = 'test_stack'
    renderapi.stack.create_stack(stack, render=render)
    renderapi.client.import_tilespecs('test_stack',tilespecs,tforms,render=render)
    yield stack
    renderapi.stack.delete_stack(stack, render=render)

@pytest.fixture(scope='module')
def test_consolidate_module(render,test_stack):
    output_stack = test_stack + "_CONS"
    input_z = np.array(renderapi.stack.get_z_values_for_stack(test_stack,render=render))
    print input_z
    params = {
        "render":render_params,
        "stack": test_stack,
        "output_stack": output_stack,
        "transforms_slice" : "1:",
        "pool_size": 2,
        "minZ":input_z[1],
        "maxZ":np.max(input_z),
        "output_json":"test.json"
    }
    
    mod = ConsolidateTransforms(input_data = params,args=[])
    mod.run()

    output_z = np.array(renderapi.stack.get_z_values_for_stack(output_stack,render=render))
    assert(input_z[0] not in output_z)
    assert(len(output_z)==len(input_z)-1)

    #make sure the input_tilespecs are correct
    input_tilespecs = renderapi.tilespec.get_tile_specs_from_stack(test_stack, render=render)   
    # 2lens correction, 2 affines
    assert all([len(ts.tforms)==4 for ts in input_tilespecs])

    #make sure the output_tilespecs have the right number of transforms
    output_tilespecs = renderapi.tilespec.get_tile_specs_from_stack(output_stack, render=render)   
    #2 lens correction, 1 combined affine
    assert all([len(ts.tforms)==3 for ts in output_tilespecs])

    input_tilespec = renderapi.tilespec.get_tile_spec(test_stack,output_tilespecs[0].tileId, render=render)
    orig_tform = input_tilespec.tforms[2]
    cons_tform = output_tilespecs[0].tforms[2]
    expected_new=renderapi.transform.AffineModel(3.0,0,0,3.0,0,0).concatenate(orig_tform)
    print input_tilespec.tforms
    print orig_tform.M
    print cons_tform.M
    for orig_elem,new_elem in zip(np.ravel(expected_new.M),np.ravel(cons_tform.M)):
        assert(np.abs(orig_elem - new_elem)<EPSILON)

    return mod

def test_consolidate_single(render,test_stack,test_consolidate_module):
    (tilespecs, tforms)=process_z(render, 
              test_consolidate_module.logger,
              test_consolidate_module['input_stack'],
              test_consolidate_module['output_stack'],
              test_consolidate_module['transforms_slice'],
              0.0)