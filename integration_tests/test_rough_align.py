
import os
import pytest
import logging
import renderapi
import json
import glob
from test_data import (ROUGH_MONTAGE_TILESPECS_JSON, render_params)

from rendermodules.materialize.render_downsample_sections import RenderSectionAtScale
from rendermodules.dataimport.make_montage_scapes_stack import MakeMontageScapeSectionStack
from rendermodules.pointmatch.create_tilepairs import TilePairClientModule
from rendermodules.rough_align.do_rough_alignment import SolveRoughAlignmentModule, example
from rendermodules.rough_align.apply_rough_alignment_transform_to_montage_stack import ApplyRoughAlignmentTransform, example as ex1


logger = renderapi.client.logger
logger.setLevel(logging.DEBUG)

render_params['project'] = 'rough_align_test'


@pytest.fixture(scope='module')
def render():
    render = renderapi.connect(**render_params)
    return render


@pytest.fixture(scope='module')
def tspecs_from_json():
    tilespecs = [renderapi.tilespec.TileSpec(json=d)
        for d in ROUGH_MONTAGE_TILESPECS_JSON]
    return tilespecs


# A stack with multiple sections montaged
@pytest.fixture(scope='module')
def montage_stack(render,tspecs_from_json):
    test_montage_stack = 'input_montage_stack'
    renderapi.stack.create_stack(test_montage_stack, render=render)
    renderapi.client.import_tilespecs(test_montage_stack, 
                                      tspecs_from_json, 
                                      render=render)
    renderapi.stack.set_stack_state(test_montage_stack, 
                                    'COMPLETE', 
                                    render=render)

    # assure stack is built correctly
    assert len({tspec.tileId for tspec
                in tspecs_from_json}.symmetric_difference(set(
                    renderapi.stack.get_stack_tileIds(
                        test_montage_stack, render=render)))) == 0
    yield test_montage_stack
    renderapi.stack.delete_stack(test_montage_stack, render=render)


@pytest.fixture(scope='module')
def downsample_sections_dir(montage_stack, tmpdir_factory):
    image_directory = str(tmpdir_factory.mktemp('Rough_Align'))
    ex = {
        "render": render_params,
        "input_stack": montage_stack,
        "image_directory": image_directory,
        "imgformat": "png",
        "scale": 0.01,
        "minZ": 1015,
        "maxZ": 1017
    }

    mod = RenderSectionAtScale(input_data=ex, args=[])
    mod.run()
    out_dir = os.path.join(image_directory, render_params['project'], montage_stack, 'sections_at_0.01/001/0')
    assert(os.path.exists(out_dir))
    
    files = glob.glob(os.path.join(out_dir, '*.png'))
    for f in files:
        img = os.path.join(out_dir, f)
        assert(os.path.exists(img) and os.path.isfile(img) and os.path.getsize(img) > 0)
    yield image_directory
    


@pytest.fixture(scope='module')
def test_montage_scape_stack(render, montage_stack, downsample_sections_dir):
    output_stack = '{}OUT'.format(montage_stack)
    params = {
        "render": render_params,
        "montage_stack": montage_stack,
        "output_stack": output_stack,
        "image_directory": downsample_sections_dir,
        "imgformat": "png",
        "scale":0.01,
        "zstart": 1015,
        "zend": 1017
    }

    mod = MakeMontageScapeSectionStack(input_data=params, args=[])
    mod.run()

    assert len(params['zend']-params['zstart']+1) == len(renderapi.stack.get_z_values_for_stack(
                                        output_stack, render=render))
    assert len({range(params['zstart'], params['zend']+1)}.symmetric_difference(
                                        renderapi.stack.get_z_values_for_stack(
                                            output_stack, render=render))) == 0
    yield output_stack
    renderapi.stack.delete_stack(test_montage_scape_stack, render=render)


@pytest.fixture(scope='module')
def test_create_rough_tile_pairs(render, test_montage_scape_stack, tmpdir_factory):
    output_directory = str(tmpdir_factory.mktemp('Rough_Align'))
    params = {
        "render": render_params,
        "stack": test_montage_scape_stack,
        "zNeighborDistance": 2,
        "xyNeighborFactor": 0.9,
        "excludeCornerNeighbors": "true",
        "excludeSameLayerNeighbors": "true",
        "excludeCompletelyObscuredTiles":"true",
        "minZ": 1015,
        "maxZ": 1017,
        "output_dir": output_directory
    }

    mod = TilePairClientModule(input_data=params, args=[])
    mod.run()

    # check if the file has been created
    tilepair_file = "tile_pairs_{}_z_{}_to_{}_dist_{}.json".format(
                        test_montage_scape_stack,
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
def test_point_match_generation(render, test_create_rough_tile_pairs):
    pt_match_collection = 'rough_align_point_matches'

    yield pt_match_collection

@pytest.fixture(scope='module')
def test_do_rough_alignment(render, test_montage_scape_stack, test_point_match_generation, tmpdir_factory, output_lowres_stack=None):
    if output_lowres_stack == None:
        output_lowres_stack = '{}_DS_Rough'.format(test_montage_scape_stack)

    scratch_directory = str(tmpdir_factory.mktemp('scratch'))
    example['render'] = render_params
    example['input_lowres_stack']['stack'] = test_montage_scape_stack
    example['input_lowres_stack']['owner'] = render_params['owner']
    example['input_lowres_stack']['project'] = render_params['project']

    example['output_lowres_stack']['stack'] = output_lowres_stack
    example['output_lowres_stack']['owner'] = render_params['owner']
    example['output_lowres_stack']['project'] = render_params['project']

    example['point_match_collection']['owner'] = render_params['owner']
    example['point_match_collection']['match_collection'] = test_point_match_generation
    example['point_match_collection']['scale'] = 1.0

    example['solver_options']['dir_scratch'] = scratch_directory
    example['solver_executable'] = ROUGH_SOLVER_EXECUTABLE
    example['minz'] = 1015
    example['maxz'] = 1017

    mod = SolveRoughAlignmentModule(input_data=example, args=[])
    mod.run()

    zend = example['maxz']
    zstart = example['minz']
    assert len(zend-zstart+1) == len(renderapi.stack.get_z_values_for_stack(
                                        output_lowres_stack, render=render))
    assert len({range(zstart, zend+1)}.symmetric_difference(
                                        renderapi.stack.get_z_values_for_stack(
                                            output_stack, render=render))) == 0

    yield output_lowres_stack
    renderapi.stack.delete_stack(output_lowres_stack, render=render)

def test_apply_rough_alignment_transform(render, montage_stack, test_do_rough_alignment, tmpdir_factory, prealigned_stack=None, output_stack=None):
    ex1['montage_stack'] = montage_stack
    if prealigned_stack is None:
        ex1['prealigned_stack'] = montage_stack
    else:
        ex1['prealigned_stack'] = prealigned_stack

    ex1['lowres_stack'] = test_do_rough_alignment
    ex1['output_stack'] = '{}_Rough'.format(montage_stack)
    ex1['tilespec_directory'] = str(tmpdir_factory.mktemp('scratch'))
    ex1['minZ'] = 1015
    ex1['maxZ'] = 1017
    ex1['scale'] = 0.05

    mod = ApplyRoughAlignmentTransform(input_data=ex1, args=[])
    mod.run()

    zend = ex1['maxZ']
    zstart = ex1['minZ']
    assert len(zend-zstart+1) == len(renderapi.stack.get_z_values_for_stack(
                                        ex1['output_stack'], render=render))
    assert len({range(zstart, zend+1)}.symmetric_difference(
                                        renderapi.stack.get_z_values_for_stack(
                                            ex1['output_stack'], render=render))) == 0
