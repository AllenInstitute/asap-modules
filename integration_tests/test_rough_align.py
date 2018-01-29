
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


@pytest.fixture(scope='module')
def render():
    render_params['project'] = 'rough_align_test'
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
    
    zvalues = render.run(renderapi.stack.get_z_values_for_stack,
                          test_montage_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))

    yield test_montage_stack
    renderapi.stack.delete_stack(test_montage_stack, render=render)

@pytest.fixture(scope='module')
def downsample_sections_dir(montage_stack, tmpdir_factory):
    image_directory = str(tmpdir_factory.mktemp('rough_align'))
    print(render_params)
    ex = {
        "render": render_params,
        "input_stack": montage_stack,
        "image_directory": image_directory,
        "imgformat": "png",
        "scale": 0.1,
        "minZ": 1020,
        "maxZ": 1022,
    }
    ex['output_json'] = os.path.join(image_directory, 'output.json')

    mod = RenderSectionAtScale(input_data=ex, args=[])
    mod.run()

    out_dir = os.path.join(image_directory, render.DEFAULT_PROJECT, montage_stack, 'sections_at_0.1/001/0')
    assert(os.path.exists(out_dir))
    
    files = glob.glob(os.path.join(out_dir, '*.png'))
    for fil in files:
        img = os.path.join(out_dir, fil)
        assert(os.path.exists(img) and os.path.isfile(img) and os.path.getsize(img) > 0)
    
    yield image_directory


@pytest.fixture(scope='module')
def point_matches_from_json():
    point_matches = [d for d in ROUGH_POINT_MATCH_COLLECTION]
    return point_matches

#@pytest.fixture(scope='module')
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

    
    
    