
import os
import pytest
import logging
import renderapi
import tifffile
import numpy as np
import random
from test_data import (MULTIPLICATIVE_MULTICHAN_INPUT_JSON, multiplicative_multichan_correction_example_dir,
                       render_params)
from rendermodules.intensity_correction.calculate_multiplicative_correction import MakeMedian
from rendermodules.intensity_correction.apply_multiplicative_correction import MultIntensityCorr, getImage, process_tile_multichan


@pytest.fixture(scope='module')
def render():
    render_params['project']='multi_mc_correct_test'
    render = renderapi.connect(**render_params)
    return render

@pytest.fixture(scope='module')
def test_tilespecs():
     tilespecs = [renderapi.tilespec.TileSpec(json=d) for d in MULTIPLICATIVE_MULTICHAN_INPUT_JSON]
     return tilespecs

@pytest.fixture(scope='module')
def raw_stack(render,test_tilespecs):
    stack = 'input_raw'
    renderapi.stack.create_stack(stack, render=render)
    renderapi.client.import_tilespecs(
        stack, test_tilespecs, render=render)
    renderapi.stack.set_stack_state(stack, 'COMPLETE', render=render)
    yield stack
    renderapi.stack.delete_stack(stack, render=render)


@pytest.fixture(scope='module')
def mini_raw_stack(render,test_tilespecs):
    stack = 'mini_input_raw'
    renderapi.stack.create_stack(stack, render=render)
    tilespecs = random.sample(test_tilespecs, 5)

    renderapi.client.import_tilespecs(stack, tilespecs, render=render)
    renderapi.stack.set_stack_state(stack, 'COMPLETE', render=render)
    yield stack
    renderapi.stack.delete_stack(stack, render=render)


@pytest.fixture(scope='module')
def test_median_stack(raw_stack, render, tmpdir_factory):
    median_stack = 'median_stack'
    output_directory = str(tmpdir_factory.mktemp('median'))
    #output_directory = os.path.join(multiplicative_multichan_correction_example_dir,'median')
    params = {
        "render": render_params,
        "input_stack": raw_stack,
        "file_prefix": "Median",
        "output_stack": median_stack,
        "output_directory": output_directory,
        "minZ": 400,
        "maxZ": 400,
        "pool_size": 3,
        "log_level": "DEBUG"
    }
    mod = MakeMedian(input_data=params, args=[])
    mod.run()

    median_tilespecs = renderapi.tilespec.get_tile_specs_from_stack(
        median_stack, render=render)
    for channel in ["DAPI_1","PSD95"]:
        N, M, median_image = getImage(median_tilespecs[0], channel=channel)
        expected_median_file = os.path.join(
            multiplicative_multichan_correction_example_dir, 'median', 'Median_median_stack_%s_400-400.tif' % channel)
        expect_median = tifffile.imread(expected_median_file)

    assert(np.max(np.abs(median_image - expect_median)) < 3)

    yield median_stack

@pytest.fixture(scope='module')
def test_apply_correction(test_median_stack, mini_raw_stack, render, tmpdir_factory):
    output_directory = str(tmpdir_factory.mktemp('intensity_corrected'))
    #output_directory = os.path.join(multiplicative_multichan_correction_example_dir, 'intensity_corrected')
    output_stack = "Flatfield_corrected_test"
    params = {
        "render": render_params,
        "input_stack": mini_raw_stack,
        "correction_stack": test_median_stack,
        "output_stack": output_stack,
        "output_directory": output_directory,
        "z_index": 400,
        "pool_size": 1,
        "overwrite_zlayer": True
    }
    mod = MultIntensityCorr(input_data=params, args=[])
    mod.run()

    expected_directory = os.path.join(multiplicative_multichan_correction_example_dir, 'intensity_corrected')
    output_tilespecs = renderapi.tilespec.get_tile_specs_from_z(
        output_stack, 400, render=render)
    for channel in ["DAPI_1","PSD95"]:
        for ts in output_tilespecs:
            N, M, out_image = getImage(ts, channel=channel)
            chan = next(ch for ch in ts.channels if ch.name==channel)
            out_filepath = chan.ip[0].imageUrl
            out_file = os.path.split(out_filepath)[1]
            exp_image = tifffile.imread(os.path.join(expected_directory, out_file))
            assert(np.max(np.abs(exp_image - out_image)) < 3)
    return mod

def test_single_tile(test_apply_correction,render,tmpdir):

    # get tilespecs
    # Z = test_apply_correction.args['z_index']
    Z = 400
    inp_tilespecs = renderapi.tilespec.get_tile_specs_from_z(
        test_apply_correction.args['input_stack'], Z, render=test_apply_correction.render)
    corr_tilespecs = renderapi.tilespec.get_tile_specs_from_z(
        test_apply_correction.args['correction_stack'], Z, render=test_apply_correction.render)
    # mult intensity correct each tilespecs and return tilespecs
    N, M, C = getImage(corr_tilespecs[0])
    corr_dict = {}
    for channel in ["DAPI_1","PSD95"]:
        _, _, corr_dict[channel] = getImage(corr_tilespecs[0], channel=channel)

	#process_tile_multichan(C, corr_dict, dirout, stackname, clip, scale_factor, clip_min, clip_max, input_ts)
    process_tile_multichan(C,
                 corr_dict,
                 test_apply_correction.args['output_directory'],
                 test_apply_correction.args['output_stack'],
		 True, 1.0,0,65535,
                 inp_tilespecs[0])
