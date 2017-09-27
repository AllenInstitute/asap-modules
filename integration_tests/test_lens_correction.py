import os
import json
import pytest
import logging
import renderapi
import numpy as np
from rendermodules.lens_correction.apply_lens_correction import ApplyLensCorrection
from rendermodules.lens_correction.lens_correction import LensCorrectionModule
from test_data import TILESPECS_NO_LC_JSON, TILESPECS_LC_JSON, render_host, render_port, client_script_location

render_params = {
    "host": render_host,
    "port": render_port,
    "owner": "test",
    "project": "lens_correction_test",
    "client_scripts": client_script_location
}

@pytest.fixture(scope='module')
def render():
    render = renderapi.connect(**render_params)
    return render

@pytest.fixture(scope='module')
def example_lc_transform():
    lc_tform = {
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

    return lc_tform

@pytest.fixture(scope='module')
def stack_no_lc(render):
    stack = "test_no_lc"
    logger = renderapi.client.logger
    logger.setLevel(logging.DEBUG)
    renderapi.stack.create_stack(stack, render=render)

    # renderapi.client.import_single_json_file(
    #     stack, TILESPECS_NO_LC_JSON, render=render)

    with open(TILESPECS_NO_LC_JSON, 'r') as fp:
        tspecs_json = json.load(fp)
    tspecs = [renderapi.tilespec.TileSpec(json=tspec) for tspec in tspecs_json]
    renderapi.client.import_tilespecs(stack, tspecs, render=render)
    renderapi.stack.set_stack_state(stack, 'COMPLETE', render=render)
    yield stack

    renderapi.stack.delete_stack(stack, render=render)

@pytest.fixture(scope='module')
def stack_lc(render):
    stack = "test_lc"
    logger = renderapi.client.logger
    logger.setLevel(logging.DEBUG)
    renderapi.stack.create_stack(stack, render=render)

    # renderapi.client.import_single_json_file(
    #     stack, TILESPECS_LC_JSON, render=render)

    with open(TILESPECS_LC_JSON, 'r') as fp:
        tspecs_json = json.load(fp)
    tspecs = [renderapi.tilespec.TileSpec(json=tspec) for tspec in tspecs_json]
    renderapi.client.import_tilespecs(stack, tspecs, render=render)
    renderapi.stack.set_stack_state(stack, 'COMPLETE', render=render)
    yield stack

    renderapi.stack.delete_stack(stack, render=render)

def test_lens_correction(example_lc_transform):
    params = {
        "manifest_path": "/allen/aibs/pipeline/image_processing/volume_assembly/lc_test_data/Wij_Set_594451332/594089217_594451332/_trackem_20170502174048_295434_5LC_0064_01_20170502174047_reference_0_.txt",
        "project_path": "/allen/aibs/pipeline/image_processing/volume_assembly/lc_test_data/Wij_Set_594451332/594089217_594451332/",
        "fiji_path": "/allen/aibs/pipeline/image_processing/volume_assembly/Fiji.app/ImageJ-linux64",
        "grid_size": 3,
        "heap_size": 20,
        "outfile": "test_LC.json",
        "processing_directory": None,
        "SIFT_params": {
            "initialSigma": 1.6,
            "steps": 3,
            "minOctaveSize": 800,
            "maxOctaveSize": 1200,
            "fdSize": 4,
            "fdBins": 8
        },
        "align_params": {
            "rod": 0.92,
            "maxEpsilon": 5.0,
            "minInlierRatio": 0.0,
            "minNumInliers": 5,
            "expectedModelIndex": 1,
            "multipleHypotheses": True,
            "rejectIdentity": True,
            "identityTolerance": 5.0,
            "tilesAreInPlace": True,
            "desiredModelIndex": 0,
            "regularize": False,
            "maxIterationsOptimize": 2000,
            "maxPlateauWidthOptimize": 200,
            "dimension": 5,
            "lambdaVal": 0.01,
            "clearTransform": True,
            "visualize": False
        }
    }

    mod = LensCorrectionModule(input_data=params, args=['--output_json', 'test_LC_out.json'])
    mod.run()

    lc_tform_path = os.path.join(params['project_path'], 'lens_correction.json')
    with open(lc_tform_path, 'r') as fp:
        lc_tform = json.load(fp)

    print lc_tform

    assert example_lc_transform['type'] == lc_tform['transform']['type']
    assert example_lc_transform['className'] == lc_tform['transform']['className']

    example_lc_transform_array = map(float, example_lc_transform['dataString'].split())
    example_lc_transform_array = np.asarray(example_lc_transform_array)

    lc_tform_array = map(float, lc_tform['transform']['dataString'].split())
    lc_tform_array = np.asarray(lc_tform_array)

    assert example_lc_transform_array[0] == lc_tform_array[0]
    assert example_lc_transform_array[1] == lc_tform_array[1]

    """
    with open(example_input["outfile"]) as outjson:
        test_tform = json.load(outjson)

    with open('test_files/lc_transform.json') as good_outjson:
        good_tform = json.load(good_outjson)

    good_tform_array = map(float, good_tform['transform']['dataString'].split().string())
    good_tform_array = np.asarray(good_tform_array)

    test_tform_array = map(float, test_tform['transform']['dataString'].split().string())
    test_tform_array = np.asarray(test_tform_array)

    assert good_tform['transform']['type'] == test_tform['transform']['type']
    assert good_tform['transform']['className'] == test_tform['transform']['className']
    assert np.allclose(test_tform_array, good_form_array, rtol=1e-00)
    """

def test_apply_lens_correction(render, stack_no_lc, stack_lc, example_lc_transform):
    params = {
        "render": render_params,
        "inputStack": stack_no_lc,
        "outputStack": stack_lc,
        "zs": [2266],
        "transform": example_lc_transform,
        "refId": None
    }

    mod = ApplyLensCorrection(input_data=params, args=['--output_json', 'test_ALC_out.json'])
    mod.run()

    """
    r = renderapi.render.connect(**alc_input['render'])
    tspecs = renderapi.tilespec.get_tile_specs_from_stack(example_input['render'], render=r)
    """

    assert True