import json
import pytest
import renderapi
import os

from rendermodules.mesh_lens_correction.do_mesh_lens_correction import MeshLensCorrection
from rendermodules.mesh_lens_correction.MeshAndSolveTransform import MeshLensCorrectionException
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
  "outfile": "/allen/aibs/pipeline/image_processing/volume_assembly/scratch/lens_out.json"
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

    mod = MeshLensCorrection(
            input_data=example_for_input,
            args=['--output_json', outjson])

    with pytest.raises(MeshLensCorrectionException):
        mod.run()


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

    mod = MeshLensCorrection(
            input_data=example_for_input,
            args=['--output_json', outjson])

    # add collection and a match so we cover deletion
    sectionId = mod.get_sectionId_from_metafile(example_for_input['metafile'])
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
            render=mod.render)

    mod.run()

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
    mod.args['rerun_pointmatch'] = False
    mod.args['output_dir'] = None
    mod.args['outfile'] = None
    mod.run()

    #test for failure of good solve check
    mod.args['good_solve']['error_std'] = 0.001
    with pytest.raises(MeshLensCorrectionException):
        mod.run()
