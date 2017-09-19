import argschema
from rendermodules.intensity_correction.calculate_multiplicative_correction import MakeMedian
from rendermodules.intensity_correction.apply_multiplicative_correction import MultIntensityCorr, getImage
import renderapi
import json
import os
from test_data import MULTIPLICATIVE_INPUT_JSON, render_host, render_port,client_script_location
import shutil
import pytest
import logging

render_params = {
    'host':render_host,
    'port':render_port,
    'owner':'test',
    'project':'multi_correct_test',
    'client_scripts':client_script_location
}

@pytest.fixture(scope='module')
def render():
    render = renderapi.connect(**render_params)
    return render

@pytest.fixture(scope='module')
def raw_stack(render):
    stack = 'input_raw'
    logger = renderapi.client.logger
    logger.setLevel(logging.DEBUG)
    renderapi.stack.create_stack(stack, render=render)
    print MULTIPLICATIVE_INPUT_JSON
    renderapi.client.import_single_json_file(stack, MULTIPLICATIVE_INPUT_JSON, render=render)
    renderapi.stack.set_stack_state(stack, 'COMPLETE', render=render)
    yield stack
    renderapi.stack.delete_stack(stack, render=render)

@pytest.fixture(scope='module')
def median_stack(raw_stack,render,tmpdir):
    median_stack = 'median_stack'
    output_directory = str(tmpdir.join('Medians'))
    #output_directory = os.path.join(os.path.split(MULTIPLICATIVE_INPUT_JSON)[0],'Medians')
    params = {
        "render":render_params,
        "input_stack": raw_stack,
        "file_prefix": "Median",
        "output_stack": median_stack,
        "output_directory": output_directory,
        "minZ": 0,
        "maxZ": 0,
        "pool_size": 3,
        "log_level": "DEBUG"
    }
    mod=MakeMedian(input_data = params, args=[])
    mod.run()

    median_tilespecs = renderapi.tilespec.get_tile_specs_from_stack(median_stack, render=render)
    median_image = getImage(median_tilespecs[0])
    yield median_stack


def test_median_stack(median_stack):
    assert True
    
