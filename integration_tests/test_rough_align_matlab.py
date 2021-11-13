import os
import pytest
import renderapi
import glob
import copy
import marshmallow as mm

from test_data import (
        ROUGH_MONTAGE_TILESPECS_JSON,
        ROUGH_MONTAGE_TRANSFORM_JSON,
        ROUGH_POINT_MATCH_COLLECTION,
        ROUGH_DS_TEST_TILESPECS_JSON,
        ROUGH_MAPPED_PT_MATCH_COLLECTION,
        render_params,
        test_rough_parameters as solver_example,
        apply_rough_alignment_example as ex1,
        pool_size,
        test_legacy_rough)
from rendermodules.module.render_module import RenderModuleException
from rendermodules.materialize.render_downsample_sections import (
    RenderSectionAtScale)
from rendermodules.dataimport.make_montage_scapes_stack import (
    MakeMontageScapeSectionStack)
from rendermodules.deprecated.rough_align.do_rough_alignment import (
    SolveRoughAlignmentModule)
from rendermodules.rough_align.apply_rough_alignment_to_montages import (
    ApplyRoughAlignmentTransform)

# skip these tests if not explicitly asked for
pytestmark = pytest.mark.skipif(not test_legacy_rough, reason=(
    "legacy code not being tested -- to test, "
    "set environment variable RENDERMODULES_TEST_LEGACY_ROUGH"))


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
        "zend": 1022
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
        "zend": 1022
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
        "new_z_start": 251
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
        "new_z_start": 253
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
        "close_stack": True
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
    render.run(
        renderapi.pointmatch.delete_collection, pt_match_collection)


@pytest.fixture(scope='module')
def test_do_rough_alignment(
        render, montage_scape_stack, rough_point_match_collection,
        tmpdir_factory, output_lowres_stack=None):
    if output_lowres_stack is None:
        output_lowres_stack = '{}_DS_Rough'.format(montage_scape_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_ex = copy.deepcopy(solver_example)
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

    mod = SolveRoughAlignmentModule(input_data=solver_ex, args=[])
    mod.run()

    zvalues = render.run(
        renderapi.stack.get_z_values_for_stack, output_lowres_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))

    yield output_lowres_stack
    renderapi.stack.delete_stack(output_lowres_stack, render=render)


@pytest.fixture(scope="module")
def test_do_mapped_rough_alignment(
        render, montage_z_mapped_stack, rough_mapped_pt_match_collection,
        tmpdir_factory, output_lowres_stack=None):
    if output_lowres_stack is None:
        output_lowres_stack = '{}_DS_Rough'.format(montage_z_mapped_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_ex = copy.deepcopy(solver_example)
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
        renderapi.stack.get_z_values_for_stack, output_lowres_stack)
    zs = [251, 252, 253]
    assert(set(zvalues) == set(zs))

    yield output_lowres_stack
    renderapi.stack.delete_stack(output_lowres_stack, render=render)


@pytest.fixture(scope='module')
def test_do_rough_alignment_with_scale(
        render, montage_scape_stack_with_scale, rough_point_match_collection,
        tmpdir_factory, output_lowres_stack=None):
    if output_lowres_stack is None:
        output_lowres_stack = '{}_DS_Rough_scale'.format(
            montage_scape_stack_with_scale)

    output_directory = str(tmpdir_factory.mktemp('output_json'))
    solver_ex = copy.deepcopy(solver_example)
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
        renderapi.stack.get_z_values_for_stack, output_lowres_stack)
    zs = [1020, 1021, 1022]
    assert(set(zvalues) == set(zs))

    yield output_lowres_stack
    renderapi.stack.delete_stack(output_lowres_stack, render=render)


def test_mapped_apply_rough_alignment_transform(
        render, montage_stack, test_do_mapped_rough_alignment,
        tmpdir_factory, prealigned_stack=None, output_stack=None):
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


def test_apply_rough_alignment_transform(
        render, montage_stack, test_do_rough_alignment,
        tmpdir_factory, prealigned_stack=None, output_stack=None):

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


def test_apply_rough_alignment_transform_with_scale(
        render, montage_stack, test_do_rough_alignment_with_scale,
        tmpdir_factory, prealigned_stack=None, output_stack=None):
    ex = copy.deepcopy(ex1)
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


def test_solver_default_options(
        render, montage_scape_stack, rough_point_match_collection,
        tmpdir_factory):
    output_lowres_stack = '{}_DS_Rough'.format(montage_scape_stack)

    output_directory = str(tmpdir_factory.mktemp('output_json'))

    solver_ex1 = copy.deepcopy(solver_example)
    solver_ex1 = dict(solver_ex1, **{
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
