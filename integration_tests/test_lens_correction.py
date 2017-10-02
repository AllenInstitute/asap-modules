import os
import json
import pytest
import logging
import renderapi
import numpy as np
import math
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
    logger = renderapi.client.logger
    logger.setLevel(logging.DEBUG)
    renderapi.stack.create_stack(stack, render=render)

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

    with open(TILESPECS_LC_JSON, 'r') as fp:
        tspecs_json = json.load(fp)
    tspecs = [renderapi.tilespec.TileSpec(json=tspec) for tspec in tspecs_json]
    renderapi.client.import_tilespecs(stack, tspecs, render=render)
    renderapi.stack.set_stack_state(stack, 'COMPLETE', render=render)
    yield stack

    renderapi.stack.delete_stack(stack, render=render)

def test_lens_correction(example_tform_dict):
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

    new_tform_path = os.path.join(params['project_path'], 'lens_correction.json')
    with open(new_tform_path, 'r') as fp:
        new_tform_dict = json.load(fp)

    example_tform = renderapi.transform.NonLinearCoordinateTransform(dataString=example_tform_dict['dataString'])
    new_tform = renderapi.transform.NonLinearCoordinateTransform(dataString=new_tform_dict['transform']['dataString'])

    assert np.array_equal([example_tform.height, example_tform.width, example_tform.length, example_tform.dimension],
                          [new_tform.height, new_tform.width, new_tform.length, new_tform.dimension])

    x = np.arange(0, example_tform.width, 50, dtype=np.float64)
    y = np.arange(0, example_tform.height, 50, dtype=np.float64)
    xv, yv = np.meshgrid(x, y)
    xv = xv.flatten()
    yv = yv.flatten()
    test_points = np.array([xv, yv]).T
    test_example_tform = example_tform.tform(test_points)
    test_new_tform = new_tform.tform(test_points)

    tform_norm = np.linalg.norm(test_new_tform - test_example_tform) / math.sqrt(test_new_tform.size)
    print 'Computed norm:'
    print tform_norm
    assert tform_norm < 10

def test_apply_lens_correction(render, stack_no_lc, stack_lc, example_tform_dict):
    params = {
        "render": render_params,
        "inputStack": stack_no_lc,
        "outputStack": stack_lc,
        "zs": [2266],
        "transform": example_tform_dict,
        "refId": None
    }

    mod = ApplyLensCorrection(input_data=params, args=['--output_json', 'test_ALC_out.json'])
    mod.run()

    example_tform = renderapi.transform.NonLinearCoordinateTransform(dataString=params['transform']['dataString'])
    
    x = np.arange(0, example_tform.width, 50, dtype=np.float64)
    y = np.arange(0, example_tform.height, 50, dtype=np.float64)
    xv, yv = np.meshgrid(x, y)
    xv = xv.flatten()
    yv = yv.flatten()
    test_points = np.array([xv, yv]).T    
    test_example_tform = example_tform.tform(test_points)

    for z in params['zs']:
        tspecs = renderapi.tilespec.get_tile_specs_from_z(params['outputStack'], z, render=render)

        for ts in tspecs:
            new_tform_dict = ts.tforms[0].to_dict()
            new_tform = renderapi.transform.NonLinearCoordinateTransform(dataString=new_tform_dict['dataString'])

            assert np.array_equal([example_tform.height, example_tform.width, example_tform.length, example_tform.dimension],
                                  [new_tform.height, new_tform.width, new_tform.length, new_tform.dimension])

            test_new_tform = new_tform.tform(test_points)

            tform_norm = np.linalg.norm(test_new_tform - test_example_tform) / math.sqrt(test_new_tform.size)
            print 'Computed norm:'
            print tform_norm
            assert tform_norm < 10