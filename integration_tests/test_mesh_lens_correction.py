import json
import pytest
import renderapi
import os
from shutil import copyfile, rmtree
import cv2
import numpy as np
from bigfeta import jsongz
from em_stitch.lens_correction.mesh_and_solve_transform import \
        MeshLensCorrectionException
from rendermodules.mesh_lens_correction.do_mesh_lens_correction import \
        MeshLensCorrection, make_mask
from test_data import render_params, TEST_DATA_ROOT
import copy

example = {
  "render": {
     "host": "em-131snb1",
     "port": 8080,
     "owner": "gayathrim",
     "project": "lens_corr",
     "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
     "memGB": "2G"
  },
  "z_index": 100,
  "overwrite_zlayer": True,
  "input_stack": "raw_lens_stack",
  "close_stack": "True",
  "metafile": "/allen/aibs/pipeline/image_processing/volume_assembly/em_modules_test_data/mesh_lens_correction_2/mesh_lens_metafile_2.json",
  "match_collection": "raw_lens_matches",
  "nfeature_limit": 20000,
  "regularization": {
        "default_lambda": 1e5,
        "translation_factor": 1e-5,
        "lens_lambda": 1e-5
  },
  "output_stack": "lens_corrected_stack",
  "outfile": "/allen/aibs/pipeline/image_processing/volume_assembly/scratch/lens_out.json",
}

render_params['project'] = "mesh_lens_correction_test"

RAW_LENS_MATCHES_1 = os.path.join(
        TEST_DATA_ROOT,
        "em_modules_test_data",
        "mesh_lens_correction_3",
        "mesh_lc_matches_3.json.gz")

RAW_LENS_MATCHES_2 = os.path.join(
        TEST_DATA_ROOT,
        "em_modules_test_data",
        "mesh_lens_correction_2",
        "mesh_lc_matches_2.json.gz")

RAW_LENS_MATCHES_3 = os.path.join(
        TEST_DATA_ROOT,
        "em_modules_test_data",
        "mesh_lens_correction_2",
        "mesh_lc_matches_2_mask.json.gz")


@pytest.fixture(scope='module')
def render():
    render = renderapi.connect(**render_params)
    return render


@pytest.fixture(scope='module')
def raw_lens_stack_1(render):
    stack = "raw_lens_stack_1"
    yield stack
    renderapi.stack.delete_stack(stack, render=render)


@pytest.fixture(scope='module')
def raw_lens_stack_2(render):
    stack = "raw_lens_stack_2"
    yield stack
    renderapi.stack.delete_stack(stack, render=render)


@pytest.fixture(scope='module')
def raw_lens_stack_3(render):
    stack = "raw_lens_stack_3"
    yield stack
    renderapi.stack.delete_stack(stack, render=render)


@pytest.fixture(scope='module')
def raw_lens_matches_1(render):
    matches = jsongz.load(RAW_LENS_MATCHES_1)
    collection = 'raw_lens_matches_1'
    renderapi.pointmatch.import_matches(collection, matches, render=render)
    yield collection
    renderapi.pointmatch.delete_collection(collection, render=render)


@pytest.fixture(scope='module')
def raw_lens_matches_1b(render):
    matches = jsongz.load(RAW_LENS_MATCHES_1)
    collection = 'raw_lens_matches_1b'
    renderapi.pointmatch.import_matches(collection, matches, render=render)
    yield collection
    renderapi.pointmatch.delete_collection(collection, render=render)


@pytest.fixture(scope='module')
def raw_lens_matches_2(render):
    matches = jsongz.load(RAW_LENS_MATCHES_2)
    collection = 'raw_lens_matches_2'
    renderapi.pointmatch.import_matches(collection, matches, render=render)
    yield collection
    renderapi.pointmatch.delete_collection(collection, render=render)


@pytest.fixture(scope='module')
def raw_lens_matches_3(render):
    matches = jsongz.load(RAW_LENS_MATCHES_3)
    collection = 'raw_lens_matches_3'
    renderapi.pointmatch.import_matches(collection, matches, render=render)
    yield collection
    renderapi.pointmatch.delete_collection(collection, render=render)


@pytest.fixture(scope='function')
def output_directory(tmpdir_factory):
    outdir = str(tmpdir_factory.mktemp("tmp_outputs"))
    yield outdir
    rmtree(outdir)


def test_coarse_mesh_failure(
        render, tmpdir_factory, raw_lens_stack_1,
        raw_lens_matches_1, output_directory):
    # coarse because there aren't many tile pairs
    example_for_input = copy.deepcopy(example)
    example_for_input['render'] = render_params
    example_for_input['metafile'] = os.path.join(TEST_DATA_ROOT,
                                                 "em_modules_test_data",
                                                 "mesh_lens_correction_3",
                                                 "mesh_lens_metafile_3.json")
    example_for_input['output_dir'] = output_directory
    example_for_input['out_html_dir'] = output_directory
    example_for_input['z_index'] = 101
    example_for_input['input_stack'] = raw_lens_stack_1
    example_for_input['match_collection'] = raw_lens_matches_1
    example_for_input['rerun_pointmatch'] = False
    outjson = os.path.join(output_directory, 'mesh_lens_out0.json')

    meshmod = MeshLensCorrection(
            input_data=example_for_input,
            args=['--output_json', outjson])

    with pytest.raises(MeshLensCorrectionException):
        meshmod.run()


def test_correction_call_ptmatch(
        render, tmpdir_factory, raw_lens_stack_1,
        raw_lens_matches_1b, output_directory):
    example_for_input = copy.deepcopy(example)
    example_for_input['render'] = render_params
    example_for_input['metafile'] = os.path.join(TEST_DATA_ROOT,
                                                 "em_modules_test_data",
                                                 "mesh_lens_correction_3",
                                                 "mesh_lens_metafile_3.json")
    example_for_input['output_dir'] = output_directory
    example_for_input['out_html_dir'] = output_directory
    example_for_input['z_index'] = 101
    example_for_input['input_stack'] = raw_lens_stack_1
    # just testing code, let's keep it fast
    example_for_input['downsample_scale'] = 0.15
    example_for_input['match_collection'] = raw_lens_matches_1b
    # this will cover delete_matches_if_exist()
    example_for_input['rerun_pointmatch'] = True
    outjson = os.path.join(output_directory, 'mesh_lens_out0.json')

    meshmod = MeshLensCorrection(
            input_data=example_for_input,
            args=['--output_json', outjson])

    # will raise Exception because there aren't many matches
    with pytest.raises(MeshLensCorrectionException):
        meshmod.run()


def test_make_mask(tmpdir_factory, output_directory):
    # no mask
    mask_coords = None
    basename = 'mymask.png'
    width = 3840
    height = 3840

    maskUrl = make_mask(
            output_directory,
            width,
            height,
            mask_coords,
            mask_file=None,
            basename=basename)
    assert (maskUrl is None)

    # mask from coords
    dx = 100
    dy = 100
    mask_coords = [
            [0, dy], [dx, 0], [width, 0], [width, height], [0, height]]
    maskUrl = make_mask(
            output_directory,
            width,
            height,
            mask_coords,
            mask_file=None,
            basename=basename)
    assert os.path.isfile(maskUrl)

    im = cv2.imread(maskUrl, 0)
    # is it the right shape?
    assert (im.shape == (height, width))
    # are the number of zero pixels close to correct?
    hyp = np.sqrt(dx**2 + dy**2)
    assert (np.abs(im.size - np.count_nonzero(im) - 0.5*dx*dy) < hyp)

    # no overwrite of mask files
    maskUrl2 = make_mask(
            output_directory,
            width,
            height,
            mask_coords,
            mask_file=None,
            basename=basename)
    assert os.path.isfile(maskUrl2)
    assert (maskUrl2 != maskUrl)
    im2 = cv2.imread(maskUrl2, 0)
    assert np.all(im2 == im)

    # mask from file
    mask_file = maskUrl2
    mask_dir = str(tmpdir_factory.mktemp("make_mask2"))
    maskUrl3 = make_mask(
            mask_dir,
            width,
            height,
            mask_coords,
            mask_file=mask_file,
            basename=None)
    assert os.path.isfile(maskUrl3)
    im3 = cv2.imread(maskUrl3, 0)
    assert np.all(im3 == im)
    rmtree(mask_dir)

    # try writing somewhere you can't
    with pytest.raises(IOError):
        maskUrl3 = make_mask(
                './this_does_not_exist',
                width,
                height,
                mask_coords,
                mask_file=None,
                basename=None)


def test_mesh_lens_correction(
        render, tmpdir_factory, raw_lens_stack_2,
        raw_lens_matches_2, output_directory):
    example_for_input = copy.deepcopy(example)
    example_for_input['render'] = render_params
    example_for_input['metafile'] = os.path.join(TEST_DATA_ROOT,
                                                 "em_modules_test_data",
                                                 "mesh_lens_correction_2",
                                                 "mesh_lens_metafile_2.json")
    example_for_input['input_stack'] = raw_lens_stack_2
    example_for_input['output_dir'] = output_directory
    example_for_input['out_html_dir'] = output_directory
    example_for_input['outfile'] = os.path.join(output_directory, 'out.json')
    outjson = os.path.join(output_directory, 'mesh_lens_out.json')
    example_for_input['z_index'] = 100
    example_for_input['match_collection'] = raw_lens_matches_2
    example_for_input['rerun_pointmatch'] = False

    meshmod = MeshLensCorrection(
            input_data=example_for_input,
            args=['--output_json', outjson])
    meshmod.run()

    with open(outjson, 'r') as f:
        js = json.load(f)

    with open(js['output_json'], 'r') as f:
        new_tform_dict = json.load(f)

    assert(
            new_tform_dict['className'] ==
            "mpicbg.trakem2.transform.ThinPlateSplineTransform")


def test_mesh_with_mask(
        render, tmpdir_factory, raw_lens_stack_3,
        raw_lens_matches_3, output_directory):
    example_for_input = copy.deepcopy(example)
    example_for_input['render'] = render_params
    example_for_input['metafile'] = os.path.join(TEST_DATA_ROOT,
                                                 "em_modules_test_data",
                                                 "mesh_lens_correction_2",
                                                 "mesh_lens_metafile_2.json")
    example_for_input['input_stack'] = raw_lens_stack_3
    example_for_input['output_dir'] = output_directory
    example_for_input['out_html_dir'] = output_directory
    example_for_input['outfile'] = os.path.join(output_directory, 'out.json')
    outjson = os.path.join(output_directory, 'mesh_lens_out.json')
    example_for_input['z_index'] = 200
    example_for_input["mask_coords"] = [
            [0, 100], [100, 0], [3840, 0], [3840, 3840], [0, 3840]]
    example_for_input["mask_dir"] = output_directory
    example_for_input['match_collection'] = raw_lens_matches_3
    example_for_input['rerun_pointmatch'] = False

    meshmod = MeshLensCorrection(
            input_data=example_for_input,
            args=['--output_json', outjson])
    meshmod.run()
    assert os.path.isfile(meshmod.maskUrl)

    outdir2 = str(tmpdir_factory.mktemp("somewhere"))
    newfile = os.path.join(outdir2, 'mask_for_input.png')
    copyfile(meshmod.maskUrl, newfile)

    # read it from a file instead of making it
    example_for_input['mask_file'] = newfile
    example_for_input['rerun_pointmatch'] = False
    meshmod = MeshLensCorrection(
            input_data=example_for_input,
            args=['--output_json', outjson])
    meshmod.run()

    renderapi.stack.delete_stack(meshmod.args['output_stack'], render=render)
    rmtree(outdir2)
