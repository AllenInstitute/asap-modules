
import os
import pytest
import logging
import renderapi
import json
import glob
import marshmallow as mm
from test_data import (ROUGH_MONTAGE_TILESPECS_JSON,
                       ROUGH_POINT_MATCH_COLLECTION,
                       ROUGH_DS_TEST_TILESPECS_JSON,
                       render_params,
                       test_rough_parameters as solver_example,
                       pool_size)

from rendermodules.module.render_module import RenderModuleException
from rendermodules.materialize.render_downsample_sections import RenderSectionAtScale, create_tilespecs_without_mipmaps
from rendermodules.dataimport.make_montage_scapes_stack import MakeMontageScapeSectionStack
from rendermodules.rough_align.do_rough_alignment import SolveRoughAlignmentModule
from rendermodules.rough_align.apply_rough_alignment_to_montages import (ApplyRoughAlignmentTransform, 
                                                                         example as ex1,
                                                                         apply_rough_alignment)


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

@pytest.fixture(scope='module')
def tspecs():
    tilespecs = [renderapi.tilespec.TileSpec(json=d)
                for d in ROUGH_DS_TEST_TILESPECS_JSON]
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
def one_tile_montage(render, tspecs):
    one_tile_montage_stack = 'one_tile_montage_stack'
    renderapi.stack.create_stack(one_tile_montage_stack, render=render)
    renderapi.client.import_tilespecs(one_tile_montage_stack, 
                                      tspecs, 
                                      render=render)
    renderapi.stack.set_stack_state(one_tile_montage_stack, 
                                    'COMPLETE', 
                                    render=render)
    # assure stack is built correctly
    assert len({tspec.tileId for tspec
                in tspecs}.symmetric_difference(set(
                    renderapi.stack.get_stack_tileIds(
                        one_tile_montage_stack, render=render)))) == 0
    
    yield one_tile_montage_stack
    render.run(renderapi.stack.delete_stack, one_tile_montage_stack)


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

    out_dir = os.path.join(image_directory, render_params['project'], montage_stack, 'sections_at_0.1/001/0')
    assert(os.path.exists(out_dir))
    
    files = glob.glob(os.path.join(out_dir, '*.png'))
    
    assert(len(files) == len(range(ex['minZ'], ex['maxZ']+1)))

    for fil in files:
        img = os.path.join(out_dir, fil)
        assert(os.path.exists(img) and os.path.isfile(img) and os.path.getsize(img) > 0)
    
    yield image_directory


@pytest.fixture(scope='module')
def rough_point_matches_from_json():
    point_matches = [d for d in ROUGH_POINT_MATCH_COLLECTION]
    return point_matches

@pytest.fixture(scope='module')
def montage_scape_stack(render, montage_stack, downsample_sections_dir):
    output_stack = '{}_DS'.format(montage_stack)
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
    outjson = 'test_montage_scape_output.json'
    mod = MakeMontageScapeSectionStack(input_data=params, args=['--output_json', outjson])
    mod.run()

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, output_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))

    yield output_stack
    renderapi.stack.delete_stack(test_montage_scape_stack, render=render)

@pytest.fixture(scope='module')
def rough_point_match_collection(render, rough_point_matches_from_json):
    pt_match_collection = 'rough_point_match_collection'
    renderapi.pointmatch.import_matches(pt_match_collection,
                                        rough_point_matches_from_json,
                                        render=render)
    
    # check if point matches have been imported properly
    groupIds = render.run(renderapi.pointmatch.get_match_groupIds, pt_match_collection)
    #assert(len(groupIds) == 3)
    yield pt_match_collection
    render.run(renderapi.pointmatch.delete_collection, pt_match_collection)

@pytest.fixture(scope='module')
def test_do_rough_alignment(render, montage_scape_stack, rough_point_match_collection, tmpdir_factory, output_lowres_stack=None):
    if output_lowres_stack == None:
        output_lowres_stack = '{}_DS_Rough'.format(montage_scape_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_example['output_json']=os.path.join(output_directory,'output.json')

    solver_example['source_collection']['stack'] = montage_scape_stack
    solver_example['target_collection']['stack'] = output_lowres_stack
    solver_example['source_point_match_collection']['match_collection'] = rough_point_match_collection

       
    mod = SolveRoughAlignmentModule(input_data=solver_example, args=[])
    mod.run()

    zend = solver_example['first_section']
    zstart = solver_example['last_section']
    
    zvalues = render.run(renderapi.stack.get_z_values_for_stack, output_lowres_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))

    yield output_lowres_stack
    renderapi.stack.delete_stack(output_lowres_stack, render=render)

    
def test_montage_scape_stack(render, montage_scape_stack):
    zvalues = render.run(renderapi.stack.get_z_values_for_stack, montage_scape_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues)==set(zs)) 
    
def test_point_match_collection(render, rough_point_match_collection):
    groupIds = render.run(renderapi.pointmatch.get_match_groupIds, rough_point_match_collection)
    assert(('1020.0' in groupIds) and ('1021.0' in groupIds) and ('1022.0' in groupIds))

def test_apply_rough_alignment_transform(render, montage_stack, test_do_rough_alignment, tmpdir_factory, prealigned_stack=None, output_stack=None):

    ex1['render'] = render_params
    ex1['montage_stack'] = montage_stack
    ex1['lowres_stack'] = test_do_rough_alignment
    ex1['prealigned_stack'] = None
    ex1['output_stack'] = '{}_Rough'.format(montage_stack)
    ex1['tilespec_directory'] = str(tmpdir_factory.mktemp('scratch'))
    ex1['minZ'] = 1020
    ex1['maxZ'] = 1022
    ex1['scale'] = 0.1
    ex1['pool_size'] = pool_size
    ex1['output_json']=str(tmpdir_factory.mktemp('output').join('output.json'))
    ex1['loglevel']='DEBUG'
    
    mod = ApplyRoughAlignmentTransform(input_data=ex1, args=[])
    mod.run()

    zend = ex1['maxZ']
    zstart = ex1['minZ']

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, ex1['output_stack'])
    zs = range(zstart, zend+1)

    assert(set(zvalues) == set(zs))

    apply_rough_alignment(render, 
                          ex1['montage_stack'], 
                          ex1['montage_stack'],
                          ex1['lowres_stack'],
                          ex1['output_stack'],
                          ex1['tilespec_directory'],
                          ex1['scale'],
                          (1020,1020),
                          consolidateTransforms=True)

    # running again for code coverage
    mod.run()

    ex1['minZ'] = 1022
    ex1['maxZ'] = 1020

    mod = ApplyRoughAlignmentTransform(input_data=ex1, args=[])
    with pytest.raises(RenderModuleException):
        mod.run()

    ex1['set_new_z'] = True
    ex1['minZ'] = 1020
    ex1['maxZ'] = 1022
    mod = ApplyRoughAlignmentTransform(input_data=ex1, args=[])
    mod.run()
    zvalues = render.run(renderapi.stack.get_z_values_for_stack, ex1['output_stack'])
    assert(set(zvalues) == set(range(len(zvalues))))
    
    ex1['set_new_z'] = False
    ex1['output_stack'] = 'failed_output'
    with pytest.raises(RenderModuleException):
        renderapi.stack.delete_section(ex1['lowres_stack'],1021,render=render)
        mod = ApplyRoughAlignmentTransform(input_data=ex1, args=[])
        mod.run()
        zvalues = renderapi.stack.get_z_values_for_stack(ex1['output_stack'],render=render)
        assert(1021 not in zvalues)
        
# additional tests for code coverage

def test_render_downsample_with_mipmaps(render, one_tile_montage, tmpdir_factory):
    image_directory = str(tmpdir_factory.mktemp('rough'))
    ex = {
        "render": render_params,
        "input_stack": one_tile_montage,
        "image_directory": image_directory,
        "imgformat": "png",
        "scale": 0.1,
        "minZ": -1,
        "maxZ": -1,
    }
    ex['output_json'] = os.path.join(image_directory, 'output.json')

    #stack_has_mipmaps = check_stack_for_mipmaps(render, ex['input_stack'], [1020])
    tempjson = create_tilespecs_without_mipmaps(render, ex['input_stack'], 0, 1020)

    mod = RenderSectionAtScale(input_data=ex, args=[])
    mod.run()

    with open(ex['output_json'], 'r') as f:
        js = json.load(f)
    
    out_dir = os.path.join(image_directory, render_params['project'], js['temp_stack'], 'sections_at_0.1/001/0')
    assert(os.path.exists(out_dir))
    
    files = glob.glob(os.path.join(out_dir, '*.png'))
    for fil in files:
        img = os.path.join(out_dir, fil)
        assert(os.path.exists(img) and os.path.isfile(img) and os.path.getsize(img) > 0)
    
    ex['minZ'] = 1021
    ex['maxZ'] = 1020
    mod = RenderSectionAtScale(input_data=ex, args=[])
    with pytest.raises(RenderModuleException):
        mod.run()
    
    ex['minZ'] = 1
    ex['maxZ'] = 2
    mod = RenderSectionAtScale(input_data=ex, args=[])
    with pytest.raises(RenderModuleException):
        mod.run()

def test_make_montage_stack_without_downsamples(render, one_tile_montage, tmpdir_factory):
    # testing for make montage scape stack without having downsamples generated
    tmp_dir = str(tmpdir_factory.mktemp('downsample'))
    output_stack = '{}_Downsample'.format(one_tile_montage) 
    params = {
        "render": render_params,
        "montage_stack": one_tile_montage,
        "output_stack": output_stack,
        "image_directory": tmp_dir,
        "imgformat": "png",
        "scale":0.1,
        "zstart": 1020,
        "zend": 1020
    }
    outjson = 'test_montage_scape_output.json'
    mod = MakeMontageScapeSectionStack(input_data=params, args=['--output_json', outjson])
    mod.run()
    
    

def test_make_montage_scape_stack_fail(render, montage_stack, downsample_sections_dir):
    output_stack = '{}_DS'.format(montage_stack)
    params = {
        "render": render_params,
        "montage_stack": montage_stack,
        "output_stack": output_stack,
        "image_directory": downsample_sections_dir,
        "imgformat": "png",
        "set_new_z":True,
        "new_z_start":-1,
        "scale":0.1,
        "zstart": 1020,
        "zend": 1022
    }
    outjson = 'test_montage_scape_output.json'
    
    with pytest.raises(mm.ValidationError):
        mod = MakeMontageScapeSectionStack(input_data=params, args=['--output_json', outjson])
        mod.run()

    params['set_new_z'] = False
    params['zstart'] = 1
    params['zend'] = 2
    mod = MakeMontageScapeSectionStack(input_data=params, args=['--output_json', outjson])
    with pytest.raises(RenderModuleException):
        mod.run()

def test_setting_new_z_montage_scape(render, montage_stack, downsample_sections_dir):
    output_stack = '{}_DS'.format(montage_stack)
    params = {
        "render": render_params,
        "montage_stack": montage_stack,
        "output_stack": output_stack,
        "image_directory": downsample_sections_dir,
        "imgformat": "png",
        "set_new_z": True,
        "new_z_start": -1,
        "scale":0.1,
        "zstart": 1020,
        "zend": 1022
    }
    outjson = 'test_montage_scape_output.json'
    with pytest.raises(mm.ValidationError):
        mod = MakeMontageScapeSectionStack(input_data=params, args=['--output_json', outjson])

def test_solver_default_options(render, montage_scape_stack, rough_point_match_collection, tmpdir_factory):
    output_lowres_stack = '{}_DS_Rough'.format(montage_scape_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_example['output_json']=os.path.join(output_directory,'output.json')

    solver_example['source_collection']['stack'] = montage_scape_stack
    solver_example['source_collection']['owner'] = None
    solver_example['source_collection']['project'] = None
    solver_example['source_collection']['service_host'] = None
    solver_example['source_collection']['baseURL'] = None
    solver_example['source_collection']['renderbinPath'] = None
    solver_example['target_collection']['stack'] = output_lowres_stack
    solver_example['target_collection']['owner'] = None
    solver_example['target_collection']['project'] = None
    solver_example['target_collection']['service_host'] = None
    solver_example['target_collection']['baseURL'] = None
    solver_example['target_collection']['renderbinPath'] = None
    solver_example['source_point_match_collection']['match_collection'] = rough_point_match_collection
    solver_example['source_point_match_collection']['server'] = None
    #solver_example['source_point_match_collection']['owner'] = None
    solver_example['first_section'] = 1020
    solver_example['last_section'] = 1020

    solver_example['source_collection'].pop('owner', None)
    solver_example['source_collection'].pop('project', None)
    solver_example['source_collection'].pop('service_host', None)
    solver_example['source_collection'].pop('baseURL', None)
    solver_example['source_collection'].pop('renderbinPath', None)
    solver_example['target_collection'].pop('owner', None)
    solver_example['target_collection'].pop('project', None)
    solver_example['target_collection'].pop('service_host', None)
    solver_example['target_collection'].pop('baseURL', None)
    solver_example['target_collection'].pop('renderbinPath', None)
    #solver_example['solver_options']['pastix'] = None
    
    mod = SolveRoughAlignmentModule(input_data=solver_example, args=[])

    with pytest.raises(RenderModuleException):
        mod.run()
    
    solver_example['first_section'] = 1022
    solver_example['last_section'] = 1020

    mod = SolveRoughAlignmentModule(input_data=solver_example, args=[])

    with pytest.raises(RenderModuleException):
        mod.run()
    
    os.environ.pop('MCRROOT', None)
    mod = SolveRoughAlignmentModule(input_data=solver_example, args=[])

    with pytest.raises(mm.ValidationError):
        mod.run()
