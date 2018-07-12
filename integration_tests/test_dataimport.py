import json
import urllib
import urlparse
import tempfile
import logging
import pytest
import renderapi
import marshmallow as mm
from rendermodules.utilities.pillow_utils import Image
from rendermodules.module.render_module import RenderModuleException
from rendermodules.dataimport import generate_EM_tilespecs_from_metafile
from rendermodules.dataimport import generate_mipmaps
from rendermodules.dataimport import apply_mipmaps_to_render
from test_data import (render_params,
                       METADATA_FILE, MIPMAP_TILESPECS_JSON,
                       MIPMAP_TRANSFORMS_JSON, scratch_dir)
import os
import copy



@pytest.fixture(scope='module')
def render():
    return renderapi.connect(**render_params)

def test_generate_EM_metadata(render):
    assert isinstance(render, renderapi.render.RenderClient)
    with open(METADATA_FILE, 'r') as f:
        md = json.load(f)
    ex = copy.copy(generate_EM_tilespecs_from_metafile.example_input)
    ex['render'] = render.make_kwargs()
    ex['metafile'] = METADATA_FILE
    with tempfile.NamedTemporaryFile(suffix='.json') as probablyemptyfn:
        outfile = probablyemptyfn.name
    mod = generate_EM_tilespecs_from_metafile.GenerateEMTileSpecsModule(
        input_data=ex, args=['--output_json', outfile])
    mod.run()

    with open(outfile, 'r') as f:
        outjson = json.load(f)

    assert outjson['stack'] == ex['stack']

    expected_tileIds = {mod.tileId_from_basename(img['img_path'])
                        for img in md[1]['data']}
    delivered_tileIds = set(renderapi.stack.get_stack_tileIds(
        ex['stack'], render=render))

    renderapi.stack.delete_stack(ex['stack'], render=render)
    assert len(expected_tileIds.symmetric_difference(delivered_tileIds)) == 0

def validate_mipmap_generated(in_ts,out_ts,levels,imgformat='tif'):
    # make sure that the corresponding tiles' l0s match
    inpath = generate_mipmaps.get_filepath_from_tilespec(in_ts)
    outpath = generate_mipmaps.get_filepath_from_tilespec(out_ts)

    assert inpath==outpath

    # make sure all levels have been assigned
    assert sorted(out_ts.ip.levels) == range(levels + 1)

    # make sure all assigned levels exist and are appropriately sized
    assert in_ts.width == out_ts.width
    assert in_ts.height == out_ts.height
    expected_width = out_ts.width
    expected_height = out_ts.height

    for lvl, mmL in out_ts.ip.iteritems():
        fn = urllib.unquote(urlparse.urlparse(mmL.imageUrl).path)
        ext=os.path.splitext(fn)[1]
        if (lvl != 0):
            assert ext[1:] == imgformat
        with Image.open(fn) as im:
            w, h = im.size
        assert w == expected_width // (2 ** lvl)
        assert h == expected_height // (2 ** lvl)


def outfile_test_and_remove(f, output_fn):
    assert not os.path.isfile(output_fn)
    val = f()
    assert os.path.isfile(output_fn)
    os.remove(output_fn)
    assert not os.path.isfile(output_fn)
    return val

def apply_generated_mipmaps(r, output_stack, generate_params,z=None):
    ex = copy.copy(apply_mipmaps_to_render.example)
    ex['render'] = r.make_kwargs()
    ex['input_stack'] = generate_params['input_stack']
    ex['output_stack'] = output_stack
    ex['mipmap_dir'] = generate_params['output_dir']
    ex['overwrite_zlayer'] = True
    zvalues = renderapi.stack.get_z_values_for_stack(ex['input_stack'],render=r)
    if z is not None:
        ex['z']=z
        ex.pop('zstart',None)
        ex.pop('zend',None)
        zapplied = [z]
    else:
        ex['zstart'] = generate_params['zstart']
        ex['zend'] = generate_params['zend']
        zapplied = [z for z in zvalues if z>=ex['zstart'] and z<=ex['zend']]

    outfn = 'TEST_applymipmapsoutput.json'
    mod = apply_mipmaps_to_render.AddMipMapsToStack(
        input_data=ex, args=['--output_json', outfn])
    mod.logger.setLevel(logging.DEBUG)

    outfile_test_and_remove(mod.run, outfn)

    for zout in zapplied:
        in_resolvedtiles = renderapi.resolvedtiles.get_resolved_tiles_from_z(
            ex['input_stack'], zout, render=r)
        in_tileIdtotspecs = {
            ts.tileId: ts for ts
            in in_resolvedtiles.tilespecs}

        out_resolvedtiles = renderapi.resolvedtiles.get_resolved_tiles_from_z(
            ex['output_stack'], zout, render=r)
        out_tileIdtotspecs = {
            ts.tileId: ts for ts
            in out_resolvedtiles.tilespecs}

        # make sure all tileIds match
        assert not (in_tileIdtotspecs.viewkeys() ^ out_tileIdtotspecs.viewkeys())
        for tId, out_ts in out_tileIdtotspecs.iteritems():
            in_ts = in_tileIdtotspecs[tId]
            validate_mipmap_generated(in_ts,out_ts,ex['levels'])
            # make sure reference transforms are intact
            assert isinstance(in_ts.tforms[0],
                              renderapi.transform.ReferenceTransform)
            assert in_ts.tforms[0].to_dict() == out_ts.tforms[0].to_dict()
        assert in_resolvedtiles.transforms
        assert in_resolvedtiles.transforms == out_resolvedtiles.transforms


@pytest.fixture(scope='module')
def resolvedtiles_to_mipmap():
    tilespecs = [renderapi.tilespec.TileSpec(json=d)
                 for d in MIPMAP_TILESPECS_JSON]
    tforms = [renderapi.transform.load_transform_json(tform_d)
              for tform_d in MIPMAP_TRANSFORMS_JSON]
    return renderapi.resolvedtiles.ResolvedTiles(
        tilespecs, tforms)


@pytest.fixture(scope='module')
def input_stack(render, resolvedtiles_to_mipmap):
    # TODO should maybe make this  fixture to separate tests
    test_input_stack='MIPMAPTEST'

    renderapi.stack.create_stack(test_input_stack, render=render)
    tspecs = resolvedtiles_to_mipmap.tilespecs
    tforms = resolvedtiles_to_mipmap.transforms
    renderapi.client.import_tilespecs_parallel(
        test_input_stack, tspecs, sharedTransforms=tforms, render=render)

    # assure stack is built correctly
    assert len({tspec.tileId for tspec
                in tspecs}.symmetric_difference(set(
                    renderapi.stack.get_stack_tileIds(
                        test_input_stack, render=render)))) == 0
    yield test_input_stack
    renderapi.stack.delete_stack(test_input_stack, render=render)

"""
def addMipMapsToRender_test(render,generate_params):
    input_stack = generate_params['input_stack']
    imgformat=generate_params['imgformat']
    levels=generate_params['levels']
    zvalues = renderapi.stack.get_z_values_for_stack(input_stack,render=render)
    z = zvalues[0]

    out_tilespecs=apply_mipmaps_to_render.addMipMapsToRender(render,
                                                        input_stack,
                                                        generate_params['output_dir'],
                                                        imgformat,
                                                        levels,
                                                        z)
    in_tileIdtotspecs = {
        ts.tileId: ts for ts
        in renderapi.tilespec.get_tile_specs_from_z(
            input_stack,z, render=render)}

    out_tileIdtotspecs = {
        ts.tileId: ts for ts
        in out_tilespecs}

    for tId, out_ts in out_tileIdtotspecs.iteritems():
        in_ts = in_tileIdtotspecs[tId]
        validate_mipmap_generated(in_ts,out_ts,levels,imgformat)
"""


@pytest.mark.parametrize("method", ["PIL", "block_reduce"])
def test_mipmaps(render, input_stack, resolvedtiles_to_mipmap, method, tmpdir,
                 output_stack=None):
    assert isinstance(render, renderapi.render.RenderClient)
    output_stack = ('{}_{}_OUT'.format(input_stack, method) if output_stack
                    is None else output_stack)

    tspecs = resolvedtiles_to_mipmap.tilespecs
    ex = copy.copy(generate_mipmaps.example)
    ex['render'] = render.make_kwargs()
    ex['input_stack'] = input_stack
    ex['zstart'] = min([ts.z for ts in tspecs])
    ex['zend'] = max([ts.z for ts in tspecs])
    ex['output_dir'] = str(tmpdir)
    ex['method'] = method

    outfn = 'TEST_genmipmaps.json'
    mod = generate_mipmaps.GenerateMipMaps(
        input_data=ex, args=['--output_json', outfn])

    outfile_test_and_remove(mod.run, outfn)

    apply_generated_mipmaps(render, output_stack, ex)

    renderapi.stack.delete_stack(output_stack, render=render)
    # addMipMapsToRender_test(render, ex)


def test_make_mipmaps_single_z(render, input_stack, resolvedtiles_to_mipmap,
                               tmpdir, output_stack=None):
    assert isinstance(render, renderapi.render.RenderClient)
    output_stack = ('{}OUTSINGLEZ'.format(input_stack) if output_stack
                    is None else output_stack)

    ex = copy.copy(generate_mipmaps.example)
    ex['render'] = render.make_kwargs()
    ex['input_stack'] = input_stack
    ex['z'] = min([ts.z for ts in resolvedtiles_to_mipmap.tilespecs])
    ex.pop('zstart', None)
    ex.pop('zend', None)
    ex['output_dir'] = scratch_dir

    outfn = str(tmpdir.join('TESTSINGLE_genmipmaps.json'))
    mod = generate_mipmaps.GenerateMipMaps(
        input_data=ex, args=['--output_json', outfn])

    outfile_test_and_remove(mod.run, outfn)
    apply_generated_mipmaps(render, output_stack, ex, z=ex['z'])
    renderapi.stack.delete_stack(output_stack, render=render)

    ex['z']=ex['z']-1
    with pytest.raises(RenderModuleException):
        outfn = str(tmpdir.join('TESTSINGLE_genmipmaps_fail.json'))
        mod = generate_mipmaps.GenerateMipMaps(
            input_data=ex, args=['--output_json', outfn])
        mod.run()

def test_make_mipmaps_fail_no_z(render,input_stack,tmpdir):
    ex = copy.copy(generate_mipmaps.example)
    ex['render'] = render.make_kwargs()
    ex['input_stack'] = input_stack
    ex['output_dir'] = scratch_dir
    ex.pop('zstart',None)
    ex.pop('zend',None)
    ex.pop('z',None)
    outfn = str(tmpdir.join('TESTFAIL_genmipmaps.json'))
    with pytest.raises(mm.ValidationError):
        mod = generate_mipmaps.GenerateMipMaps(
        input_data=ex, args=['--output_json', outfn])


def test_create_mipmap_from_tuple(resolvedtiles_to_mipmap, tmpdir):
    ts = resolvedtiles_to_mipmap.tilespecs[0]
    filename=generate_mipmaps.get_filepath_from_tilespec(ts)
    mytuple = (filename,str(tmpdir))
    generate_mipmaps.create_mipmap_from_tuple(mytuple)
