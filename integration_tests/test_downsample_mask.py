import os
import renderapi
import json
from test_data import (
        TEST_DATA_ROOT,
        render_params)

from rendermodules.rough_align.downsample_mask_handler import (
        DownsampleMaskHandler, points_in_mask, polygon_list_from_mask)
from rendermodules.module.render_module import \
        RenderModuleException
import pytest
import numpy as np
import itertools

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
    for group1, group2 in itertools.combinations(groups, 2):
        matches += renderapi.pointmatch.get_matches_from_group_to_group(
                collection, group1, group2, render=render)
    ids = []
    for m in matches:
        if np.any(np.isclose(np.array(m['matches']['w']), 0.0)):
            ids.append([m['pGroupId'], m['qGroupId']])
    return ids


def test_mask_polygons():
    mask1 = np.zeros((100, 100)).astype('uint8')
    mask2 = np.zeros((100, 100)).astype('uint8')
    mask1[40:60, 40:60] = 255
    mask2[0:10, 20:50] = 255
    polys = polygon_list_from_mask(mask1 + mask2)
    assert len(polys) == 2

    # flip the axes order to be (col, row), i.e. (x, y)
    m1mnmx = np.hstack((
        np.argwhere(mask1 == 255).min(axis=0)[::-1],
        np.argwhere(mask1 == 255).max(axis=0)[::-1]))
    m2mnmx = np.hstack((
        np.argwhere(mask2 == 255).min(axis=0)[::-1],
        np.argwhere(mask2 == 255).max(axis=0)[::-1]))

    def check_matching(polys, m1mnmx, m2mnnx):
        # check that the polygons match up 1-to-1 with the input
        match = [-1] * len(polys)
        for i in range(len(polys)):
            pmnmx = np.hstack((
                np.array(polys[i].boundary.xy).min(axis=1).astype('int'),
                np.array(polys[i].boundary.xy).max(axis=1).astype('int')))
            if np.all(np.isclose(pmnmx, m1mnmx)):
                match[i] = 1
            if np.all(np.isclose(pmnmx, m2mnmx)):
                match[i] = 2
        assert (match == [1, 2]) | (match == [2, 1])

    check_matching(polys, m1mnmx, m2mnmx)

    # give a transform
    B0 = 10
    B1 = -20
    tf = renderapi.transform.AffineModel(
            B0=B0,
            B1=B1)
    polys = polygon_list_from_mask(mask1 + mask2, transforms=[tf])
    m1mnmx[[0, 2]] += B0
    m1mnmx[[1, 3]] += B1
    m2mnmx[[0, 2]] += B0
    m2mnmx[[1, 3]] += B1
    check_matching(polys, m1mnmx, m2mnmx)


def test_points_in_mask():
    mask = np.zeros((1000, 1000)).astype('uint8')
    # render masks areas where mask = 0
    mask[0:500, :] = 255

    # all should be weight=1 (included)
    w1pts = np.random.rand(2, 100)
    w1pts[0, :] *= 999
    w1pts[1, :] *= 499
    w1 = points_in_mask(mask, w1pts.tolist())
    assert np.all(np.isclose(w1, 1.0))

    # all should be weight=0 (excluded)
    w0pts = np.random.rand(2, 100)
    w0pts[0, :] *= 999
    w0pts[1, :] *= 499
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
