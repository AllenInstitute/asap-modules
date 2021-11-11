#!/usr/bin/env python
'''
'''
import os
import imghdr
import copy

import pytest


import renderapi
from asap.utilities.pillow_utils import Image
from asap.materialize import materialize_sections
from test_data import (render_params,
                       MATERIALIZE_BOX_JSON)


@pytest.fixture(scope='module')
def render():
    return renderapi.connect(**render_params)


@pytest.fixture(scope='module')
def tspecs_to_materialize():
    tilespecs = [renderapi.tilespec.TileSpec(json=d)
                 for d in MATERIALIZE_BOX_JSON]
    return tilespecs


@pytest.fixture(scope='module')
def input_materializeboxes_stack(render, tspecs_to_materialize):
    test_stack = 'materialize_boxes_test'
    renderapi.stack.create_stack(test_stack, render=render)
    renderapi.client.import_tilespecs_parallel(
        test_stack, tspecs_to_materialize, render=render)

    # assure stack is built correctly
    assert len({tspec.tileId for tspec
                in tspecs_to_materialize}.symmetric_difference(set(
                    renderapi.stack.get_stack_tileIds(
                        test_stack, render=render)))) == 0
    yield test_stack
    renderapi.stack.delete_stack(test_stack, render=render)


format_ext_mapping = {
    'PNG': 'png',
    'TIF': 'tif',
    'JPEG': 'jpg'}


def test_materialize_boxes(render, input_materializeboxes_stack, tmpdir):
    # TODO model this after pm test w/ spark

    zs_totest = renderapi.stack.get_z_values_for_stack(
        input_materializeboxes_stack, render=render)

    input_params = dict(copy.copy(materialize_sections.example_input), **{
        'stack': input_materializeboxes_stack,
        'render': {
            'owner': render_params['owner'],
            'project': render_params['project'],
            'host': render_params['host'],
            'port': render_params['port']},
        'zValues': zs_totest,
        'rootDirectory': str(tmpdir)})

    _ = input_params.pop('baseDataUrl', None)
    _ = input_params.pop('owner', None)
    _ = input_params.pop('project', None)

    mod = materialize_sections.MaterializeSectionsModule(
        input_data=input_params, args=[
            '--output_json', 'MaterializeSections_test.json'])
    mod.run()

    # gather components of basedir
    root_dir = mod.args['rootDirectory']
    assert os.path.isdir(root_dir)

    stack = mod.args['stack']
    h = mod.args['height']
    w = mod.args['width']
    project = mod.args['project']
    maxLevel = mod.args['maxLevel']
    fmt = mod.args.get('fmt', 'PNG')
    zs = mod.args['zValues']

    # TODO is bottom dir hxw or wxh
    basedir = os.path.join(
        root_dir, project, stack, '{}x{}'.format(w, h))
    assert os.path.isdir(basedir)

    test_image = True
    for z in zs:
        bounds = renderapi.stack.get_bounds_from_z(stack, z, render=render)
        assert bounds['maxX'] > 0
        assert bounds['maxY'] > 0

        expected_colmin = max(0, bounds['minX'] // w)
        expected_colmax = bounds['maxX'] // w

        expected_rowmin = max(0, bounds['minY'] // h)
        expected_rowmax = bounds['maxY'] // h

        for lvl in range(maxLevel + 1):
            zdir = os.path.join(basedir, str(lvl), str(z))
            assert os.path.isdir(zdir)
            # TODO
            # make sure directories line up with corners of section bounds
            rowdirs = {os.path.join(d, '') for d in os.listdir(zdir)
                       if os.path.isdir(os.path.join(zdir, d))}
            rows = [int(os.path.split(d)[0]) for d in rowdirs]

            cols = set()
            for rowdir in rowdirs:
                cols = cols.union({int(os.path.splitext(f)[0]) for f in
                                  os.listdir(os.path.join(zdir, rowdir))})
                if test_image:
                    imgfn = os.path.join(zdir, rowdir, '{}.{}'.format(
                        next(iter(cols)), format_ext_mapping[fmt]))
                    with Image.open(imgfn) as img:
                        imwidth, imheight = img.size
                    assert imwidth == w
                    assert imheight == h
                    assert imghdr.what(imgfn) == format_ext_mapping[fmt]
                    test_image = False

            if lvl == 0:
                assert min(rows) == expected_rowmin
                assert max(rows) == expected_rowmax
                assert min(cols) == expected_colmin
                assert max(cols) == expected_colmax
