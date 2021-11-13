import os
import pytest
import renderapi
import random
import json
import glob
import copy
import re
import marshmallow as mm
import six
from six.moves import urllib
from test_data import (
        ROUGH_MONTAGE_TILESPECS_JSON,
        ROUGH_MONTAGE_TRANSFORM_JSON,
        ROUGH_POINT_MATCH_COLLECTION,
        ROUGH_DS_TEST_TILESPECS_JSON,
        ROUGH_MAPPED_PT_MATCH_COLLECTION,
        ROUGH_MASK_DIR,
        NONLINEAR_ROUGH_DS_RESOLVEDTILES_JSON,
        NONLINEAR_ROUGH_RAW_RESOLVEDTILES_JSON,
        NONLINEAR_ROUGH_DS_SCALE,
        render_params,
        test_rough_parameters_python,
        apply_rough_alignment_example as ex1,
        rough_solver_example as solver_input,
        pool_size)
from rendermodules.module.render_module import RenderModuleException
from rendermodules.materialize.render_downsample_sections import (
    RenderSectionAtScale, create_tilespecs_without_mipmaps)
from rendermodules.dataimport.make_montage_scapes_stack import (
    MakeMontageScapeSectionStack, create_montage_scape_tile_specs)
from rendermodules.solver.solve import Solve_stack
from rendermodules.rough_align.apply_rough_alignment_to_montages import (
    ApplyRoughAlignmentTransform)
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

    out_dir = os.path.join(
        image_directory, render_params['project'], montage_stack,
        'sections_at_0.1/001/0')
    assert(os.path.exists(out_dir))

    files = glob.glob(os.path.join(out_dir, '*.png'))

    assert(len(files) == len(range(ex['minZ'], ex['maxZ']+1)))

    for fil in files:
        img = os.path.join(out_dir, fil)
        assert(os.path.exists(img) and
               os.path.isfile(img) and
               os.path.getsize(img) > 0)

    # remove files from the previous run
    os.system("rm {}/*.png".format(out_dir))

    # set bounds to section bounds
    ex['use_stack_bounds'] = "False"

    mod = RenderSectionAtScale(input_data=ex, args=[])
    mod.run()

    out_dir = os.path.join(
        image_directory, render_params['project'], montage_stack,
        'sections_at_0.1/001/0')
    assert(os.path.exists(out_dir))

    files = glob.glob(os.path.join(out_dir, '*.png'))

    assert(len(files) == len(range(ex['minZ'], ex['maxZ']+1)))

    for fil in files:
        img = os.path.join(out_dir, fil)
        assert(os.path.exists(img) and
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
        "zend": 1022,
        "uuid_prefix": False
    }
    outjson = 'test_montage_scape_output.json'
    mod = MakeMontageScapeSectionStack(
        input_data=params, args=['--output_json', outjson])
    mod.run()

    zvalues = render.run(renderapi.stack.get_z_values_for_stack, output_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))

    yield output_stack
    renderapi.stack.delete_stack(output_stack, render=render)


@pytest.fixture(scope='module')
def montage_scape_stack_with_scale(render, montage_stack,
                                   downsample_sections_dir):
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
        "zend": 1022,
        "uuid_prefix": False
    }
    outjson = 'test_montage_scape_output.json'
    mod = MakeMontageScapeSectionStack(
        input_data=params, args=['--output_json', outjson])
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
        "new_z_start": 251,
        "uuid_prefix": False
    }
    outjson = 'test_montage_scape_output.json'
    mod = MakeMontageScapeSectionStack(
        input_data=params, args=['--output_json', outjson])
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
        "new_z_start": 253,
        "uuid_prefix": False
    }
    mod = MakeMontageScapeSectionStack(
        input_data=params1, args=['--output_json', outjson])
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
        "close_stack": True,
        "uuid_prefix": False
    }
    mod = MakeMontageScapeSectionStack(
        input_data=params2, args=['--output_json', outjson])
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
        renderapi.pointmatch.get_match_groupIds, pt_match_collection)
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
        renderapi.pointmatch.get_match_groupIds, pt_match_collection)
    assert(len(groupIds) == 3)
    yield pt_match_collection
    render.run(renderapi.pointmatch.delete_collection, pt_match_collection)


@pytest.fixture(scope="module")
def test_do_mapped_rough_alignment_python(
        render,
        montage_z_mapped_stack,
        rough_mapped_pt_match_collection,
        tmpdir_factory,
        output_lowres_stack=None):
    if output_lowres_stack is None:
        output_lowres_stack = '{}_mapped_Rough_python'.format(
            montage_z_mapped_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))

    solver_ex_py = copy.deepcopy(solver_input)
    solver_ex_py = dict(solver_ex_py, **{
        'first_section': 251,
        'last_section': 253,
        'solve_type': "3D",
        'transformation': "rigid",
        'input_stack': dict(solver_input['input_stack'], **{
            'name': montage_z_mapped_stack,
            'db_interface': "render"
        }),
        'output_stack': dict(solver_input['output_stack'], **{
            "name": "temp_stack",
            "db_interface": "render"
        }),
        'pointmatch': dict(solver_input['pointmatch'], **{
            'name': rough_mapped_pt_match_collection,
            'db_interface': "render"
        }),
        'matrix_assembly': dict(solver_input['matrix_assembly'], **{
            'montage_pt_weight': 0,
            'cross_pt_weight': 1.0
        })
    })

    out_json = os.path.join(output_directory, "output.json")

    mod = Solve_stack(
        input_data=solver_ex_py, args=["--output_json", out_json])
    mod.run()

    solver_ex_py['input_stack']['name'] = "temp_stack"
    solver_ex_py['tranformation'] = "AffineModel"
    solver_ex_py['output_stack']['name'] = output_lowres_stack
    mod = Solve_stack(
        input_data=solver_ex_py, args=["--output_json", out_json])
    mod.run()

    stacks = renderapi.render.get_stacks_by_owner_project(render=render)
    assert(output_lowres_stack in stacks)

    zvalues = render.run(
        renderapi.stack.get_z_values_for_stack, output_lowres_stack)
    zs = [251, 252, 253]
    assert(set(zvalues) == set(zs))

    renderapi.stack.delete_stack("temp_stack", render=render)

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
        output_directory, 'python_rough_solve_output.json')

    smod = Solve_stack(input_data=solver_input, args=[])
    smod.run()

    zvalues = render.run(
        renderapi.stack.get_z_values_for_stack, output_lowres_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))

    yield output_lowres_stack


@pytest.fixture(scope='module')
def rough_downsample_stack(
        render, montage_scape_stack, rough_point_match_collection,
        tmpdir_factory):
    out_stack = '{}_DS_Rough'.format(montage_scape_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_ex_py = copy.deepcopy(solver_input)
    solver_ex_py = dict(solver_ex_py, **{
        'first_section': 1020,
        'last_section': 1022,
        'solve_type': "3D",
        'transformation': "rigid",
        'input_stack': dict(solver_input['input_stack'], **{
            'name': montage_scape_stack,
            'db_interface': "render"
        }),
        'output_stack': dict(solver_input['output_stack'], **{
            "name": "temp_stack",
            "db_interface": "render"
        }),
        'pointmatch': dict(solver_input['pointmatch'], **{
            'name': rough_point_match_collection,
            'db_interface': "render"
        }),
        'matrix_assembly': dict(solver_input['matrix_assembly'], **{
            'montage_pt_weight': 0,
            'cross_pt_weight': 1.0
        })
    })

    out_json = os.path.join(output_directory, "output.json")

    mod = Solve_stack(
        input_data=solver_ex_py, args=["--output_json", out_json])
    mod.run()

    solver_ex_py['input_stack']['name'] = "temp_stack"
    solver_ex_py['tranformation'] = "AffineModel"
    solver_ex_py['output_stack']['name'] = out_stack
    mod = Solve_stack(
        input_data=solver_ex_py, args=["--output_json", out_json])
    mod.run()

    stacks = renderapi.render.get_stacks_by_owner_project(render=render)
    assert(out_stack in stacks)
    yield out_stack
    renderapi.stack.delete_stack(out_stack, render=render)


def test_montage_scape_stack(render, montage_scape_stack):
    zvalues = render.run(
        renderapi.stack.get_z_values_for_stack, montage_scape_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))


def test_point_match_collection(render, rough_point_match_collection):
    groupIds = render.run(
        renderapi.pointmatch.get_match_groupIds, rough_point_match_collection)
    assert(('1020.0' in groupIds) and
           ('1021.0' in groupIds) and
           ('1022.0' in groupIds))


def test_apply_rough_alignment_transform(
        render,
        montage_stack,
        rough_downsample_stack,
        tmpdir_factory,
        prealigned_stack=None,
        output_stack=None):
    ex = copy.deepcopy(ex1)
    ex = dict(ex, **{
        'render': dict(ex1['render'], **render_params),
        'montage_stack': montage_stack,
        'lowres_stack': rough_downsample_stack,
        'prealigned_stack': None,
        'output_stack': '{}_Rough'.format(montage_stack),
        'tilespec_directory': str(tmpdir_factory.mktemp('scratch')),
        'old_z': [1020, 1021, 1022],
        'scale': 0.1,
        'pool_size': pool_size,
        'output_json': str(tmpdir_factory.mktemp('output').join(
            'output.json')),
        'loglevel': 'DEBUG'
    })

    mod = ApplyRoughAlignmentTransform(input_data=ex, args=[])
    mod.run()

    zstart = 1020
    zend = 1022

    zvalues = render.run(
        renderapi.stack.get_z_values_for_stack, ex['output_stack'])
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


def modular_test_for_masks(render, ex):
    ex = copy.deepcopy(ex)

    mod = ApplyRoughAlignmentTransform(input_data=ex, args=[])
    mod.run()

    zstart = 1020
    zend = 1022

    zvalues = render.run(
        renderapi.stack.get_z_values_for_stack, ex['output_stack'])
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


def test_apply_rough_alignment_with_masks(
        render, montage_stack, test_do_rough_alignment_python,
        tmpdir_factory, prealigned_stack=None, output_stack=None):
    ex = copy.deepcopy(ex1)
    ex = dict(ex, **{
        'render': dict(ex['render'], **render_params),
        'montage_stack': montage_stack,
        'lowres_stack': test_do_rough_alignment_python,
        'prealigned_stack': None,
        'output_stack': '{}_Rough'.format(montage_stack),
        'tilespec_directory': str(tmpdir_factory.mktemp('scratch')),
        'old_z': [1020, 1021, 1022],
        'scale': 0.1,
        'pool_size': pool_size,
        'output_json': str(tmpdir_factory.mktemp('output').join(
            'output.json')),
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

    # set mask and filter the highres output
    for apply_scale in [True, False]:
        renderapi.stack.clone_stack(
            orig_lowres, ex['lowres_stack'], render=render)
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
    renderapi.stack.delete_stack(ex['output_stack'], render=render)

    # read the masks from the lowres stack (just modified above)
    ex['read_masks_from_lowres_stack'] = True
    modular_test_for_masks(render, ex)
    ntiles = len(renderapi.tilespec.get_tile_specs_from_stack(
        ex['output_stack'], render=render))
    assert(ntiles == ntiles_montage - 3)
    renderapi.stack.delete_stack(ex['lowres_stack'], render=render)

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


def test_mapped_apply_rough_alignment_transform(
            render,
            montage_stack,
            test_do_mapped_rough_alignment_python,
            tmpdir_factory,
            prealigned_stack=None,
            output_stack=None):
    ex = copy.deepcopy(ex1)
    ex = dict(ex, **{
        'render': dict(ex1['render'], **render_params),
        'montage_stack': montage_stack,
        'lowres_stack': test_do_mapped_rough_alignment_python,
        'prealigned_stack': None,
        'output_stack': '{}_Rough'.format(montage_stack),
        'tilespec_directory': str(tmpdir_factory.mktemp('scratch')),
        'old_z': [1020, 1021, 1022],
        'new_z': [251, 252, 253],
        'map_z': True,
        'scale': 0.1,
        'pool_size': pool_size,
        'output_json': str(tmpdir_factory.mktemp('output').join(
            'output.json')),
        'loglevel': 'DEBUG'
    })

    mod = ApplyRoughAlignmentTransform(input_data=ex, args=[])
    mod.run()

    zvalues = render.run(
        renderapi.stack.get_z_values_for_stack, ex['output_stack'])
    zs = [251, 252, 253]
    assert(set(zvalues) == set(zs))

    # test for map_z_start validation error
    ex4 = dict(ex, **{'new_z': [-1]})

    with pytest.raises(mm.ValidationError):
        mod = ApplyRoughAlignmentTransform(input_data=ex4, args=[])


# additional tests for code coverage
def test_render_downsample_with_mipmaps(
        render, one_tile_montage, tmpdir_factory,
        test_do_rough_alignment_python, montage_stack):
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

    # generate tilespecs used for rendering stack input
    maxlvl = 1
    tspecs = create_tilespecs_without_mipmaps(
        render, ex['input_stack'], maxlvl, 1020)
    ts_levels = {int(i) for l in (  # noqa: E741
        ts.ip.levels for ts in tspecs.tilespecs) for i in l}
    # levels > maxlevel should not be included if
    assert not ts_levels.difference(set(range(maxlvl + 1)))

    mod = RenderSectionAtScale(input_data=ex, args=[])
    mod.run()

    with open(ex['output_json'], 'r') as f:
        js = json.load(f)

    out_dir = os.path.join(
        image_directory, render_params['project'], js['temp_stack'],
        'sections_at_0.1/001/0')
    assert(os.path.exists(out_dir))

    files = glob.glob(os.path.join(out_dir, '*.png'))
    for fil in files:
        img = os.path.join(out_dir, fil)
        assert(os.path.exists(img) and
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
        'lowres_stack': test_do_rough_alignment_python,
        'prealigned_stack': None,
        'tilespec_directory': str(tmpdir_factory.mktemp('scratch')),
        'old_z': [1020, 1021, 1022],
        'scale': 0.1,
        'pool_size': pool_size,
        'output_json': str(tmpdir_factory.mktemp('output').join(
            'output.json')),
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

    tagstr = "%s.0_%s.0" % (params['zstart'], params['zend'])
    Z = [1020, 1020]

    tilespecdir = os.path.join(params['image_directory'],
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


def test_setting_remap_section_ids(render,
                                   montage_stack,
                                   rough_downsample_stack,
                                   test_do_mapped_rough_alignment_python,
                                   downsample_sections_dir,
                                   tmpdir_factory):
    output_stack = '{}_Rough'.format(montage_stack)
    params = {
        "render": render_params,
        "montage_stack": montage_stack,
        "lowres_stack": test_do_mapped_rough_alignment_python,
        "prealigned_stack": None,
        "output_stack": output_stack,
        "image_directory": downsample_sections_dir,
        "tilespec_directory": str(tmpdir_factory.mktemp('scratch')),
        "old_z": [1020, 1021, 1022],
        "new_z": [251, 252, 253],
        "map_z": True,
        "remap_section_ids": True,
        "scale": 0.1,
        "apply_scale": False,
        "consolidate_transforms": "True"
    }

    outjson = 'test_montage_scape_output.json'
    mod = ApplyRoughAlignmentTransform(
        input_data=params, args=['--output_json', outjson])
    mod.run()

    newrange = [251, 252, 253]
    zvals = renderapi.stack.get_z_values_for_stack(output_stack, render=render)
    assert([z in newrange for z in zvals])

    renderapi.stack.delete_stack(output_stack, render=render)

    params['remap_section_ids'] = False
    params['lowres_stack'] = rough_downsample_stack
    params['map_z'] = False
    mod = ApplyRoughAlignmentTransform(
        input_data=params, args=['--output_json', outjson])
    mod.run()
    rang = [1020, 1021, 1022]
    zvals = renderapi.stack.get_z_values_for_stack(output_stack, render=render)
    assert([z in rang for z in zvals])


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

    zvalues = renderapi.stack.get_z_values_for_stack(
        output_stack, render=render)
    assert(set(zvalues) == set([1020, 1021, 1022]))


def test_make_montage_stack_uuid(
        render, montage_stack, tmpdir_factory):
    # testing for make montage scape stack without having downsamples generated
    tmp_dir = str(tmpdir_factory.mktemp('downsample'))
    output_stack = '{}_Downsample_uuid'.format(montage_stack)
    uuid_len = 5
    params = {
        "render": render_params,
        "montage_stack": montage_stack,
        "output_stack": output_stack,
        "image_directory": tmp_dir,
        "imgformat": "png",
        "scale": 0.1,
        "zstart": 1020,
        "zend": 1020,
        "uuid_length": uuid_len,
        "uuid_prefix": True
    }

    outjson = 'test_montage_scape_output_uuid.json'
    mod = MakeMontageScapeSectionStack(
        input_data=params, args=['--output_json', outjson])
    mod.run()

    base_tid = renderapi.tilespec.get_tile_specs_from_z(
        montage_stack, 1020, render=render)[0].tileId

    tspecs = render.run(
        renderapi.tilespec.get_tile_specs_from_stack, output_stack)
    assert len(tspecs) == 1
    restring = "^ds[0-9a-fA-F]{5}_" + base_tid + "$"
    assert re.match(restring, tspecs[0].tileId)


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


@pytest.fixture(scope='module')
def multiple_transform_raw_stack(render):
    """stack of single-capture tiles corresponding to a subset of the
    area in the downsampled rough alignment stack
    """
    with open(NONLINEAR_ROUGH_RAW_RESOLVEDTILES_JSON, 'r') as f:
        rt = renderapi.resolvedtiles.ResolvedTiles(json=json.load(f))

    stackname = "test_ra_nonaffine_raw"

    renderapi.stack.create_stack(stackname, render=render)

    renderapi.client.import_tilespecs_parallel(
        stackname, rt.tilespecs, poolsize=pool_size,
        sharedTransforms=rt.transforms, render=render)

    yield stackname

    renderapi.stack.delete_stack(stackname, render=render)


@pytest.fixture(scope='module')
def multiple_transform_ds_ra_stack(render):
    """stack of downsampled flattened montage tilespecs
    (as used in rough alignment) with multiple (and non-affine) transforms
    """
    with open(NONLINEAR_ROUGH_DS_RESOLVEDTILES_JSON, 'r') as f:
        rt = renderapi.resolvedtiles.ResolvedTiles(json=json.load(f))

    stackname = "test_ra_nonaffine_ds_aligned"

    renderapi.stack.create_stack(stackname, render=render)

    renderapi.client.import_tilespecs_parallel(
        stackname, rt.tilespecs, poolsize=pool_size,
        sharedTransforms=rt.transforms, render=render)

    yield stackname

    renderapi.stack.delete_stack(stackname, render=render)


def get_resolved_tiles_from_stack_render(stack, render):
    # TODO implement get_resolved_tiles_from_stack in render-python
    rts = [renderapi.resolvedtiles.get_resolved_tiles_from_z(
               stack, z, render=render)
           for z in renderapi.stack.get_z_values_for_stack(
               stack, render=render)]

    return renderapi.resolvedtiles.ResolvedTiles(
        tilespecs=[tspec for tspecs in (rt.tilespecs for rt in rts)
                   for tspec in tspecs],
        transformList=list({tform.transformId: tform
                            for tforms in (rt.transforms for rt in rts)
                            for tform in tforms}.values()))


@pytest.fixture(scope='module')
def multiple_transform_ds_prealign_stack(
        multiple_transform_ds_ra_stack, render):

    stackname = "test_ra_nonaffine_ds_prealign"

    rt = get_resolved_tiles_from_stack_render(
        multiple_transform_ds_ra_stack, render)

    for ts in rt.tilespecs:
        # apply_scale is not supported for nonlinear transforms (thankfully)
        ts.tforms = [renderapi.transform.AffineModel(
            M00=(1.), M11=(1.))]

    renderapi.stack.create_stack(stackname, render=render)

    renderapi.client.import_tilespecs_parallel(
        stackname, rt.tilespecs, poolsize=pool_size,
        sharedTransforms=rt.transforms, render=render)

    yield stackname

    renderapi.stack.delete_stack(stackname, render=render)


@pytest.fixture(scope='module')
def multiple_transform_aligned_stack(render):
    """output stack"""
    stackname = "test_ra_nonaffine_alignedoutput"

    yield stackname

    renderapi.stack.delete_stack(stackname, render=render)


def test_multiple_transform_apply_rough(
        render, multiple_transform_ds_ra_stack, multiple_transform_raw_stack,
        multiple_transform_aligned_stack, multiple_transform_ds_prealign_stack,
        tmpdir_factory, num_sampletspecs=15,
        ds_scale=NONLINEAR_ROUGH_DS_SCALE):
    # do apply rough

    # TODO current z value mapping is hardcoded -- could probably alter input
    input_d = {
        'render': render.make_kwargs(),
        'prealigned_stack': multiple_transform_raw_stack,
        'lowres_stack': multiple_transform_ds_ra_stack,
        'output_stack': multiple_transform_aligned_stack,
        'tilespec_directory': str(tmpdir_factory.mktemp('scratch')),
        "map_z": True,
        "old_z": [150650, 134011, 124024, 143059],
        "new_z": [25378, 18512, 13425, 22543],
        "apply_scale": False,
        "montage_stack": multiple_transform_raw_stack,
        'scale': ds_scale,
        'pool_size': pool_size,
        'output_json': str(tmpdir_factory.mktemp('output').join(
            'output.json')),
        'loglevel': 'DEBUG'
    }

    mod = ApplyRoughAlignmentTransform(input_data=input_d, args=[])
    mod.run()

    for oldz, newz in zip(input_d['old_z'], input_d['new_z']):

        # get local points for comparison (via local-to-world)
        # in this case, center of tiles
        raw_rt = renderapi.resolvedtiles.get_resolved_tiles_from_z(
            multiple_transform_raw_stack, oldz, render=render)

        l2w_pts_raw = [
            {'tileId': ts.tileId, 'visible': False,
             'local': [ts.width // 2, ts.height // 2]}
            for ts in random.sample(raw_rt.tilespecs, num_sampletspecs)]

        raw_wpts = renderapi.coordinate.local_to_world_coordinates_batch(
            multiple_transform_raw_stack, l2w_pts_raw, oldz, render=render)

        # scale these source point in a world space (to represent downsample)
        # prealigned points are defined by section bounds, so shift.

        zbounds = renderapi.stack.get_bounds_from_z(
            multiple_transform_raw_stack, oldz, render=render)

        offset = zbounds['minX'], zbounds['minY']

        scaled_prealigned_wpts = [
            dict(ptd, **{
                "world": [
                    (ptd['world'][0] - offset[0]) * ds_scale,
                    (ptd['world'][1] - offset[1]) * ds_scale,
                    ptd['world'][2]]})
            for ptd in raw_wpts]

        # get in local downsample space
        ds_lpts = [i for l in  # noqa: E741
                   renderapi.coordinate.world_to_local_coordinates_batch(
                       multiple_transform_ds_prealign_stack,
                       scaled_prealigned_wpts, newz,
                       render=render) for i in l]  # why, render, why?

        # get transformed points in downsampled space, then scale
        aligned_ds_wpts = (
            renderapi.coordinate.local_to_world_coordinates_batch(
                multiple_transform_ds_ra_stack, ds_lpts, newz, render=render))

        aligned_wpts = [
            dict(ptd, **{
                "world": [
                    ptd['world'][0] / ds_scale,
                    ptd['world'][1] / ds_scale,
                    ptd['world'][2]
                ]})
            for ptd in aligned_ds_wpts]

        # get transformed points in applied  tile space

        aligned_lpts = [
            i for l in  # noqa: E741
            renderapi.coordinate.world_to_local_coordinates_batch(
                multiple_transform_aligned_stack, aligned_wpts,
                newz, render=render) for i in l]

        assert len(l2w_pts_raw) == len(aligned_lpts)

        raw_tId_to_lpts = {lpt['tileId']: lpt for lpt in l2w_pts_raw}
        aligned_tId_to_lpts = {lpt['tileId']: lpt for lpt in aligned_lpts}

        assert not (six.viewkeys(raw_tId_to_lpts) ^
                    six.viewkeys(aligned_tId_to_lpts))

        # compare
        for tId, r_lpt in raw_tId_to_lpts.items():
            a_lpt = aligned_tId_to_lpts[tId]
            assert np.linalg.norm(
                np.array(a_lpt['local'][:2]) -
                np.array(r_lpt['local'][:2])) < 1
