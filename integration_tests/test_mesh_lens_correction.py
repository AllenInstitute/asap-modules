import json
import pytest
import renderapi
import os
from shutil import copyfile
import cv2
import numpy as np

from rendermodules.mesh_lens_correction.do_mesh_lens_correction import \
        MeshLensCorrection, MeshAndSolveTransform, make_mask
from rendermodules.mesh_lens_correction.MeshAndSolveTransform import \
        MeshLensCorrectionException, \
        find_delaunay_with_max_vertices, \
        force_vertices_with_npoints
from test_data import render_params, TEST_DATA_ROOT

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


@pytest.fixture(scope='module')
def render():
    render = renderapi.connect(**render_params)
    return render


def test_coarse_mesh_failure(render, tmpdir_factory):
    outdir = str(tmpdir_factory.mktemp("mesh_lens"))
    out_html_dir = outdir
    example_for_input = dict(example)
    example_for_input['render'] = render_params
    example_for_input['metafile'] = os.path.join(TEST_DATA_ROOT,
                                                 "em_modules_test_data",
                                                 "mesh_lens_correction_3",
                                                 "mesh_lens_metafile_3.json")
    example_for_input['output_dir'] = outdir
    example_for_input['out_html_dir'] = out_html_dir
    example_for_input['z_index'] = 101
    outjson = os.path.join(outdir, 'mesh_lens_out0.json')

    meshmod = MeshLensCorrection(
            input_data=example_for_input,
            args=['--output_json', outjson])

    with pytest.raises(MeshLensCorrectionException):
        meshmod.run()


def test_make_mask(tmpdir_factory):
    # no mask
    mask_dir = str(tmpdir_factory.mktemp("make_mask"))
    mask_coords = None
    basename = 'mymask.png'
    width = 3840
    height = 3840

    maskUrl = make_mask(
            mask_dir,
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
            mask_dir,
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
            mask_dir,
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

    # try writing somewhere you can't
    mask_dir = './this_does_not_exist'
    with pytest.raises(IOError):
        maskUrl3 = make_mask(
                mask_dir,
                width,
                height,
                mask_coords,
                mask_file=None,
                basename=None)


def test_mesh_lens_correction(render, tmpdir_factory):
    outdir = str(tmpdir_factory.mktemp("mesh_lens"))
    out_html_dir = outdir
    example_for_input = dict(example)
    example_for_input['render'] = render_params
    example_for_input['metafile'] = os.path.join(TEST_DATA_ROOT,
                                                 "em_modules_test_data",
                                                 "mesh_lens_correction_2",
                                                 "mesh_lens_metafile_2.json")
    example_for_input['output_dir'] = outdir
    example_for_input['out_html_dir'] = out_html_dir
    example_for_input['outfile'] = os.path.join(outdir, 'out.json')
    outjson = os.path.join(outdir, 'mesh_lens_out.json')
    example_for_input['z_index'] = 100

    meshmod = MeshLensCorrection(
            input_data=example_for_input,
            args=['--output_json', outjson])

    # add collection and a match so we cover deletion
    sectionId = meshmod.get_sectionId_from_metafile(
            example_for_input['metafile'])
    match = {}
    match['qId'] = 'qid'
    match['pId'] = 'pid'
    match['pGroupId'] = sectionId
    match['qGroupId'] = sectionId
    match['matches'] = {}
    match['matches']['q'] = [[0], [1]]
    match['matches']['p'] = [[2], [3]]
    match['matches']['w'] = [0]
    renderapi.pointmatch.import_matches(
            example_for_input['match_collection'],
            [match],
            render=meshmod.render)

    meshmod.run()

    with open(outjson, 'r') as f:
        js = json.load(f)

    with open(js['output_json'], 'r') as f:
        new_tform_dict = json.load(f)

    with open(js['qc_json'], 'r') as f:
        qc = json.load(f)

    assert(
            new_tform_dict['className'] ==
            "mpicbg.trakem2.transform.ThinPlateSplineTransform")

    # some little bits of coverage
    meshmod.args['rerun_pointmatch'] = False
    meshmod.args['output_dir'] = None
    meshmod.args['outfile'] = None
    meshmod.run()

    # test for failure of good solve check
    meshmod.args['good_solve']['error_std'] = 0.001
    with pytest.raises(MeshLensCorrectionException):
        meshmod.run()

    meshmod.args['good_solve']['error_std'] = 3.0
    meshclass = MeshAndSolveTransform(
            input_data=dict(meshmod.args),
            args=['--output_json', outjson])
    meshclass.run()

    # gets into the iterative area adjustment in force_vertices
    tmp_mesh, tmp_area_fac = \
        find_delaunay_with_max_vertices(
                meshclass.bbox,
                4*meshclass.args['nvertex'])
    tmp_mesh, tmp_area_fac = \
        force_vertices_with_npoints(
                tmp_area_fac,
                meshclass.bbox,
                meshclass.coords,
                3)


def test_mesh_with_mask(render, tmpdir_factory):
    outdir = str(tmpdir_factory.mktemp("mesh_lens"))
    out_html_dir = outdir
    example_for_input = dict(example)
    example_for_input['render'] = render_params
    example_for_input['metafile'] = os.path.join(TEST_DATA_ROOT,
                                                 "em_modules_test_data",
                                                 "mesh_lens_correction_2",
                                                 "mesh_lens_metafile_2.json")
    example_for_input['output_dir'] = outdir
    example_for_input['out_html_dir'] = out_html_dir
    example_for_input['outfile'] = os.path.join(outdir, 'out.json')
    outjson = os.path.join(outdir, 'mesh_lens_out.json')
    example_for_input['z_index'] = 200
    example_for_input["mask_coords"] = [
            [0, 100], [100, 0], [3840, 0], [3840, 3840], [0, 3840]]
    example_for_input["mask_dir"] = outdir

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
