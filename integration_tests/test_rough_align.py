
import os
import pytest
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
                       ROUGH_MASK_DIR,
                       render_params,
                       test_rough_parameters_python,
                       test_rough_parameters as solver_example,
                       apply_rough_alignment_example as ex1,
                       pool_size)

from rendermodules.module.render_module import \
        RenderModuleException
from rendermodules.materialize.render_downsample_sections \
        import RenderSectionAtScale, create_tilespecs_without_mipmaps
from rendermodules.dataimport.make_montage_scapes_stack import \
        MakeMontageScapeSectionStack, create_montage_scape_tile_specs
from rendermodules.rough_align.do_rough_alignment import \
        SolveRoughAlignmentModule
from rendermodules.rough_align.pairwise_rigid_rough import \
        PairwiseRigidRoughAlignment
from rendermodules.rough_align.make_anchor_stack import \
        MakeAnchorStack
from rendermodules.rough_align.apply_rough_alignment_to_montages import (
        ApplyRoughAlignmentTransform)
from rendermodules.solver.solve import Solve_stack
import shutil
import numpy as np


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
    tilespecs = [
            renderapi.tilespec.TileSpec(json=d)
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

    zvalues = render.run(
            renderapi.stack.get_z_values_for_stack,
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

    out_dir = os.path.join(
            image_directory,
            render_params['project'],
            montage_stack,
            'sections_at_0.1/001/0')
    assert(os.path.exists(out_dir))

    files = glob.glob(os.path.join(out_dir, '*.png'))

    assert(len(files) == len(range(ex['minZ'], ex['maxZ']+1)))

    for fil in files:
        img = os.path.join(out_dir, fil)
        assert(
                os.path.exists(img) and
                os.path.isfile(img) and
                os.path.getsize(img) > 0)

    # remove files from the previous run
    os.system("rm {}/*.png".format(out_dir))

    # set bounds to section bounds
    ex['use_stack_bounds'] = "False"

    mod = RenderSectionAtScale(input_data=ex, args=[])
    mod.run()

    out_dir = os.path.join(
            image_directory,
            render_params['project'],
            montage_stack,
            'sections_at_0.1/001/0')
    assert(os.path.exists(out_dir))

    files = glob.glob(os.path.join(out_dir, '*.png'))

    assert(len(files) == len(range(ex['minZ'], ex['maxZ']+1)))

    for fil in files:
        img = os.path.join(out_dir, fil)
        assert(
                os.path.exists(img) and
                os.path.isfile(img) and
                os.path.getsize(img) > 0)

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
        "scale": 0.1,
        "zstart": 1020,
        "zend": 1022
    }
    outjson = 'test_montage_scape_output.json'
    mod = MakeMontageScapeSectionStack(
            input_data=params,
            args=['--output_json', outjson])
    mod.run()

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, output_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))

    yield output_stack
    renderapi.stack.delete_stack(output_stack, render=render)


@pytest.fixture(scope='module')
def montage_scape_stack_with_scale(
        render, montage_stack, downsample_sections_dir):
    output_stack = '{}_DS_scale'.format(montage_stack)
    params = {
        "render": render_params,
        "montage_stack": montage_stack,
        "output_stack": output_stack,
        "image_directory": downsample_sections_dir,
        "imgformat": "png",
        "scale": 0.1,
        "apply_scale": "True",
        "zstart": 1020,
        "zend": 1022
    }
    outjson = 'test_montage_scape_output.json'
    mod = MakeMontageScapeSectionStack(
            input_data=params,
            args=['--output_json', outjson])
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
        "zend": 1021,
        "set_new_z": True,
        "new_z_start": 251
    }
    outjson = 'test_montage_scape_output.json'
    mod = MakeMontageScapeSectionStack(
            input_data=params,
            args=['--output_json', outjson])
    mod.run()

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, output_stack)
    zs = [251, 252]

    for z in zs:
        assert(z in zvalues)

    # check for overwrite = False
    params1 = {
        "render": render_params,
        "montage_stack": montage_stack,
        "output_stack": output_stack,
        "image_directory": downsample_sections_dir,
        "imgformat": "png",
        "scale": 0.1,
        "zstart": 1022,
        "zend": 1022,
        "set_new_z": True,
        "new_z_start": 253
    }
    mod = MakeMontageScapeSectionStack(
            input_data=params1,
            args=['--output_json', outjson])
    mod.run()

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, output_stack)
    zs = [251, 252, 253]

    for z in zs:
        assert(z in zvalues)

    params2 = {
        "render": render_params,
        "montage_stack": montage_stack,
        "output_stack": output_stack,
        "image_directory": downsample_sections_dir,
        "overwrite_zlayer": True,
        "imgformat": "png",
        "scale": 0.1,
        "zstart": 1022,
        "zend": 1022,
        "set_new_z": True,
        "new_z_start": 253,
        "close_stack": True
    }
    mod = MakeMontageScapeSectionStack(
            input_data=params2,
            args=['--output_json', outjson])
    mod.run()

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, output_stack)
    zs = [251, 252, 253]

    for z in zs:
        assert(z in zvalues)

    yield output_stack
    renderapi.stack.delete_stack(output_stack, render=render)


@pytest.fixture(scope='module')
def rough_point_match_collection(render, rough_point_matches_from_json):
    pt_match_collection = 'rough_point_match_collection'
    renderapi.pointmatch.import_matches(pt_match_collection,
                                        rough_point_matches_from_json,
                                        render=render)

    # check if point matches have been imported properly
    groupIds = render.run(
            renderapi.pointmatch.get_match_groupIds,
            pt_match_collection)
    assert isinstance(groupIds, list)
    # assert(len(groupIds) == 3)
    yield pt_match_collection
    render.run(renderapi.pointmatch.delete_collection, pt_match_collection)


@pytest.fixture(scope='module')
def rough_mapped_pt_match_collection(
        render, rough_mapped_pt_matches_from_json):
    pt_match_collection = 'rough_mapped_point_match_collection'
    renderapi.pointmatch.import_matches(pt_match_collection,
                                        rough_mapped_pt_matches_from_json,
                                        render=render)

    # check if point matches have been imported properly
    groupIds = render.run(
            renderapi.pointmatch.get_match_groupIds,
            pt_match_collection)
    assert(len(groupIds) == 3)
    yield pt_match_collection
    render.run(renderapi.pointmatch.delete_collection, pt_match_collection)


@pytest.fixture(scope="module")
def test_do_mapped_rough_alignment(
        render,
        montage_z_mapped_stack,
        rough_mapped_pt_match_collection,
        tmpdir_factory,
        output_lowres_stack=None):
    if output_lowres_stack is None:
        output_lowres_stack = '{}_DS_Rough'.format(montage_z_mapped_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_ex = dict(solver_example, **{
        'output_json': os.path.join(output_directory, 'output.json'),
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

    zvalues = render.run(
            renderapi.stack.get_z_values_for_stack,
            output_lowres_stack)
    zs = [251, 252, 253]
    assert(set(zvalues) == set(zs))

    yield output_lowres_stack
    renderapi.stack.delete_stack(output_lowres_stack, render=render)


@pytest.fixture(scope='module')
def test_do_rough_alignment(
        render,
        montage_scape_stack,
        rough_point_match_collection,
        tmpdir_factory,
        output_lowres_stack=None):
    if output_lowres_stack is None:
        output_lowres_stack = '{}_DS_Rough'.format(montage_scape_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_ex = dict(solver_example, **{
        'output_json': os.path.join(output_directory, 'output.json'),
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
    solver_ex['source_point_match_collection']['match_collection'] = \
            rough_point_match_collection
    """

    mod = SolveRoughAlignmentModule(input_data=solver_ex, args=[])
    mod.run()

    zvalues = render.run(
            renderapi.stack.get_z_values_for_stack,
            output_lowres_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))

    yield output_lowres_stack
    renderapi.stack.delete_stack(output_lowres_stack, render=render)


@pytest.fixture(scope='module')
def test_do_rough_alignment_with_scale(
        render,
        montage_scape_stack_with_scale,
        rough_point_match_collection,
        tmpdir_factory,
        output_lowres_stack=None):
    if output_lowres_stack is None:
        output_lowres_stack = '{}_DS_Rough_scale'.format(
                montage_scape_stack_with_scale)

    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_ex = dict(solver_example, **{
        'output_json': os.path.join(output_directory, 'output.json'),
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

    zvalues = render.run(
            renderapi.stack.get_z_values_for_stack,
            output_lowres_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))

    yield output_lowres_stack
    renderapi.stack.delete_stack(output_lowres_stack, render=render)


@pytest.fixture(scope='module')
def test_do_rough_alignment_python(
        render, montage_scape_stack, rough_point_match_collection,
        tmpdir_factory, output_lowres_stack=None):

    if output_lowres_stack is None:
        output_lowres_stack = '{}_DS_Rough_python'.format(montage_scape_stack)
    output_directory = str(tmpdir_factory.mktemp('output_json'))

    solver_input = copy.deepcopy(test_rough_parameters_python)
    solver_input['input_stack']['name'] = montage_scape_stack
    solver_input['output_stack']['name'] = output_lowres_stack
    solver_input['pointmatch']['name'] = rough_point_match_collection
    solver_input['output_json'] = os.path.join(
            output_directory,
            'python_rough_solve_output.json')

    smod = Solve_stack(input_data=solver_input, args=[])
    smod.run()

    zvalues = render.run(
            renderapi.stack.get_z_values_for_stack,
            output_lowres_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))

    yield output_lowres_stack
    renderapi.stack.delete_stack(output_lowres_stack, render=render)


def test_montage_scape_stack(render, montage_scape_stack):
    zvalues = render.run(
            renderapi.stack.get_z_values_for_stack,
            montage_scape_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))


'''
def test_montage_scape_stack_code_coverage(
    render, montage_stack, downsample_sections_dir):
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
    groupIds = render.run(
        renderapi.pointmatch.get_match_groupIds,
        rough_point_match_collection)
    assert(
        ('1020.0' in groupIds) and
        ('1021.0' in groupIds) and
        ('1022.0' in groupIds))


def test_mapped_apply_rough_alignment_transform(
        render,
        montage_stack,
        test_do_mapped_rough_alignment,
        tmpdir_factory,
        prealigned_stack=None,
        output_stack=None):
    ex = dict(ex1, **{
        'render': dict(ex1['render'], **render_params),
        'montage_stack': montage_stack,
        'lowres_stack': test_do_mapped_rough_alignment,
        'prealigned_stack': None,
        'output_stack': '{}_Rough'.format(montage_stack),
        'tilespec_directory': str(tmpdir_factory.mktemp('scratch')),
        'old_z': [1020, 1021, 1022],
        'new_z': [251, 252, 253],
        'map_z': True,
        'scale': 0.1,
        'pool_size': pool_size,
        'output_json': str(
            tmpdir_factory.mktemp('output').join('output.json')),
        'loglevel': 'DEBUG'
    })

    mod = ApplyRoughAlignmentTransform(input_data=ex, args=[])
    mod.run()

    zvalues = render.run(
            renderapi.stack.get_z_values_for_stack,
            ex['output_stack'])
    zs = [251, 252, 253]
    assert(set(zvalues) == set(zs))

    # test for map_z_start validation error
    ex4 = dict(ex, **{'new_z': [-1]})

    with pytest.raises(mm.ValidationError):
        mod = ApplyRoughAlignmentTransform(input_data=ex4, args=[])


def test_apply_rough_alignment_transform(
        render,
        montage_stack,
        test_do_rough_alignment,
        tmpdir_factory,
        prealigned_stack=None,
        output_stack=None):

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
        'output_json': str(
            tmpdir_factory.mktemp('output').join('output.json')),
        'loglevel': 'DEBUG'
    })
    # ex2 = dict(ex, **{'minZ': 1022, 'maxZ': 1020})
    # ex4 = dict(ex, **{'map_z': True, 'map_z_start': -1})

    mod = ApplyRoughAlignmentTransform(input_data=ex, args=[])
    mod.run()

    # zend = ex['maxZ']
    # zstart = ex['minZ']
    zstart = 1020
    zend = 1022

    zvalues = render.run(
            renderapi.stack.get_z_values_for_stack,
            ex['output_stack'])
    zs = range(zstart, zend+1)

    assert(set(zvalues) == set(zs))
    for z in zs:
        # WARNING: montage stack should be different than output stack
        in_resolvedtiles = render.run(
            renderapi.resolvedtiles.get_resolved_tiles_from_z,
            ex['montage_stack'],
            z)
        out_resolvedtiles = render.run(
            renderapi.resolvedtiles.get_resolved_tiles_from_z,
            ex['output_stack'],
            z)
        assert in_resolvedtiles.transforms
        assert in_resolvedtiles.transforms == out_resolvedtiles.transforms
        assert all([isinstance(
            ts.tforms[0], renderapi.transform.ReferenceTransform)
                    for ts in out_resolvedtiles.tilespecs])
    renderapi.stack.delete_stack(ex['output_stack'], render=render)


def modular_test_for_masks(render, ex):
    ex = copy.deepcopy(ex)

    mod = ApplyRoughAlignmentTransform(input_data=ex, args=[])
    mod.run()

    zstart = 1020
    zend = 1022

    zvalues = render.run(
            renderapi.stack.get_z_values_for_stack,
            ex['output_stack'])
    zs = range(zstart, zend+1)

    assert(set(zvalues) == set(zs))
    for z in zs:
        # WARNING: montage stack should be different than output stack
        in_resolvedtiles = render.run(
            renderapi.resolvedtiles.get_resolved_tiles_from_z,
            ex['montage_stack'],
            z)
        out_resolvedtiles = render.run(
            renderapi.resolvedtiles.get_resolved_tiles_from_z,
            ex['output_stack'],
            z)
        assert in_resolvedtiles.transforms
        assert in_resolvedtiles.transforms == out_resolvedtiles.transforms
        assert all([isinstance(
            ts.tforms[0], renderapi.transform.ReferenceTransform)
                for ts in out_resolvedtiles.tilespecs])


def test_apply_rough_alignment_with_masks(
        render,
        montage_stack,
        test_do_rough_alignment_python,
        tmpdir_factory,
        prealigned_stack=None,
        output_stack=None):

    ex = dict(ex1, **{
        'render': dict(ex1['render'], **render_params),
        'montage_stack': montage_stack,
        'lowres_stack': test_do_rough_alignment_python,
        'prealigned_stack': None,
        'output_stack': '{}_Rough'.format(montage_stack),
        'tilespec_directory': str(tmpdir_factory.mktemp('scratch')),
        'old_z': [1020, 1021, 1022],
        'scale': 0.1,
        'pool_size': pool_size,
        'output_json': str(
            tmpdir_factory.mktemp('output').join('output.json')),
        'loglevel': 'DEBUG'
    })

    ntiles_montage = len(renderapi.tilespec.get_tile_specs_from_stack(
        ex['montage_stack'], render=render))

    # make some clones, redirect output
    orig_montage = str(ex['montage_stack'])
    orig_lowres = str(ex['lowres_stack'])
    ex['montage_stack'] = "mask_montage_input_stack"
    ex['lowres_stack'] = "mask_rough_stack"
    renderapi.stack.clone_stack(
            orig_montage, ex['montage_stack'], render=render)

    # set mask, but neither boolean control
    renderapi.stack.clone_stack(orig_lowres, ex['lowres_stack'], render=render)
    ex['mask_input_dir'] = ROUGH_MASK_DIR
    ex['filter_montage_output_with_masks'] = False
    ex['update_lowres_with_masks'] = False
    ex['output_stack'] = "mask_montage_output_stack_no_mask"
    modular_test_for_masks(render, ex)
    ntiles = len(renderapi.tilespec.get_tile_specs_from_stack(
        ex['output_stack'], render=render))
    assert(ntiles == ntiles_montage)
    renderapi.stack.delete_stack(ex['lowres_stack'], render=render)
    renderapi.stack.delete_stack(ex['output_stack'], render=render)

    # set mask and filter the highres output
    for apply_scale in [True, False]:
        renderapi.stack.clone_stack(
                orig_lowres,
                ex['lowres_stack'],
                render=render)
        ex['mask_input_dir'] = ROUGH_MASK_DIR
        ex['filter_montage_output_with_masks'] = True
        ex['update_lowres_with_masks'] = False
        ex['output_stack'] = "mask_montage_output_stack_with_mask"
        ex['apply_scale'] = apply_scale
        modular_test_for_masks(render, ex)
        ntiles = len(renderapi.tilespec.get_tile_specs_from_stack(
            ex['output_stack'], render=render))
        assert(ntiles == ntiles_montage - 3)
        renderapi.stack.delete_stack(ex['lowres_stack'], render=render)
        renderapi.stack.delete_stack(ex['output_stack'], render=render)

    # modify the input stack
    renderapi.stack.clone_stack(orig_lowres, ex['lowres_stack'], render=render)
    ex['mask_input_dir'] = ROUGH_MASK_DIR
    ex['filter_montage_output_with_masks'] = True
    ex['update_lowres_with_masks'] = True
    ex['output_stack'] = "mask_montage_output_stack_with_mask"
    modular_test_for_masks(render, ex)
    ntiles = len(renderapi.tilespec.get_tile_specs_from_stack(
        ex['output_stack'], render=render))
    assert(ntiles == ntiles_montage - 3)
    lrs = renderapi.tilespec.get_tile_specs_from_stack(
        ex['lowres_stack'], render=render)
    assert lrs[0].ip['0']['maskUrl'] is None
    assert lrs[1].ip['0']['maskUrl'] is not None
    assert lrs[2].ip['0']['maskUrl'] is None
    # renderapi.stack.delete_stack(ex['lowres_stack'], render=render)

    # read the masks from the lowres stack (just modified above)
    ex['read_masks_from_lowres_stack'] = True
    modular_test_for_masks(render, ex)
    ntiles = len(renderapi.tilespec.get_tile_specs_from_stack(
        ex['output_stack'], render=render))
    assert(ntiles == ntiles_montage - 3)
    renderapi.stack.delete_stack(ex['lowres_stack'], render=render)
    renderapi.stack.delete_stack(ex['output_stack'], render=render)

    # make multiple matches for one tileId
    mpath = urllib.parse.unquote(
                urllib.parse.urlparse(
                    lrs[1].ip['0']['maskUrl']).path)
    mbase = os.path.splitext(os.path.basename(mpath))[0]
    tmp_dir = str(tmpdir_factory.mktemp('masks'))
    shutil.copy(mpath, os.path.join(tmp_dir, mbase + '.png'))
    shutil.copy(mpath, os.path.join(tmp_dir, mbase + '.tif'))

    renderapi.stack.clone_stack(orig_lowres, ex['lowres_stack'], render=render)
    ex['read_masks_from_lowres_stack'] = False
    ex['mask_input_dir'] = tmp_dir
    ex['filter_montage_output_with_masks'] = True
    ex['update_lowres_with_masks'] = True
    ex['output_stack'] = "mask_montage_output_stack_with_mask"
    with pytest.raises(RenderModuleException):
        modular_test_for_masks(render, ex)

    renderapi.stack.delete_stack(ex['lowres_stack'], render=render)
    renderapi.stack.delete_stack(ex['output_stack'], render=render)
    renderapi.stack.delete_stack(ex['montage_stack'], render=render)


# additional tests for code coverage
def test_render_downsample_with_mipmaps(
        render,
        one_tile_montage,
        tmpdir_factory,
        test_do_rough_alignment,
        montage_stack):
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
    ex3 = dict(ex2, **{'minZ': 1, 'maxZ': 2})

    # stack_has_mipmaps = check_stack_for_mipmaps(
    #     render, ex['input_stack'], [1020])
    # tempjson = create_tilespecs_without_mipmaps(
    #     render, ex['input_stack'], 0, 1020)

    # generate tilespecs used for rendering stack input
    maxlvl = 1
    tspecs = create_tilespecs_without_mipmaps(
            render, ex['input_stack'], maxlvl, 1020)
    ts_levels = {
            int(i) for l in (
                ts.ip.levels for ts in tspecs.tilespecs) for i in l}
    # ts_levels = {int(i) for l in (ts.ip.levels for ts in tspecs) for i in l}
    # levels > maxlevel should not be included if
    assert not ts_levels.difference(set(range(maxlvl + 1)))

    mod = RenderSectionAtScale(input_data=ex, args=[])
    mod.run()

    with open(ex['output_json'], 'r') as f:
        js = json.load(f)

    out_dir = os.path.join(
            image_directory,
            render_params['project'],
            js['temp_stack'],
            'sections_at_0.1/001/0')
    assert(os.path.exists(out_dir))

    files = glob.glob(os.path.join(out_dir, '*.png'))
    for fil in files:
        img = os.path.join(out_dir, fil)
        assert(
                os.path.exists(img) and
                os.path.isfile(img) and
                os.path.getsize(img) > 0)

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
        'output_json': str(
            tmpdir_factory.mktemp('output').join('output.json')),
        'loglevel': 'DEBUG'
        })
    with pytest.raises(RenderModuleException):
        renderapi.stack.set_stack_state(
                ex2['lowres_stack'], 'LOADING', render=render)
        renderapi.stack.delete_section(
                ex2['lowres_stack'], 1021, render=render)
        renderapi.stack.set_stack_state(
                ex2['lowres_stack'], 'COMPLETE', render=render)
        mod = ApplyRoughAlignmentTransform(input_data=ex2, args=[])
        mod.run()
        zvalues = renderapi.stack.get_z_values_for_stack(
                ex2['output_stack'], render=render)
        assert(1021 not in zvalues)

    renderapi.stack.delete_stack('failed_output', render=render)


def make_montage_stack_without_downsamples(
        render, montage_stack, tmpdir_factory):
    # testing for make montage scape stack without having downsamples generated
    tmp_dir = str(tmpdir_factory.mktemp('downsample'))
    output_stack = '{}_Downsample'.format(one_tile_montage)
    params = {
        "render": render_params,
        "montage_stack": montage_stack,
        "output_stack": output_stack,
        "image_directory": tmp_dir,
        "imgformat": "png",
        "scale": 0.1,
        "zstart": 1020,
        "zend": 1020
    }
    # outjson = 'test_montage_scape_output.json'
    # mod = MakeMontageScapeSectionStack(
    #     input_data=params, args=['--output_json', outjson])
    # mod.run()

    tagstr = "%s.0_%s.0" % (params['zstart'], params['zend'])
    Z = [1020, 1020]

    tilespecdir = os.path.join(
            params['image_directory'],
            render_params['project'],
            params['montage_stack'],
            'sections_at_%s' % str(params['scale']),
            'tilespecs_%s' % tagstr)

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

    renderapi.stack.delete_stack(output_stack, render=render)


def test_make_montage_stack_module_without_downsamples(
        render, montage_stack, tmpdir_factory):
    # testing for make montage scape stack without having downsamples generated
    tmp_dir = str(tmpdir_factory.mktemp('downsample'))
    output_stack = '{}_Downsample'.format(montage_stack)
    params = {
        "render": render_params,
        "montage_stack": montage_stack,
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
    renderapi.stack.delete_stack(output_stack, render=render)


def test_apply_rough_alignment_transform_with_scale(
        render,
        montage_stack,
        test_do_rough_alignment_with_scale,
        tmpdir_factory,
        prealigned_stack=None,
        output_stack=None):
    ex = dict(ex1, **{
        'render': dict(ex1['render'], **render_params),
        'montage_stack': montage_stack,
        'lowres_stack': test_do_rough_alignment_with_scale,
        'prealigned_stack': None,
        'output_stack': '{}_Rough_scaled'.format(montage_stack),
        'tilespec_directory': str(tmpdir_factory.mktemp('scratch')),
        'old_z': [1020, 1021, 1022],
        'scale': 0.1,
        'apply_scale': "True",
        'pool_size': pool_size,
        'output_json': str(
            tmpdir_factory.mktemp('output').join('output.json')),
        'loglevel': 'DEBUG'
    })
    mod = ApplyRoughAlignmentTransform(input_data=ex, args=[])
    mod.run()

    zstart = 1020
    zend = 1022

    zvalues = render.run(
            renderapi.stack.get_z_values_for_stack,
            ex['output_stack'])
    zs = range(zstart, zend+1)

    assert(set(zvalues) == set(zs))
    for z in zs:
        # WARNING: montage stack should be different than output stack
        in_resolvedtiles = render.run(
            renderapi.resolvedtiles.get_resolved_tiles_from_z,
            ex['montage_stack'],
            z)
        out_resolvedtiles = render.run(
            renderapi.resolvedtiles.get_resolved_tiles_from_z,
            ex['output_stack'],
            z)
        assert in_resolvedtiles.transforms
        assert in_resolvedtiles.transforms == out_resolvedtiles.transforms
        assert all([isinstance(
            ts.tforms[0], renderapi.transform.ReferenceTransform)
                    for ts in out_resolvedtiles.tilespecs])

    renderapi.stack.delete_stack(ex['output_stack'], render=render)


def test_make_montage_scape_stack_fail(
        render, montage_stack, downsample_sections_dir):
    output_stack = '{}_DS'.format(montage_stack)
    params = {
        "render": render_params,
        "montage_stack": montage_stack,
        "output_stack": output_stack,
        "image_directory": downsample_sections_dir,
        "imgformat": "png",
        "set_new_z": True,
        "new_z_start": -1,
        "scale": 0.1,
        "zstart": 1020,
        "zend": 1022
    }
    params_RMEx = dict(params, **{'set_new_z': False, 'zstart': 1, 'zend': 2})
    outjson = 'test_montage_scape_output.json'

    with pytest.raises(mm.ValidationError):
        mod = MakeMontageScapeSectionStack(
                input_data=params, args=['--output_json', outjson])
        mod.run()

    mod = MakeMontageScapeSectionStack(input_data=params_RMEx,
                                       args=['--output_json', outjson])
    with pytest.raises(RenderModuleException):
        mod.run()


def test_setting_new_z_montage_scape(
        render, montage_stack, downsample_sections_dir):
    output_stack = '{}_DS'.format(montage_stack)
    params = {
        "render": render_params,
        "montage_stack": montage_stack,
        "output_stack": output_stack,
        "image_directory": downsample_sections_dir,
        "imgformat": "png",
        "set_new_z": True,
        "new_z_start": -1,
        "scale": 0.1,
        "zstart": 1020,
        "zend": 1022
    }
    outjson = 'test_montage_scape_output.json'
    with pytest.raises(mm.ValidationError):
        mod = MakeMontageScapeSectionStack(
                input_data=params, args=['--output_json', outjson])
        del mod

    zvalues = renderapi.stack.get_z_values_for_stack(
            output_stack, render=render)
    assert(set(zvalues) == set([1020, 1021, 1022]))


def test_solver_default_options(
        render,
        montage_scape_stack,
        rough_point_match_collection,
        tmpdir_factory):
    output_lowres_stack = '{}_DS_Rough'.format(montage_scape_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))

    solver_ex1 = dict(solver_example, **{
        'output_json': os.path.join(output_directory, 'output.json'),
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
    # solver_example['solver_options']['pastix'] = None

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


def test_make_anchor_stack(
        render,
        montage_scape_stack,
        tmpdir_factory):

    zs = renderapi.stack.get_z_values_for_stack(
            montage_scape_stack,
            render=render)

    # make some transforms that would come from a manual trakem alignment
    transforms = {}
    for z in zs[:-1]:
        tf = renderapi.transform.AffineModel(
                M00=1.0 + np.random.randn(),
                M11=1.0 + np.random.randn())
        transforms["%d_blah.png" % z] = tf.to_dict()
    output_directory = str(tmpdir_factory.mktemp('anchor_stack_input'))
    tjson_path = os.path.join(output_directory, 'human_made_transforms.json')
    with open(tjson_path, 'w') as f:
        json.dump(transforms, f, indent=2)

    anchor_stack = "my_anchor_stack"
    ex = {
            "render": dict(solver_example['render']),
            "input_stack": montage_scape_stack,
            "output_stack": anchor_stack,
            "transform_json": tjson_path,
            "close_stack": True
            }
    mmod = MakeAnchorStack(input_data=ex, args=[])
    mmod.run()

    tspecs = renderapi.tilespec.get_tile_specs_from_stack(
            ex['output_stack'], render=render)
    for t in tspecs:
        assert len(t.tforms) == 1
        for tf in transforms:
            if tf.startswith('%d_' % t.z):
                assert t.tforms[0].dataString == transforms[tf]['dataString']

    # pedantic, what if a downsample stack has multiple tiles for one z
    other_stack = "other_stack"
    renderapi.stack.clone_stack(
            montage_scape_stack, other_stack, render=render)
    tspecs = renderapi.tilespec.get_tile_specs_from_stack(
            other_stack, render=render)
    t = tspecs[0]
    t.tileId = 'something_unique'
    renderapi.client.import_tilespecs(other_stack, [t], render=render)
    ex['input_stack'] = other_stack
    mmod = MakeAnchorStack(input_data=ex, args=[])
    with pytest.raises(RenderModuleException):
        mmod.run()
    renderapi.stack.delete_stack(other_stack, render=render)

    # add a z to the transforms that isn't in the stack
    ztry = zs[-1] + 1
    while ztry in zs:
        ztry += 1
    tf = renderapi.transform.AffineModel(
                M00=1.0 + np.random.randn(),
                M11=1.0 + np.random.randn())
    transforms["%d_blah.png" % ztry] = tf.to_dict()
    with open(tjson_path, 'w') as f:
        json.dump(transforms, f, indent=2)
    ex['input_stack'] = montage_scape_stack
    mmod = MakeAnchorStack(input_data=ex, args=[])
    with pytest.raises(renderapi.errors.RenderError):
        mmod.run()
    renderapi.stack.delete_stack(ex['output_stack'], render=render)


def calc_residuals(tspecs, matches):
    tids = np.array([t.tileId for t in tspecs])
    res = []
    for m in matches:
        pind = np.argwhere(tids == m['pId']).flatten()[0]
        qind = np.argwhere(tids == m['qId']).flatten()[0]
        p = np.array(m['matches']['p']).transpose()
        q = np.array(m['matches']['q']).transpose()
        for tf in tspecs[pind].tforms:
                p = tf.tform(p)
        for tf in tspecs[qind].tforms:
                q = tf.tform(q)
        res += np.linalg.norm(p - q, axis=1).tolist()
    return res


def test_pairwise_results(render, tmpdir_factory):
    render_params['project'] = 'rough_align_test'
    # ground truth tilespecs, some gradual rotation and translation
    nz = 10
    z = np.arange(nz)
    theta = np.arange(nz) * 0.002
    dx = np.arange(nz) * 100 + 245
    dy = np.arange(nz) * -200 - 356
    ground_truth = [renderapi.tilespec.TileSpec() for i in np.arange(nz)]
    downsample = [renderapi.tilespec.TileSpec() for i in np.arange(nz)]
    # downsample stack will have default affine
    for i in range(nz):
        c, s = np.cos(theta[i]), np.sin(theta[i])
        tf = renderapi.transform.AffineModel(
                M00=c, M01=-s, M10=s, M11=c, B0=dx[i], B1=dy[i])
        ground_truth[i].tforms = [
                renderapi.transform.AffineModel(json=tf.to_dict())]
        downsample[i].tforms = [renderapi.transform.AffineModel()]
        for tspec in [ground_truth[i], downsample[i]]:
            tspec.ip['0'] = renderapi.image_pyramid.MipMap()
            tspec.z = z[i]
            tspec.layout.sectionId = str(float(z[i]))
            tspec.tileId = '%d' % z[i]
            tspec.width = 1500
            tspec.height = 1500

    # point matches are image-based, i.e. ground truth
    # for pairwise rigid, we need them between the ground truth pairs
    matches = []
    for i in range(nz - 1):
        src = np.random.rand(10, 2) * 1500
        p = ground_truth[i].tforms[0].inverse_tform(src)
        q = ground_truth[i + 1].tforms[0].inverse_tform(src)
        w = [1.0] * 10
        matches.append({
            "pGroupId": ground_truth[i].layout.sectionId,
            "qGroupId": ground_truth[i + 1].layout.sectionId,
            "pId": ground_truth[i].tileId,
            "qId": ground_truth[i + 1].tileId,
            "matches": {
                "w": w,
                "p": p.transpose().tolist(),
                "q": q.transpose().tolist()}})

    # make the downsample stack and collection
    ds_stack = "pw_downsample_stack"
    ds_coll = "pw_downsample_collection"
    renderapi.stack.create_stack(ds_stack, render=render)
    renderapi.client.import_tilespecs(ds_stack, downsample, render=render)
    renderapi.stack.set_stack_state(ds_stack, state='COMPLETE', render=render)
    renderapi.pointmatch.import_matches(ds_coll, matches, render=render)

    # a human determines the true relative transforms for 2 sections
    transforms = {}
    transforms['%d_blah' % z[2]] = ground_truth[2].tforms[0].to_dict()
    transforms['%d_blah' % z[-1]] = ground_truth[-1].tforms[0].to_dict()
    output_directory = str(tmpdir_factory.mktemp('pairwise'))
    tjson_path = os.path.join(output_directory, 'human_made_transforms.json')
    with open(tjson_path, 'w') as f:
        json.dump(transforms, f, indent=2)

    # make an anchor stack from that
    anchor_stack = "an_anchor_stack"
    ex = {
            "render": dict(render_params),
            "input_stack": ds_stack,
            "output_stack": anchor_stack,
            "transform_json": tjson_path,
            "close_stack": True
            }
    mmod = MakeAnchorStack(input_data=ex, args=[])
    mmod.run()

    aligned_stack = "aligned_stack"
    pw_example = {
            "render": dict(render_params),
            "input_stack": ds_stack,
            "output_stack": aligned_stack,
            "anchor_stack": anchor_stack,
            "match_collection": ds_coll,
            "close_stack": True,
            "minZ": z[0],
            "maxZ": z[-1],
            "gap_file": None,
            "pool_size": 2,
            "output_json": os.path.join(output_directory, 'output.json'),
            "overwrite_zlayer": True,
            "translate_to_positive": True,
            "translation_buffer": [50, 50]
            }
    pwmod = PairwiseRigidRoughAlignment(input_data=dict(pw_example), args=[])
    pwmod.run()

    with open(pwmod.args['output_json'], 'r') as f:
        pwout = json.load(f)

    # check the residuals
    new_specs = renderapi.tilespec.get_tile_specs_from_stack(
            pwout['output_stack'], render=render)
    res_new = calc_residuals(new_specs, matches)
    assert np.all(np.array(res_new) < 1.0)

    # everything rotated correctly?
    assert np.all(np.isclose(
        theta,
        np.array([t.tforms[0].rotation for t in new_specs])))

    # in this artificial example, the ground truth is changing
    # in a smooth linear way, we can check the results are
    # weighted linear averages of the anchors
    for i in range(2, 9):
        assert np.all(
                np.isclose(
                    new_specs[i].tforms[0].M,
                    (new_specs[2].tforms[0].M * (7 - np.abs(2 - i)) +
                        new_specs[9].tforms[0].M * (7 - np.abs(9 - i))) / 7,
                    1e-3))

    # finally, the module gives good residuals without an anchor stack
    # one should just be careful doing this over long stretches
    # as it may lead to some undesired, unphysical long-range drift
    # in the solution
    pw_example['anchor_stack'] = None
    pwmod = PairwiseRigidRoughAlignment(input_data=dict(pw_example), args=[])
    pwmod.run()
    with open(pwmod.args['output_json'], 'r') as f:
        pwout = json.load(f)
    # check the residuals
    new_specs = renderapi.tilespec.get_tile_specs_from_stack(
            pwout['output_stack'], render=render)
    res_new = calc_residuals(new_specs, matches)
    assert np.all(np.array(res_new) < 1.0)

    # delete the render things
    renderapi.stack.delete_stack(ds_stack, render=render)
    renderapi.stack.delete_stack(anchor_stack, render=render)
    renderapi.stack.delete_stack(pwout['output_stack'], render=render)
    renderapi.pointmatch.delete_collection(ds_coll, render=render)


def test_pairwise_rigid_alignment_coverage(
        render,
        montage_scape_stack,
        rough_point_match_collection,
        tmpdir_factory):
    output_lowres_stack = '{}_DS_Pairwise_rigid'.format(montage_scape_stack)

    output_directory = str(tmpdir_factory.mktemp('pwr_output_json'))

    example = {
            "render": dict(solver_example['render']),
            "input_stack": montage_scape_stack,
            "output_stack": output_lowres_stack,
            "match_collection": rough_point_match_collection,
            "close_stack": True,
            "minZ": 1020,
            "maxZ": 1022,
            "gap_file": None,
            "pool_size": 2,
            "output_json": os.path.join(output_directory, 'output.json'),
            "overwrite_zlayer": True,
            "translate_to_positive": True,
            "translation_buffer": [50, 50]
            }

    # normal
    ex = dict(example)
    pwmod = PairwiseRigidRoughAlignment(input_data=ex, args=[])
    pwmod.run()
    with open(ex['output_json'], 'r') as f:
        outj = json.load(f)
    assert(outj['masked'] == [])
    assert(outj['missing'] == [])
    assert(len(outj['residuals']) == 2)
    renderapi.stack.delete_stack(
            pwmod.output_stack, render=render)

    # gap file
    ex = dict(example)
    gapfile = os.path.join(output_directory, "gapfile.json")
    with open(gapfile, 'w') as f:
        json.dump({"1020": "gap for some reason"}, f)
    ex['gap_file'] = gapfile
    pwmod = PairwiseRigidRoughAlignment(input_data=ex, args=[])
    pwmod.run()
    with open(ex['output_json'], 'r') as f:
        outj = json.load(f)
    assert(outj['masked'] == [])
    assert(outj['missing'] == [1020])
    assert(len(outj['residuals']) == 1)
    renderapi.stack.delete_stack(
            pwmod.output_stack, render=render)

    # make one match missing
    ex = dict(example)
    render = renderapi.connect(**ex['render'])
    matches = renderapi.pointmatch.get_matches_outside_group(
            rough_point_match_collection,
            "1020.0",
            render=render)
    new_collection = 'with_missing'
    renderapi.pointmatch.import_matches(
            new_collection,
            matches,
            render=render)
    ex['match_collection'] = new_collection

    with pytest.raises(RenderModuleException):
        pwmod = PairwiseRigidRoughAlignment(input_data=ex, args=[])
        pwmod.run()

    renderapi.pointmatch.delete_collection(
            new_collection, render=render)
    renderapi.stack.delete_stack(
            pwmod.output_stack, render=render)


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
        del mod


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
        del mod
