import os
import renderapi
import json
from test_data import (
        TEST_DATA_ROOT,
        render_params)

from rendermodules.rough_align.downsample_mask_handler import (
        DownsampleMaskHandler, points_in_mask)
from rendermodules.module.render_module import \
        RenderModuleException
import pytest
import numpy as np

DS_MASK_TEST_PATH = os.path.join(
        TEST_DATA_ROOT,
        "em_modules_test_data",
        "downsample_masking")
DS_MASK_PATH = os.path.join(
        DS_MASK_TEST_PATH,
        "masks")
DS_BAD_MASK_PATH = os.path.join(
        DS_MASK_TEST_PATH,
        "bad_masks")
DS_TSPEC_PATH = os.path.join(
        DS_MASK_TEST_PATH,
        "ds_tilespecs.json")
DS_COLLECTION_PATH = os.path.join(
        DS_MASK_TEST_PATH,
        "ds_matches.json")


@pytest.fixture(scope='module')
def render():
    render_params['project'] = 'downsample_mask_test'
    render = renderapi.connect(**render_params)
    return render


@pytest.fixture(scope='module')
def downsampled_stack(render):
    with open(DS_TSPEC_PATH, 'r') as f:
        tspecs = [
            renderapi.tilespec.TileSpec(json=i)
            for i in json.load(f)]

    stack = "downsampled_stack_for_masks"
    renderapi.stack.create_stack(stack, render=render)
    renderapi.client.import_tilespecs(stack,
                                      tspecs,
                                      render=render)
    renderapi.stack.set_stack_state(stack,
                                    'COMPLETE',
                                    render=render)
    yield stack


@pytest.fixture(scope='module')
def downsampled_collection(render):
    collection = "downsampled_collection_for_masks"
    with open(DS_COLLECTION_PATH, 'r') as f:
        renderapi.pointmatch.import_matches(
                collection,
                json.load(f),
                render=render)
    yield collection


def zs_have_masks(render, stack):
    tspecs = renderapi.tilespec.get_tile_specs_from_stack(
            stack,
            render=render)
    zs = [{'z': t.z, 'group': t.layout.sectionId}
          for t in tspecs if t.ip[0].maskUrl is not None]
    return zs


def matches_are_filtered(render, collection):
    groups = renderapi.pointmatch.get_match_groupIds(
            collection,
            render=render)
    matches = []
    for i in range(len(groups)):
        for j in range(i):
            matches += renderapi.pointmatch.get_matches_from_group_to_group(
                    collection, groups[i], groups[j], render=render)
    ids = []
    for m in matches:
        if np.count_nonzero(
                np.isclose(
                    np.array(m['matches']['w']),
                    0.0)) != 0:
            ids.append([m['pGroupId'], m['qGroupId']])
    return ids


def test_points_in_mask():
    mask = np.zeros((1000, 1000)).astype('uint8')
    # render masks areas where mask = 0
    mask[0:500, :] = 255

    # all should be weight=1 (included)
    w1pts = np.random.rand(2, 100)
    w1pts[0, :] *= 1000
    w1pts[1, :] *= 500
    w1 = points_in_mask(mask, w1pts.tolist())
    assert np.all(np.isclose(w1, 1.0))

    # all should be weight=0 (excluded)
    w0pts = np.random.rand(2, 100)
    w0pts[0, :] *= 1000
    w0pts[1, :] *= 500
    w0pts[1, :] += 500
    w0 = points_in_mask(mask, w0pts.tolist())
    assert np.all(np.isclose(w0, 0.0))


def test_masks(render, downsampled_stack, downsampled_collection):
    # check that the starting point has no masks and nothing filtered
    assert len(zs_have_masks(render, downsampled_stack)) == 0
    assert len(matches_are_filtered(render, downsampled_collection)) == 0

    render_params['project'] = 'downsample_mask_test'
    input_args = {
            "render": render_params,
            "mask_dir": DS_MASK_PATH,
            "stack": downsampled_stack,
            "collection": downsampled_collection,
            "zMask": [10395, 10398],
            "zReset": None,
            "log_level": "WARNING"
            }

    dsmod = DownsampleMaskHandler(input_data=input_args, args=[])
    dsmod.run()

    # check that the stack now has masks where we asked
    # and that the collection is filtered
    zhm = zs_have_masks(render, downsampled_stack)
    assert [iz['z'] for iz in zhm] == input_args['zMask']
    for ids in matches_are_filtered(render, downsampled_collection):
        assert np.any([iz['group'] in ids for iz in zhm])

    # reset those masks
    input_args['zReset'] = list(input_args['zMask'])
    input_args['zMask'] = None
    dsmod = DownsampleMaskHandler(input_data=input_args, args=[])
    dsmod.run()
    assert len(zs_have_masks(render, downsampled_stack)) == 0
    assert len(matches_are_filtered(render, downsampled_collection)) == 0
    # run it again (it was already reset)
    with pytest.raises(RenderModuleException):
        dsmod.run()
    assert len(zs_have_masks(render, downsampled_stack)) == 0
    assert len(matches_are_filtered(render, downsampled_collection)) == 0

    # ask for a z value outside of the stack z range
    input_args['zMask'] = [10392, 10395]
    input_args['zReset'] = None
    dsmod = DownsampleMaskHandler(input_data=input_args, args=[])
    dsmod.run()
    zhm = zs_have_masks(render, downsampled_stack)
    assert [iz['z'] for iz in zhm] == [10395]
    for ids in matches_are_filtered(render, downsampled_collection):
        assert np.any([iz['group'] in ids for iz in zhm])
    # run it again (there's already a mask)
    with pytest.raises(RenderModuleException):
        dsmod.run()
    zhm = zs_have_masks(render, downsampled_stack)
    assert [iz['z'] for iz in zhm] == [10395]
    for ids in matches_are_filtered(render, downsampled_collection):
        assert np.any([iz['group'] in ids for iz in zhm])

    # reset those masks
    input_args['zMask'] = None
    input_args['zReset'] = [10395]
    dsmod = DownsampleMaskHandler(input_data=input_args, args=[])
    dsmod.run()
    assert len(zs_have_masks(render, downsampled_stack)) == 0
    assert len(matches_are_filtered(render, downsampled_collection)) == 0

    # 2 mask filenames match
    input_args['zMask'] = [10395, 10398]
    input_args['zReset'] = None
    input_args['mask_dir'] = DS_BAD_MASK_PATH
    dsmod = DownsampleMaskHandler(input_data=input_args, args=[])
    with pytest.raises(RenderModuleException):
        dsmod.run()
    assert len(zs_have_masks(render, downsampled_stack)) == 0
    assert len(matches_are_filtered(render, downsampled_collection)) == 0

    # make a z that has multiple tile specs
    tspecs = [
            renderapi.tilespec.get_tile_specs_from_z(
                downsampled_stack,
                z,
                render=render)[0]
            for z in [10395, 10396]]
    for t in tspecs:
        t.tileId = '%d_%s_junk' % (t.z, t.layout.sectionId)
        t.z = 10392
    renderapi.client.import_tilespecs(downsampled_stack, tspecs, render=render)
    input_args['zMask'] = [10392]
    input_args['mask_dir'] = DS_BAD_MASK_PATH
    input_args['zReset'] = None
    dsmod = DownsampleMaskHandler(input_data=input_args, args=[])
    with pytest.raises(RenderModuleException):
        dsmod.run()
    renderapi.stack.delete_section(downsampled_stack, 10392, render=render)
    assert len(zs_have_masks(render, downsampled_stack)) == 0
    assert len(matches_are_filtered(render, downsampled_collection)) == 0

    # remove a mask that isn't there
    input_args['zMask'] = None
    input_args['zReset'] = [10392]
    input_args['mask_dir'] = DS_MASK_PATH
    dsmod = DownsampleMaskHandler(input_data=input_args, args=[])
    dsmod.run()
    assert len(zs_have_masks(render, downsampled_stack)) == 0
