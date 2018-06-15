import os 
import pytest 
import logging 
import renderapi
import json

from test_data import render_params, example_env, render_json_template, TEST_DATA_ROOT
from rendermodules.module.render_module import RenderModuleException
from rendermodules.registration.register_sections import *

logger = renderapi.client.logger
logger.setLevel(logging.DEBUG)

example = {
    "render": {
        'host':'em-131db',
        'port':8080,
        'owner':"TEM",
        'project':"247488_8R",
        'client_scripts':"/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
        'memGB':'2G'
    },
    "reference_stack": "reference_stack",
    "moving_stack": "moving_stack",
    "output_stack": "output_stack",
    "match_collection": "rough_align_fixes",
    "regsitration_model": "Affine",
    "reference_z": 133,
    "moving_z": 133,
    "overwrite_output": True,
    "consolidate_transforms": True
}

REF_STACK_TSPECS = render_json_template(example_env, 'rough_registration_ref_stack_tspecs.json',
                                        test_data_root=TEST_DATA_ROOT)

MOVING_STACK_TSPECS = render_json_template(example_env, 'rough_registration_moving_stack_tspecs.json',
                                        test_data_root=TEST_DATA_ROOT)

POINT_MATCHES = render_json_template(example_env, 'rough_registration_point_matches.json',
                                        test_data_root=TEST_DATA_ROOT)


@pytest.fixture(scope='module')
def render():
    render_params['project'] = 'rough_registration'  
    render = renderapi.connect(**render_params)
    return render

@pytest.fixture(scope='module')
def reference_stack(render):
    tilespecs = [renderapi.tilespec.TileSpec(json=d) 
                    for d in REF_STACK_TSPECS]
    ref_stack = "reference_stack"
    
    renderapi.stack.create_stack(ref_stack, render=render)
    renderapi.client.import_tilespecs(ref_stack, tilespecs, render=render)
    renderapi.stack.set_stack_state(ref_stack, 'COMPLETE', render=render)

    assert len({tspec.tileId for tspec in tilespecs}.symmetric_difference(set(
                        renderapi.stack.get_stack_tileIds(
                            ref_stack, render=render)))) == 0
    
    yield ref_stack
    renderapi.stack.delete_stack(ref_stack, render=render)

@pytest.fixture(scope='module')
def moving_stack(render):
    tilespecs = [renderapi.tilespec.TileSpec(json=d) 
                    for d in MOVING_STACK_TSPECS]
    moving_stack = "moving_stack"
    
    renderapi.stack.create_stack(moving_stack, render=render)
    renderapi.client.import_tilespecs(moving_stack, tilespecs, render=render)
    renderapi.stack.set_stack_state(moving_stack, 'COMPLETE', render=render)

    assert len({tspec.tileId for tspec in tilespecs}.symmetric_difference(set(
                        renderapi.stack.get_stack_tileIds(
                            moving_stack, render=render)))) == 0
    
    yield moving_stack
    renderapi.stack.delete_stack(moving_stack, render=render)

@pytest.fixture(scope='module')
def point_match_collection(render):
    point_matches = [d for d in POINT_MATCHES]
    pt_match_collection = 'rough_align_fixes'
    renderapi.pointmatch.import_matches(pt_match_collection,
                                        point_matches,
                                        render=render)
    yield pt_match_collection
    renderapi.pointmatch.delete_collection(pt_match_collection, render=render)

def test_rough_registration(render, reference_stack, moving_stack, point_match_collection):
    example['render'] = render_params
    example['render']['project'] = "rough_registration"
    example['reference_stack'] = reference_stack
    example['moving_stack'] = moving_stack
    example['match_collection'] = point_match_collection

    out_json = "rough_register_out.json"

    mod = RegisterSectionByPointMatch(input_data=example, args=['--output_json', out_json])
    mod.run()

    stacks = renderapi.render.get_stacks_by_owner_project(owner=render.DEFAULT_OWNER,
                                                          project=render.DEFAULT_PROJECT,
                                                          render=render)
    assert(example['output_stack'] in stacks)

    zvalues = renderapi.stack.get_z_values_for_stack(example['output_stack'], render=render)
    assert(example['moving_z'] in zvalues)

    # code coverage
    mod.run()

    # rigid model
    example['registration_model'] = "Rigid"
    mod = RegisterSectionByPointMatch(input_data=example, args=['--output_json', out_json])
    mod.run()
    zvalues = renderapi.stack.get_z_values_for_stack(example['output_stack'], render=render)
    assert(example['moving_z'] in zvalues)

    example['reference_stack'] = moving_stack
    example['moving_stack'] = reference_stack
    mod = RegisterSectionByPointMatch(input_data=example, args=['--output_json', out_json])
    mod.run()
    zvalues = renderapi.stack.get_z_values_for_stack(example['output_stack'], render=render)
    assert(example['moving_z'] in zvalues)


