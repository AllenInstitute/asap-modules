import os
import pytest
import logging
import renderapi
import tempfile
import json

from test_data import PT_MATCH_STACK_TILESPECS, render_params

from rendermodules.module.render_module import RenderModuleException
from rendermodules.point_match_optimization.point_match_optimization import ex as example
from rendermodules.point_match_optimization.point_match_optimization import *

logger = renderapi.client.logger
logger.setLevel(logging.DEBUG)

@pytest.fixture(scope='module')
def render():
    render_params['project'] = 'pt_match_optimization'
    render = renderapi.connect(**render_params)
    return render

@pytest.fixture(scope='module')
def stack_from_json():
    tilespecs = [renderapi.tilespec.TileSpec(json=d)
                    for d in PT_MATCH_STACK_TILESPECS]
    return tilespecs

@pytest.fixture(scope='module')
def pt_match_input_stack(render, stack_from_json):
    ptmatch_input_stack = "pt_match_input_stack"
    renderapi.stack.create_stack(
                        ptmatch_input_stack,
                        render=render)
    renderapi.client.import_tilespecs(
                        ptmatch_input_stack,
                        stack_from_json,
                        render=render)
    renderapi.stack.set_stack_state(
                        ptmatch_input_stack,
                        'COMPLETE',
                        render=render)
    
    # assure stack is built correctly
    assert len({tspec.tileId for tspec
                in stack_from_json}.symmetric_difference(set(
                    renderapi.stack.get_stack_tileIds(
                        ptmatch_input_stack, render=render)))) == 0

    yield ptmatch_input_stack
    renderapi.stack.delete_stack(
                        ptmatch_input_stack,
                        render=render)
    

def test_pt_match_optimization_module(render, pt_match_input_stack, tmpdir_factory):
    output_dir = str(str(tmpdir_factory.mktemp('pt_match_optimization')))

    example['render'] = render_params
    example['stack'] = pt_match_input_stack
    example['outputDirectory'] = output_dir
    example.pop('tile_stack', None)

    out_json = "pt_match_optimization_output.json"
    mod = PointMatchOptimizationModule(input_data=example, args=['--output_json', out_json])
    mod.run()

    # check if the output html file is generated
    with open(out_json, 'r') as f:
        js = json.load(f)

    assert(os.path.exists(js['output_html']) and os.path.isfile(js['output_html']))

def test_get_parameters_and_strings(render, pt_match_input_stack, tmpdir_factory):
    output_dir = str(str(tmpdir_factory.mktemp('pt_match_optimization')))
    example['render'] = render_params
    example['stack'] = pt_match_input_stack
    example['outputDirectory'] = output_dir
    example['tile_stack'] = 'pt_match_tile_stack'

    keys, options = get_parameter_sets_and_strings(example['SIFT_options'])
    assert(len(keys) > 0)


def test_get_canvas_url(pt_match_input_stack):
    render_args = example['render']
    stack = pt_match_input_stack
    tile1 = example['tileId1']
    tile2 = example['tileId2']
    url_options = example['url_options']

    url = get_canvas_url(render_args, 
                         pt_match_input_stack,
                         example['tileId1'],
                         example['tileId2'],
                         example['url_options'])
    
    base_data_url = '%s:%d/render-ws/v1'%(render_args['host'], render_args['port']) 
    tile_base_url = "%s/owner/%s/project/%s/stack/%s/tile"%(base_data_url, 
                                                            render_args['owner'], 
                                                            render_args['project'], 
                                                            stack) 

    url_suffix = "render-parameters?filter=true&normalizeForMatching=true&renderWithoutMask=true" 

    canvas_urls = "%s/%s/%s %s/%s/%s"%(tile_base_url, 
                                        tile1, 
                                        url_suffix, 
                                        tile_base_url, 
                                        tile2, 
                                        url_suffix) 
    assert(canvas_urls == url)

    example['url_options']['normalizeForMatching'] = False
    example['url_options']['renderWithFilter'] = False
    example['url_options']['renderWithoutMask'] = False

    url = get_canvas_url(render_args, 
                         pt_match_input_stack,
                         example['tileId1'],
                         example['tileId2'],
                         example['url_options'])
    url_suffix = "render-parameters?filter=false&normalizeForMatching=false&renderWithoutMask=false" 

    canvas_urls = "%s/%s/%s %s/%s/%s"%(tile_base_url, 
                                        tile1, 
                                        url_suffix, 
                                        tile_base_url, 
                                        tile2, 
                                        url_suffix) 
    assert(canvas_urls == url)
    
def test_run_without_partial(render, pt_match_input_stack, tmpdir_factory):
    output_dir = str(str(tmpdir_factory.mktemp('pt_match_optimization')))
    example['render'] = render_params
    example['stack'] = pt_match_input_stack
    example['outputDirectory'] = output_dir
    example['tile_stack'] = 'pt_match_tile_stack'

    example['url_options']['normalizeForMatching'] = True
    example['url_options']['renderWithFilter'] = True
    example['url_options']['renderWithoutMask'] = True

    keys, options = get_parameter_sets_and_strings(example['SIFT_options'])

    compute_point_matches(render,
                          example['tile_stack'],
                          example['tileId1'],
                          example['tileId2'],
                          1050.0,
                          1050.0,
                          example['outputDirectory'],
                          example['url_options'],
                          keys, options[0])

