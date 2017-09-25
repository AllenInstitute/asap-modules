import pytest
from rendermodules.lens_correction.lens_correction import LensCorrectionModule

@pytest.fixture(scope='session',autouse=True)
def test_lens_correction():
    example_input = {
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
    mod=LensCorrectionModule(input_data = example_input,args=["--output_json","calc_lens_test_output.json"])
    mod.run()
    return mod

def test_me(test_lens_correction):
    assert True