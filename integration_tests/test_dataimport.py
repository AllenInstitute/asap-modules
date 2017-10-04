import json
import pytest
import urllib
import urlparse
import tempfile
import logging
from PIL import Image
import renderapi
from rendermodules.dataimport import generate_EM_tilespecs_from_metafile
from rendermodules.dataimport import generate_mipmaps
from rendermodules.dataimport import apply_mipmaps_to_render
from test_data import (render_params, 
                       METADATA_FILE, MIPMAP_TILESPECS_JSON, scratch_dir)

@pytest.fixture(scope='module')
def render():
    return renderapi.connect(**render_params)

def test_generate_EM_metadata(render):
    assert isinstance(render, renderapi.render.RenderClient)
    with open(METADATA_FILE, 'r') as f:
        md = json.load(f)
    ex = generate_EM_tilespecs_from_metafile.example_input
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

def validate_mipmap_generated(in_ts,out_ts,levels):
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

    for lvl, mmL in dict(out_ts.ip).iteritems():
        fn = urllib.unquote(urlparse.urlparse(mmL['imageUrl']).path)
        with Image.open(fn) as im:
            w, h = im.size
        assert w == expected_width // (2 ** lvl)
        assert h == expected_height // (2 ** lvl)

def apply_generated_mipmaps(r, output_stack, generate_params):
    ex = apply_mipmaps_to_render.example
    ex['render'] = r.make_kwargs()
    ex['input_stack'] = generate_params['input_stack']
    ex['output_stack'] = output_stack
    ex['mipmap_dir'] = generate_params['output_dir']
    ex['zstart'] = generate_params['zstart']
    ex['zend'] = generate_params['zend']

    in_tileIdtotspecs = {
        ts.tileId: ts for ts
        in renderapi.tilespec.get_tile_specs_from_stack(
            ex['input_stack'], render=r)}

    mod = apply_mipmaps_to_render.AddMipMapsToStack(input_data=ex, args=[])
    mod.logger.setLevel(logging.DEBUG)
    mod.run()

    out_tileIdtotspecs = {
        ts.tileId: ts for ts
        in renderapi.tilespec.get_tile_specs_from_stack(
            ex['output_stack'], render=r)}

    # make sure all tileIds match
    assert not (in_tileIdtotspecs.viewkeys() ^ out_tileIdtotspecs.viewkeys())
    for tId, out_ts in out_tileIdtotspecs.iteritems():
        in_ts = in_tileIdtotspecs[tId]
        validate_mipmap_generated(in_ts,out_ts,ex['levels'])

@pytest.fixture(scope='module')
def tspecs_to_mipmap():
    tilespecs = [renderapi.tilespec.TileSpec(json=d) 
        for d in MIPMAP_TILESPECS_JSON]
    return tilespecs

@pytest.fixture(scope='module')
def input_stack(render,tspecs_to_mipmap):
    # TODO should maybe make this  fixture to separate tests
    test_input_stack='MIPMAPTEST'

    renderapi.stack.create_stack(test_input_stack, render=render)
    renderapi.client.import_tilespecs_parallel(
        test_input_stack, tspecs_to_mipmap, render=render)

    # assure stack is built correctly
    assert len({tspec.tileId for tspec
                in tspecs_to_mipmap}.symmetric_difference(set(
                    renderapi.stack.get_stack_tileIds(
                        test_input_stack, render=render)))) == 0
    yield test_input_stack
    renderapi.stack.delete_stack(test_input_stack, render=render)

def addMipMapsToRender_test(render,output_stack,generate_params):
    tmpdir=tempfile.mkdtemp()
    input_stack = generate_params['input_stack']
    imgformat='tif'
    levels=3
    zvalues = renderapi.stack.get_z_values_for_stack(input_stack,render=render)
    z = zvalues[0]

    ts_paths=apply_mipmaps_to_render.addMipMapsToRender(render, 
                                                        input_stack,
                                                        tmpdir,
                                                        imgformat,
                                                        levels,
                                                        z)
    in_tileIdtotspecs = {
        ts.tileId: ts for ts
        in renderapi.tilespec.get_tile_specs_from_z(
            input_stack,z, render=render)}

    out_tileIdtotspecs = {
        ts.tileId: ts for ts
        in renderapi.tilespec.get_tile_specs_from_z(
            output_stack,z, render=render)}

    for tId, out_ts in out_tileIdtotspecs.iteritems():
        in_ts = in_tileIdtotspecs[tId]
        validate_mipmap_generated(in_ts,out_ts,levels)

def test_mipmaps(render, input_stack, tspecs_to_mipmap, output_stack=None):
    assert isinstance(render, renderapi.render.RenderClient)
    output_stack = ('{}OUT'.format(input_stack) if output_stack
                    is None else output_stack)

    ex = generate_mipmaps.example
    ex['render'] = render.make_kwargs()
    ex['input_stack'] = input_stack
    ex['zstart'] = min([ts.z for ts in tspecs_to_mipmap])
    ex['zend'] = max([ts.z for ts in tspecs_to_mipmap])
    ex['output_dir'] = scratch_dir

    mod = generate_mipmaps.GenerateMipMaps(input_data=ex, args=[])
    mod.run()

    apply_generated_mipmaps(render, output_stack, ex)
    addMipMapsToRender_test(render, output_stack, ex)
    renderapi.stack.delete_stack(output_stack, render=render)

def test_create_mipmap_from_tuple(tspecs_to_mipmap,tmpdir):
    ts = tspecs_to_mipmap[0]
    filename=generate_mipmaps.get_filepath_from_tilespec(ts)
    mytuple = (filename,str(tmpdir))
    generate_mipmaps.create_mipmap_from_tuple(mytuple)

