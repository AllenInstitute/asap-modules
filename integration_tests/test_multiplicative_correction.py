import argschema
from rendermodules.intensity_correction.calculate_multiplicative_correction import MakeMedian
from rendermodules.intensity_correction.apply_multiplicative_correction import MultIntensityCorr, getImage
import renderapi
import json
import os
from test_data import MULTIPLICATIVE_INPUT_JSON, multiplicative_correction_example_dir,\
                      render_host, render_port, client_script_location
import shutil
import pytest
import logging
import tifffile 
import numpy as np
import random

render_params = {
    'host': render_host,
    'port': render_port,
    'owner': 'test',
    'project': 'multi_correct_test',
    'client_scripts': client_script_location
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
    renderapi.client.import_single_json_file(
        stack, MULTIPLICATIVE_INPUT_JSON, render=render)
    renderapi.stack.set_stack_state(stack, 'COMPLETE', render=render)
    yield stack
    renderapi.stack.delete_stack(stack, render=render)
@pytest.fixture(scope='module')
def mini_raw_stack(render):
    stack = 'mini_input_raw'
    logger = renderapi.client.logger
    logger.setLevel(logging.DEBUG)
    renderapi.stack.create_stack(stack, render=render)
    with open(MULTIPLICATIVE_INPUT_JSON,'r') as fp:
        tsj = json.load(fp)
    tilespecs = [renderapi.tilespec.TileSpec(json=ts) for ts in tsj]
    tilespecs = random.sample(tilespecs,5)

    renderapi.client.import_tilespecs(stack, tilespecs, render=render)
    renderapi.stack.set_stack_state(stack, 'COMPLETE', render=render)
    yield stack
    renderapi.stack.delete_stack(stack, render=render)

@pytest.fixture(scope='module')
def test_median_stack(raw_stack, render, tmpdir_factory):
    median_stack = 'median_stack'
    output_directory = str(tmpdir_factory.mktemp('Median'))
    #output_directory = os.path.join(os.path.split(MULTIPLICATIVE_INPUT_JSON)[0],'Medians')
    params = {
        "render": render_params,
        "input_stack": raw_stack,
        "file_prefix": "Median",
        "output_stack": median_stack,
        "output_directory": output_directory,
        "minZ": 0,
        "maxZ": 0,
        "pool_size": 3,
        "log_level": "DEBUG"
    }
    mod = MakeMedian(input_data=params, args=[])
    mod.run()

    median_tilespecs = renderapi.tilespec.get_tile_specs_from_stack(
        median_stack, render=render)
    N,M,median_image = getImage(median_tilespecs[0])

    expected_median_file = os.path.join(multiplicative_correction_example_dir,'median','Median_median_stack_0.tif')
    expect_median = tifffile.imread(expected_median_file)

    assert(np.max(np.abs(median_image-expect_median))<3)

    yield median_stack


def test_apply_correction(test_median_stack,raw_stack,render,tmpdir):
    output_directory = os.path.join(os.path.split(MULTIPLICATIVE_INPUT_JSON)[0],'corrected')
    #output_directory = str(tmpdir.join('corrected'))
    output_stack = "Flatfield_corrected_test"
    params = {
        "render":render_params,
        "input_stack": raw_stack,
        "correction_stack": test_median_stack,
        "output_stack": "Flatfield_TEST_DAPI_1",
        "output_directory": output_directory,
        "z_index": 0,
        "pool_size": 10
    }
    mod = MultIntensityCorr(input_data = params, args=[])
    mod.run()

    expected_directory = os.path.join(os.path.split(MULTIPLICATIVE_INPUT_JSON)[0],'corrected')
    output_tilespecs = renderapi.tilespec.get_tile_specs_from_z(output_stack, 0, render=render)

    for ts in output_tilespecs:
        N,M,out_image = getImage(ts)
        out_filepath = ts.ip.get(0)['imageUrl']
        out_file = os.path.split(out_filepath)[0]
        exp_image = tifffile.imread(os.path.join(expected_directory,out_file))
        assert(np.max(np.abs(exp_image-out_image))<3)
