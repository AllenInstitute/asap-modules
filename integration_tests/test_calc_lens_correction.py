import pytest
from rendermodules.lens_correction.lens_correction import LensCorrectionModule
from test_data import calc_lens_parameters

@pytest.fixture(scope='session',autouse=True)
def test_lens_correction():
    
    mod=LensCorrectionModule(input_data = calc_lens_parameters,args=["--output_json","calc_lens_test_output.json"])
    mod.run()
    return mod

def test_me(test_lens_correction):
    assert True