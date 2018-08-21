
import os
import pytest
import logging
import renderapi
import json
import glob
import copy
import marshmallow as mm
from six.moves import urllib
from test_data import (ROUGH_MONTAGE_TILESPECS_JSON,
                       ROUGH_MONTAGE_TRANSFORM_JSON,
                       ROUGH_POINT_MATCH_COLLECTION,
                       ROUGH_DS_TEST_TILESPECS_JSON,
                       ROUGH_MAPPED_PT_MATCH_COLLECTION,
                       render_params,
                       test_rough_parameters as solver_example,
                       apply_rough_alignment_example as ex1,
                       pool_size)

from rendermodules.module.render_module import RenderModuleException
from rendermodules.materialize.render_downsample_sections import RenderSectionAtScale, create_tilespecs_without_mipmaps
from rendermodules.dataimport.make_montage_scapes_stack import MakeMontageScapeSectionStack, create_montage_scape_tile_specs
from rendermodules.rough_align.do_rough_alignment import SolveRoughAlignmentModule
from rendermodules.rough_align.apply_rough_alignment_to_montages import (ApplyRoughAlignmentTransform,
                                                                         #example as ex1,
                                                                         apply_rough_alignment)


logger = renderapi.client.logger
logger.setLevel(logging.DEBUG)



@pytest.fixture(scope='module')
def render():
    render_params['project'] = 'rough_align_test'
    render = renderapi.connect(**render_params)
    return render


@pytest.fixture(scope='module')
def resolvedtiles_from_json():
    tilespecs = [renderapi.tilespec.TileSpec(json=d)
                 for d in ROUGH_MONTAGE_TILESPECS_JSON]
    transforms = [renderapi.transform.load_transform_json(d)
                  for d in ROUGH_MONTAGE_TRANSFORM_JSON]
    return renderapi.resolvedtiles.ResolvedTiles(
        tilespecs, transforms)


@pytest.fixture(scope='module')
def tspecs():
    tilespecs = [renderapi.tilespec.TileSpec(json=d)
                for d in ROUGH_DS_TEST_TILESPECS_JSON]
    return tilespecs


# A stack with multiple sections montaged
@pytest.fixture(scope='module')
def montage_stack(render, resolvedtiles_from_json):
    tspecs = resolvedtiles_from_json.tilespecs
    tforms = resolvedtiles_from_json.transforms
    test_montage_stack = 'input_montage_stack'
    renderapi.stack.create_stack(test_montage_stack, render=render)
    renderapi.client.import_tilespecs(test_montage_stack,
                                      tspecs, sharedTransforms=tforms,
                                      render=render)
    renderapi.stack.set_stack_state(test_montage_stack,
                                    'COMPLETE',
                                    render=render)

    # assure stack is built correctly
    assert len({tspec.tileId for tspec
                in tspecs}.symmetric_difference(set(
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
    
    # set bounds parameter to stack bounds
    ex['use_stack_bounds'] = "True"
    
    mod = RenderSectionAtScale(input_data=ex, args=[])
    mod.run()

    out_dir = os.path.join(image_directory, render_params['project'], montage_stack, 'sections_at_0.1/001/0')
    assert(os.path.exists(out_dir))

    files = glob.glob(os.path.join(out_dir, '*.png'))

    assert(len(files) == len(range(ex['minZ'], ex['maxZ']+1)))

    for fil in files:
        img = os.path.join(out_dir, fil)
        assert(os.path.exists(img) and os.path.isfile(img) and os.path.getsize(img) > 0)

    # remove files from the previous run
    os.system("rm {}/*.png".format(out_dir))

    # set bounds to section bounds
    ex['user_stack_bounds'] = "False"
    
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
def rough_mapped_pt_matches_from_json():
    pt_matches = [d for d in ROUGH_MAPPED_PT_MATCH_COLLECTION]
    return pt_matches


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
    renderapi.stack.delete_stack(output_stack, render=render)

@pytest.fixture(scope='module')
def montage_scape_stack_with_scale(render, montage_stack, downsample_sections_dir):
    output_stack = '{}_DS_scale'.format(montage_stack)
    params = {
        "render": render_params,
        "montage_stack": montage_stack,
        "output_stack": output_stack,
        "image_directory": downsample_sections_dir,
        "imgformat": "png",
        "scale":0.1,
        "apply_scale": "True",
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
    renderapi.stack.delete_stack(output_stack, render=render)


@pytest.fixture(scope='module')
def montage_z_mapped_stack(render, montage_stack, downsample_sections_dir):
    output_stack = '{}_mapped_DS'.format(montage_stack)
    params = {
        "render": render_params,
        "montage_stack": montage_stack,
        "output_stack": output_stack,
        "image_directory": downsample_sections_dir,
        "imgformat": "png",
        "scale": 0.1,
        "zstart": 1020,
        "zend": 1022,
        "set_new_z": True,
        "new_z_start": 251
    }
    outjson = 'test_montage_scape_output.json'
    mod = MakeMontageScapeSectionStack(input_data=params, args=['--output_json', outjson])
    mod.run()

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, output_stack)
    zs = [251, 252, 253]

    yield output_stack
    renderapi.stack.delete_stack(output_stack, render=render)


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
def rough_mapped_pt_match_collection(render, rough_mapped_pt_matches_from_json):
    pt_match_collection = 'rough_mapped_point_match_collection'
    renderapi.pointmatch.import_matches(pt_match_collection,
                                        rough_mapped_pt_matches_from_json,
                                        render=render)

    # check if point matches have been imported properly
    groupIds = render.run(renderapi.pointmatch.get_match_groupIds, pt_match_collection)
    assert(len(groupIds) == 3)
    yield pt_match_collection
    render.run(renderapi.pointmatch.delete_collection, pt_match_collection)


@pytest.fixture(scope="module")
def test_do_mapped_rough_alignment(render, montage_z_mapped_stack, rough_mapped_pt_match_collection, tmpdir_factory, output_lowres_stack=None):
    if output_lowres_stack == None:
        output_lowres_stack = '{}_DS_Rough'.format(montage_z_mapped_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_ex = dict(solver_example, **{
        'output_json': os.path.join(output_directory,'output.json'),
        'first_section': 251,
        'last_section': 253,
        'source_collection': dict(solver_example['source_collection'], **{
            'stack': montage_z_mapped_stack}),
        'target_collection': dict(solver_example['target_collection'], **{
            'stack': output_lowres_stack}),
        'source_point_match_collection': dict(
            solver_example['source_point_match_collection'], **{
                'match_collection': rough_mapped_pt_match_collection
            })
    })

    mod = SolveRoughAlignmentModule(input_data=solver_ex, args=[])
    mod.run()

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, output_lowres_stack)
    zs = [251, 252, 253]
    assert(set(zvalues) == set(zs))

    yield output_lowres_stack
    renderapi.stack.delete_stack(output_lowres_stack, render=render)



@pytest.fixture(scope='module')
def test_do_rough_alignment(render, montage_scape_stack, rough_point_match_collection, tmpdir_factory, output_lowres_stack=None):
    if output_lowres_stack == None:
        output_lowres_stack = '{}_DS_Rough'.format(montage_scape_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_ex = dict(solver_example, **{
        'output_json': os.path.join(output_directory,'output.json'),
        'source_collection': dict(solver_example['source_collection'], **{
            'stack': montage_scape_stack}),
        'target_collection': dict(solver_example['target_collection'], **{
            'stack': output_lowres_stack}),
        'source_point_match_collection': dict(
            solver_example['source_point_match_collection'], **{
                'match_collection': rough_point_match_collection
            })
    })
    """
    solver_ex = copy.copy(solver_example)
    solver_ex['output_json']=os.path.join(output_directory,'output.json')

    solver_ex['source_collection']['stack'] = montage_scape_stack
    solver_ex['target_collection']['stack'] = output_lowres_stack
    solver_ex['source_point_match_collection']['match_collection'] = rough_point_match_collection
    """


    mod = SolveRoughAlignmentModule(input_data=solver_ex, args=[])
    mod.run()

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, output_lowres_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))

    yield output_lowres_stack
    renderapi.stack.delete_stack(output_lowres_stack, render=render)


@pytest.fixture(scope='module')
def test_do_rough_alignment_with_scale(render, montage_scape_stack_with_scale, rough_point_match_collection, tmpdir_factory, output_lowres_stack=None):
    if output_lowres_stack == None:
        output_lowres_stack = '{}_DS_Rough_scale'.format(montage_scape_stack_with_scale)

    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_ex = dict(solver_example, **{
        'output_json': os.path.join(output_directory,'output.json'),
        'source_collection': dict(solver_example['source_collection'], **{
            'stack': montage_scape_stack_with_scale}),
        'target_collection': dict(solver_example['target_collection'], **{
            'stack': output_lowres_stack}),
        'source_point_match_collection': dict(
            solver_example['source_point_match_collection'], **{
                'match_collection': rough_point_match_collection
            })
    })

    mod = SolveRoughAlignmentModule(input_data=solver_ex, args=[])
    mod.run()

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, output_lowres_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))

    yield output_lowres_stack
    renderapi.stack.delete_stack(output_lowres_stack, render=render)



def test_montage_scape_stack(render, montage_scape_stack):
    zvalues = render.run(renderapi.stack.get_z_values_for_stack, montage_scape_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues)==set(zs))
'''
def test_montage_scape_stack_code_coverage(render, montage_stack, downsample_sections_dir):
    output_stack = '{}_DS_code_coverage'.format(montage_stack)
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
    tagstr = "%s.0_%s.0" % (params['zstart'], params['zend'])
    Z = [1020, 1020]
    create_montage_scape_tile_specs(render,
                                    params['montage_stack'],
                                    params['image_directory'],
                                    params['scale'],
                                    render_params['project'],
                                    tagstr,
                                    params['imgformat'],
                                    Z)
'''

def test_point_match_collection(render, rough_point_match_collection):
    groupIds = render.run(renderapi.pointmatch.get_match_groupIds, rough_point_match_collection)
    assert(('1020.0' in groupIds) and ('1021.0' in groupIds) and ('1022.0' in groupIds))


def test_mapped_apply_rough_alignment_transform(render, montage_stack, test_do_mapped_rough_alignment, tmpdir_factory, prealigned_stack=None, output_stack=None):
    ex = dict(ex1, **{
        'render': dict(ex1['render'], **render_params),
        'montage_stack': montage_stack,
        'lowres_stack': test_do_mapped_rough_alignment,
        'prealigned_stack': None,
        'output_stack': '{}_Rough'.format(montage_stack),
        'tilespec_directory': str(tmpdir_factory.mktemp('scratch')),
        'old_z': [1020, 1021, 1022],
        'new_z': [251, 252, 253],
        'map_z':True,
        'scale': 0.1,
        'pool_size': pool_size,
        'output_json': str(tmpdir_factory.mktemp('output').join('output.json')),
        'loglevel': 'DEBUG'
    })

    mod = ApplyRoughAlignmentTransform(input_data=ex, args=[])
    mod.run()

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, ex['output_stack'])
    zs = [251, 252, 253]
    assert(set(zvalues) == set(zs))

    # test for map_z_start validation error
    ex4 = dict(ex, **{'new_z': [-1]})

    with pytest.raises(mm.ValidationError):
        mod = ApplyRoughAlignmentTransform(input_data=ex4, args=[])



def test_apply_rough_alignment_transform(render, montage_stack, test_do_rough_alignment, tmpdir_factory, prealigned_stack=None, output_stack=None):

    ex = dict(ex1, **{
        'render': dict(ex1['render'], **render_params),
        'montage_stack': montage_stack,
        'lowres_stack': test_do_rough_alignment,
        'prealigned_stack': None,
        'output_stack': '{}_Rough'.format(montage_stack),
        'tilespec_directory': str(tmpdir_factory.mktemp('scratch')),
        'old_z': [1020, 1021, 1022],
        'scale': 0.1,
        'pool_size': pool_size,
        'output_json': str(tmpdir_factory.mktemp('output').join('output.json')),
        'loglevel': 'DEBUG'
    })
    #ex2 = dict(ex, **{'minZ': 1022, 'maxZ': 1020})
    #ex4 = dict(ex, **{'map_z': True, 'map_z_start': -1})

    mod = ApplyRoughAlignmentTransform(input_data=ex, args=[])
    mod.run()

    #zend = ex['maxZ']
    #zstart = ex['minZ']
    zstart = 1020
    zend = 1022

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, ex['output_stack'])
    zs = range(zstart, zend+1)

    assert(set(zvalues) == set(zs))
    for z in zs:
        # WARNING: montage stack should be different than output stack
        in_resolvedtiles = render.run(
            renderapi.resolvedtiles.get_resolved_tiles_from_z,
                ex['montage_stack'], z)
        out_resolvedtiles = render.run(
            renderapi.resolvedtiles.get_resolved_tiles_from_z,
                ex['output_stack'], z)
        assert in_resolvedtiles.transforms
        assert in_resolvedtiles.transforms == out_resolvedtiles.transforms
        assert all([isinstance(
            ts.tforms[0], renderapi.transform.ReferenceTransform)
                    for ts in out_resolvedtiles.tilespecs])



# additional tests for code coverage
def test_render_downsample_with_mipmaps(render, one_tile_montage, tmpdir_factory, test_do_rough_alignment, montage_stack):
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

    ex2 = dict(ex, **{'minZ': 1021, 'maxZ': 1020})
    ex3 = dict(ex2, **{'minZ': 1 , 'maxZ': 2})

    #stack_has_mipmaps = check_stack_for_mipmaps(render, ex['input_stack'], [1020])
    # tempjson = create_tilespecs_without_mipmaps(render, ex['input_stack'], 0, 1020)

    # generate tilespecs used for rendering stack input
    maxlvl = 1
    tspecs = create_tilespecs_without_mipmaps(render, ex['input_stack'], maxlvl, 1020)
    ts_levels = {int(i) for l in (ts.ip.levels for ts in tspecs) for i in l}
    # levels > maxlevel should not be included if
    assert not ts_levels.difference(set(range(maxlvl + 1)))

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

    mod = RenderSectionAtScale(input_data=ex2, args=[])
    with pytest.raises(RenderModuleException):
        mod.run()

    mod = RenderSectionAtScale(input_data=ex3, args=[])
    with pytest.raises(RenderModuleException):
        mod.run()

    ex2 = dict(ex1, **{
        'set_new_z': False,
        'output_stack': 'failed_output',
        'render': dict(ex1['render'], **render_params),
        'montage_stack': montage_stack,
        'lowres_stack': test_do_rough_alignment,
        'prealigned_stack': None,
        'tilespec_directory': str(tmpdir_factory.mktemp('scratch')),
        'old_z': [1020, 1021, 1022],
        'scale': 0.1,
        'pool_size': pool_size,
        'output_json': str(tmpdir_factory.mktemp('output').join('output.json')),
        'loglevel': 'DEBUG'
        })
    with pytest.raises(RenderModuleException):
        renderapi.stack.set_stack_state(ex2['lowres_stack'],'LOADING',render=render)
        renderapi.stack.delete_section(ex2['lowres_stack'],1021,render=render)
        renderapi.stack.set_stack_state(ex2['lowres_stack'],'COMPLETE',render=render)
        mod = ApplyRoughAlignmentTransform(input_data=ex2, args=[])
        mod.run()
        zvalues = renderapi.stack.get_z_values_for_stack(ex2['output_stack'],render=render)
        assert(1021 not in zvalues)


def make_montage_stack_without_downsamples(render, one_tile_montage, tmpdir_factory):
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
    #mod = MakeMontageScapeSectionStack(input_data=params, args=['--output_json', outjson])
    #mod.run()

    tagstr = "%s.0_%s.0" % (params['zstart'], params['zend'])
    Z = [1020, 1020]

    tilespecdir = os.path.join(params['image_directory'],
                                   render_params['project'],
                                   params['montage_stack'],
                                   'sections_at_%s'%str(params['scale']),
                                   'tilespecs_%s'%tagstr)

    if not os.path.exists(tilespecdir):
        os.makedirs(tilespecdir)

    create_montage_scape_tile_specs(render,
                                    params['montage_stack'],
                                    params['image_directory'],
                                    params['scale'],
                                    render_params['project'],
                                    tagstr,
                                    params['imgformat'],
                                    Z,
                                    pool_size=pool_size)


def test_make_montage_stack_module_without_downsamples(
        render, one_tile_montage, tmpdir_factory):
    # testing for make montage scape stack without having downsamples generated
    tmp_dir = str(tmpdir_factory.mktemp('downsample'))
    output_stack = '{}_Downsample'.format(one_tile_montage)
    params = {
        "render": render_params,
        "montage_stack": one_tile_montage,
        "output_stack": output_stack,
        "image_directory": tmp_dir,
        "imgformat": "png",
        "scale": 0.1,
        "zstart": 1020,
        "zend": 1020
    }

    outjson = 'test_montage_scape_output.json'
    mod = MakeMontageScapeSectionStack(
        input_data=params, args=['--output_json', outjson])
    mod.run()

    tspecs = render.run(
        renderapi.tilespec.get_tile_specs_from_stack, output_stack)

    tsfn = urllib.parse.unquote(urllib.parse.urlparse(
        tspecs[0].ip[0].imageUrl).path)
    assert os.path.isfile(tsfn)
    assert os.path.basename(tsfn) == '1020.0.png'

def test_apply_rough_alignment_transform_with_scale(render, montage_stack, test_do_rough_alignment_with_scale, tmpdir_factory, prealigned_stack=None, output_stack=None):
    ex = dict(ex1, **{
        'render': dict(ex1['render'], **render_params),
        'montage_stack': montage_stack,
        'lowres_stack': test_do_rough_alignment_with_scale,
        'prealigned_stack': None,
        'output_stack': '{}_Rough_scaled'.format(montage_stack),
        'tilespec_directory': str(tmpdir_factory.mktemp('scratch')),
        'old_z': [1020, 1021, 1022],
        'scale': 0.1,
        'apply_scale':"True",
        'pool_size': pool_size,
        'output_json': str(tmpdir_factory.mktemp('output').join('output.json')),
        'loglevel': 'DEBUG'
    })
    mod = ApplyRoughAlignmentTransform(input_data=ex, args=[])
    mod.run()

    zstart = 1020
    zend = 1022

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, ex['output_stack'])
    zs = range(zstart, zend+1)

    assert(set(zvalues) == set(zs))
    for z in zs:
        # WARNING: montage stack should be different than output stack
        in_resolvedtiles = render.run(
            renderapi.resolvedtiles.get_resolved_tiles_from_z,
                ex['montage_stack'], z)
        out_resolvedtiles = render.run(
            renderapi.resolvedtiles.get_resolved_tiles_from_z,
                ex['output_stack'], z)
        assert in_resolvedtiles.transforms
        assert in_resolvedtiles.transforms == out_resolvedtiles.transforms
        assert all([isinstance(
            ts.tforms[0], renderapi.transform.ReferenceTransform)
                    for ts in out_resolvedtiles.tilespecs])





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
    params_RMEx = dict(params, **{'set_new_z': False, 'zstart': 1, 'zend': 2})
    outjson = 'test_montage_scape_output.json'

    with pytest.raises(mm.ValidationError):
        mod = MakeMontageScapeSectionStack(input_data=params, args=['--output_json', outjson])
        mod.run()

    mod = MakeMontageScapeSectionStack(input_data=params_RMEx,
                                       args=['--output_json', outjson])
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

    zvalues = renderapi.stack.get_z_values_for_stack(output_stack, render=render)
    assert(set(zvalues) == set([1020, 1021, 1022]))



def test_solver_default_options(render, montage_scape_stack, rough_point_match_collection, tmpdir_factory):
    output_lowres_stack = '{}_DS_Rough'.format(montage_scape_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))

    solver_ex1 = dict(solver_example, **{
        'output_json': os.path.join(output_directory,'output.json'),
        'source_collection': dict(solver_example['source_collection'], **{
            'stack': montage_scape_stack,
            'owner': None,
            'project': None,
            'service_host': None,
            'baseURL': None,
            'renderbinPath': None}),
        'target_collection': dict(solver_example['target_collection'], **{
            'stack': output_lowres_stack,
            'owner': None,
            'project': None,
            'service_host': None,
            'baseURL': None,
            'renderbinPath': None}),
        'source_point_match_collection': dict(
            solver_example['source_point_match_collection'], **{
                'match_collection': rough_point_match_collection,
                'server': None,
                'owner': None
            }),
        'first_section': 1020,
        'last_section': 1020})

    solver_ex2 = dict(solver_ex1, **{
        'first_section': 1022,
        'last_section': 1020})

    solver_ex3 = copy.copy(solver_ex2)

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

    mod = SolveRoughAlignmentModule(input_data=solver_ex1, args=[])

    with pytest.raises(RenderModuleException):
        mod.run()

    mod = SolveRoughAlignmentModule(input_data=solver_ex2, args=[])

    with pytest.raises(RenderModuleException):
        mod.run()

    os.environ.pop('MCRROOT', None)
    mod = SolveRoughAlignmentModule(input_data=solver_ex3, args=[])

    with pytest.raises(mm.ValidationError):
        mod.run()


def test_filterNameList_warning_makemontagescapes(tmpdir):
    warn_input = {
        "render": render_params,
        "montage_stack": "montage_stack",
        "output_stack": "output_stack",
        "image_directory": str(tmpdir),
        "imgformat": "png",
        "set_new_z": False,
        "new_z_start": 0,
        "scale": 0.1,
        "zstart": 1020,
        "zend": 1022,
        "filterListName": "notafilter"}
    with pytest.warns(UserWarning):
        mod = MakeMontageScapeSectionStack(input_data=warn_input, args=[])


def test_filterNameList_warning_rendersection(tmpdir):
    warn_input = {
        "render": render_params,
        "input_stack": "one_tile_montage",
        "image_directory": str(tmpdir),
        "imgformat": "png",
        "scale": 0.1,
        "minZ": -1,
        "maxZ": -1,
        "filterListName": "notafilter"}
    with pytest.warns(UserWarning):
        mod = RenderSectionAtScale(input_data=warn_input, args=[])
