
import os
import pytest
import logging
import renderapi
import json
import glob
from test_data import (ROUGH_MONTAGE_TILESPECS_JSON,
                       ROUGH_POINT_MATCH_COLLECTION,
                       render_params,
                       test_rough_parameters as solver_example)

from rendermodules.materialize.render_downsample_sections import RenderSectionAtScale
from rendermodules.dataimport.make_montage_scapes_stack import MakeMontageScapeSectionStack
from rendermodules.rough_align.do_rough_alignment import SolveRoughAlignmentModule
from rendermodules.rough_align.apply_rough_alignment_to_montages import ApplyRoughAlignmentTransform, example as ex1


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
def point_matches_from_json():
    point_matches = [d for d in ROUGH_POINT_MATCH_COLLECTION]
    return point_matches


@pytest.fixture(scope='module')
def downsample_sections_dir(montage_stack, tmpdir_factory):
    image_directory = str(tmpdir_factory.mktemp('rough_align'))
    ex = {
        "render": render_params,
        "input_stack": montage_stack,
        "image_directory": image_directory,
        "imgformat": "png",
        "scale": 0.1,
        "minZ": 1020,
        "maxZ": 1022
    }

    mod = RenderSectionAtScale(input_data=ex, args=[])
    mod.run()
    out_dir = os.path.join(image_directory, render_params['project'], montage_stack, 'sections_at_0.1/001/0')
    assert(os.path.exists(out_dir))
    
    files = glob.glob(os.path.join(out_dir, '*.png'))
    for fil in files:
        img = os.path.join(out_dir, fil)
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
        "scale":0.1,
        "zstart": 1020,
        "zend": 1022
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
def point_match_collection(render, point_matches_from_json):
    test_point_match_collection = 'point_match_collection'
    renderapi.pointmatch.import_matches(test_point_match_collection,
                                        point_matches_from_json,
                                        render=render)
    
    # check if point matches have been imported properly
    groupIds = render.run(renderapi.pointmatch.get_match_groupIds, test_point_match_collection)
    assert(len(groupIds) == 3)
    yield test_point_match_collection



'''
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
def test_point_match_generation(render, test_create_rough_tile_pairs, tmpdir_factory):
    output_directory = str(tmpdir_factory.mktemp('output_json'))
    pointmatch_example['output_json']=os.path.join(output_directory,'output.json')
    pointmatch_example['pairJson'] = test_create_rough_tile_pairs
    pointmatch_example['renderScale'] = 1.0
    pointmatch_example['SIFTmaxScale'] = 1.0
    pointmatch_example['SIFTminScale'] = 0.2
    
    mod = PointMatchClientModuleSpark(input_data=pointmatch_example,args=[])
    mod.run()
    
    with open(pointmatch_example['output_json'],'r') as fp:
        output_d = json.load(fp)
    
    assert (output_d['pairCount']>0)
    yield pointmatch_example['collection']

'''

@pytest.fixture(scope='module')
def test_do_rough_alignment(render, test_montage_scape_stack, point_match_collection, tmpdir_factory, output_lowres_stack=None):
    if output_lowres_stack == None:
        output_lowres_stack = '{}_DS_Rough'.format(test_montage_scape_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_example['output_json']=os.path.join(output_directory,'output.json')

    solver_example['source_collection']['stack'] = test_montage_scape_stack
    solver_example['target_collection']['stack'] = output_lowres_stack
    solver_example['source_point_match_collection']['match_collection'] = point_match_collection

       
    mod = SolveRoughAlignmentModule(input_data=solver_example, args=[])
    mod.run()

    zend = solver_example['maxz']
    zstart = solver_example['minz']
    assert len(zend-zstart+1) == len(renderapi.stack.get_z_values_for_stack(
                                        output_lowres_stack, render=render))
    assert len({range(zstart, zend+1)}.symmetric_difference(
                                        renderapi.stack.get_z_values_for_stack(
                                            output_lowres_stack, render=render))) == 0

    yield output_lowres_stack
    renderapi.stack.delete_stack(output_lowres_stack, render=render)

def test_apply_rough_alignment_transform(render, montage_stack, test_do_rough_alignment, tmpdir_factory, prealigned_stack=None, output_stack=None):
    ex1['montage_stack'] = montage_stack
    if prealigned_stack is None:
        ex1['prealigned_stack'] = montage_stack
    else:
        ex1['prealigned_stack'] = prealigned_stack

    ex1['render'] = render_params
    ex1['lowres_stack'] = test_do_rough_alignment
    ex1['output_stack'] = '{}_Rough'.format(montage_stack)
    ex1['tilespec_directory'] = str(tmpdir_factory.mktemp('scratch'))
    ex1['minZ'] = 1020
    ex1['maxZ'] = 1022
    ex1['scale'] = 0.1

    mod = ApplyRoughAlignmentTransform(input_data=ex1, args=[])
    mod.run()

    zend = ex1['maxZ']
    zstart = ex1['minZ']
    assert len(zend-zstart+1) == len(renderapi.stack.get_z_values_for_stack(
                                        ex1['output_stack'], render=render))
    assert len({range(zstart, zend+1)}.symmetric_difference(
                                        renderapi.stack.get_z_values_for_stack(
                                            ex1['output_stack'], render=render))) == 0
