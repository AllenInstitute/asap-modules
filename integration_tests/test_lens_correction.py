import json
import pytest
import logging
import renderapi
import numpy as np
import math
from rendermodules.lens_correction.apply_lens_correction import \
        ApplyLensCorrection
from rendermodules.lens_correction.lens_correction import LensCorrectionModule
from rendermodules.mesh_lens_correction.do_mesh_lens_correction import \
        make_mask
from test_data import render_params, TILESPECS_NO_LC_JSON, TILESPECS_LC_JSON
from test_data import calc_lens_parameters
import matplotlib.pyplot as plt
from six.moves import urllib
import os


render_params['project'] = "lens_correction_test"


@pytest.fixture(scope='module')
def render():
    render = renderapi.connect(**render_params)
    return render


@pytest.fixture(scope='module')
def example_tform_dict():
    tform = {
        "type": "leaf",
        "className": "lenscorrection.NonLinearTransform",
        "dataString": (
            "5 21 1078.539787490504 5.9536401731869155 "
            "18.082459176969103 1078.355487979244 3.5307003058070348 "
            "11.64046339965791 -2.0439286697147363 -24.64074017045258 "
            "-41.26811513301735 -9.491349156078 -1.6954196055547417 "
            "-9.185363883704582 3.2959653136929163 16.063471152021727 "
            "16.294847510892705 11.433417367508135 31.814503296730077 "
            "8.568546283786144 1.1875763257283882 1.8390027135003706 "
            "4.811216491589896 -6.951845669522106 -12.267142955347461 "
            "-15.925381113080153 -14.870929614388771 -1.4936338107986824 "
            "-14.329785142195151 -10.312907851336057 -0.42262010802849903 "
            "-1.009175398784258 -3.2394612925182904 1.1172748871012366 "
            "3.675506795700918 4.147928095339033 4.180779006453825 "
            "2.3467092081149583 3.126555229782104 -0.7606672639855052 "
            "4.694244302355039 4.905604855794568 19.42462457061161 "
            "17.804784158940837 1942.4644352489915 1780.4747249033032 "
            "4947240.512601199 3472086.434895099 4297903.568850483 "
            "1.4156910200690086E10 8.869224932399399E9 8.401913335029685E9 "
            "1.184452643883111E10 4.326915271956289E13 "
            "2.5462360962795074E13 2.1493026326968934E13 "
            "2.3188186000529023E13 3.519602640946822E13 "
            "1.3795333182608984E17 7.805152532090952E16 "
            "6.180627842946396E16 5.937108087578708E16 "
            "6.8994694539978896E16 1.09803035347323568E17 100.0 "
            "1083.561059814147 1062.000092490804 4335259.912658479 "
            "3072116.6105437097 4089560.9959054096 1.588497037768282E10 "
            "1.054070313855633E10 1.0306317022320707E10 "
            "1.463025351609144E10 5.735536632714905E13 "
            "3.677632888097447E13 3.3248028854072227E13 "
            "3.53752851004701E13 5.205228949477172E13 "
            "2.06753448194955584E17 1.29851821487233248E17 "
            "1.12997804746083296E17 1.1130902498005392E17 "
            "1.23651446458254E17 1.85995206005396736E17 0.0 3840 3840 ")
    }

    return tform


@pytest.fixture(scope='module')
def stack_no_lc(render):
    stack = "test_no_lc"

    renderapi.stack.create_stack(stack, render=render)

    tspecs = [renderapi.tilespec.TileSpec(json=tspec)
              for tspec in TILESPECS_NO_LC_JSON]
    renderapi.client.import_tilespecs(stack, tspecs, render=render)
    renderapi.stack.set_stack_state(stack, 'COMPLETE', render=render)
    yield stack

    renderapi.stack.delete_stack(stack, render=render)


@pytest.fixture(scope='module')
def stack_lc(render):
    stack = "test_lc"

    renderapi.stack.create_stack(stack, render=render)

    tspecs = [renderapi.tilespec.TileSpec(json=tspec)
              for tspec in TILESPECS_LC_JSON]
    renderapi.client.import_tilespecs(stack, tspecs, render=render)
    renderapi.stack.set_stack_state(stack, 'COMPLETE', render=render)
    yield stack

    renderapi.stack.delete_stack(stack, render=render)


@pytest.fixture(scope='module')
def test_points(example_tform_dict):
    example_tform = renderapi.transform.NonLinearCoordinateTransform(
            dataString=example_tform_dict['dataString'])
    x = np.arange(0, example_tform.width, 100, dtype=np.float64)
    y = np.arange(0, example_tform.height, 100, dtype=np.float64)
    xv, yv = np.meshgrid(x, y)
    xv = xv.flatten()
    yv = yv.flatten()
    test_points = np.array([xv, yv]).T

    return test_points


def compute_lc_norm_and_max(test_example_tform, test_new_tform):
    tform_norm = (
            np.linalg.norm(test_new_tform - test_example_tform) /
            math.sqrt(test_new_tform.size))
    tform_diff = np.power(test_new_tform - test_example_tform, 2)
    tform_max_diff = max(np.power(tform_diff[:, 0] + tform_diff[:, 1], 0.5))
    print('Norm: %s Max difference: %s' % (tform_norm, tform_max_diff))
    assert tform_max_diff < 3
    assert tform_norm < 1


def test_calc_lens_correction(example_tform_dict, test_points, tmpdir):
    outfile = str(tmpdir.join('test_LC_out.json'))
    print(outfile)

    mod = LensCorrectionModule(
            input_data=calc_lens_parameters, args=['--output_json', outfile])
    mod.logger.setLevel(logging.DEBUG)
    mod.run()

    with open(calc_lens_parameters['outfile'], 'r') as fp:
        new_tform_dict = json.load(fp)

    # new_tform_path = calc_lens_parameters['outfile']
    # with open(new_tform_path, 'r') as fp:
    #     new_tform_dict = json.load(fp)

    example_tform = renderapi.transform.NonLinearCoordinateTransform(
            dataString=example_tform_dict['dataString'])
    new_tform = renderapi.transform.NonLinearCoordinateTransform(
            dataString=new_tform_dict['transform']['dataString'])

    assert np.array_equal(
            [example_tform.height, example_tform.width,
                example_tform.length, example_tform.dimension],
            [new_tform.height, new_tform.width,
                new_tform.length, new_tform.dimension])

    test_example_tform = example_tform.tform(test_points)
    test_new_tform = new_tform.tform(test_points)

    compute_lc_norm_and_max(test_example_tform, test_new_tform)


def test_apply_lens_correction(render, stack_no_lc, stack_lc,
                               example_tform_dict, test_points):
    params = {
        "render": render_params,
        "inputStack": stack_no_lc,
        "outputStack": stack_lc,
        "zs": [2266],
        "transform": example_tform_dict,
        "refId": None,
        "pool_size": 5,
        "overwrite_zlayer": True
    }

    out_fn = 'test_ALC_out.json'
    mod = ApplyLensCorrection(input_data=params,
                              args=['--output_json', out_fn])
    mod.run()

    with open(out_fn, 'r') as f:
        refId = json.load(f)['refId']

    example_tform = renderapi.transform.NonLinearCoordinateTransform(
        dataString=params['transform']['dataString'], transformId=refId)

    test_example_tform = example_tform.tform(test_points)

    for z in params['zs']:
        resolvedtiles = renderapi.resolvedtiles.get_resolved_tiles_from_z(
            params['output_stack'], z, render=render)
        tspecs = resolvedtiles.tilespecs
        tforms = resolvedtiles.transforms
        # all tiles in z should be given same ref tform
        assert all([ts.tforms[0].refId == refId for ts in tspecs])
        # should only be one ref tform
        assert len(tforms) == 1
        new_tform = tforms[0]
        print(new_tform.to_dict())
        assert new_tform.transformId == refId
        assert np.array_equal(
            [example_tform.height, example_tform.width, example_tform.length,
                example_tform.dimension],
            [new_tform.height, new_tform.width, new_tform.length,
                new_tform.dimension])
        test_new_tform = new_tform.tform(test_points)
        compute_lc_norm_and_max(test_example_tform, test_new_tform)


def test_apply_lens_correction_mask(
        render, stack_no_lc, stack_lc,
        example_tform_dict, test_points, tmpdir_factory):

    params = {
        "render": render_params,
        "inputStack": stack_no_lc,
        "outputStack": stack_lc,
        "zs": [2266],
        "transform": example_tform_dict,
        "refId": None,
        "pool_size": 5,
        "overwrite_zlayer": True
    }

    # make a mask
    tspecs = renderapi.tilespec.get_tile_specs_from_z(
            params['inputStack'],
            float(params['zs'][0]),
            render=renderapi.connect(**params['render']))
    mask_dir = str(tmpdir_factory.mktemp("make_mask"))
    dx = 100
    dy = 100
    width = int(tspecs[0].width)
    height = int(tspecs[0].height)
    mask_coords = [
            [0, dy], [dx, 0], [width, 0], [width, height],
            [0, height]]
    maskUrl = make_mask(
            mask_dir,
            width,
            height,
            mask_coords,
            mask_file=None,
            basename='mymask.png')
    params['maskUrl'] = maskUrl

    out_fn = 'test_ALC_out.json'
    mod = ApplyLensCorrection(input_data=params,
                              args=['--output_json', out_fn])
    mod.run()

    tspecs = renderapi.tilespec.get_tile_specs_from_z(
            params['outputStack'],
            float(params['zs'][0]),
            render=renderapi.connect(**params['render']))

    for t in tspecs:
        for lvl, mm in t.ip.items():
            assert(mm.maskUrl is not None)
            mpath = urllib.parse.unquote(
                    urllib.parse.urlparse(mm.maskUrl).path)
            assert(os.path.isfile(mpath))
            mask = plt.imread(mpath)
            assert (mask.shape[0] == height / (2**int(lvl)))
            assert (mask.shape[1] == width / (2**int(lvl)))
