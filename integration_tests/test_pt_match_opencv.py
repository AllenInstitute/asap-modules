import os
import pytest
import renderapi
import json
import cv2
from six.moves import urllib

from test_data import (
        render_params, example_env,
        render_json_template, TEST_DATA_ROOT)
from asap.pointmatch.generate_point_matches_opencv import (
    read_downsample_equalize_mask,
    GeneratePointMatchesOpenCV
    )
from asap.mesh_lens_correction.do_mesh_lens_correction import \
    make_mask_from_coords

pt_match_opencv_example = {
        "ndiv": 8,
        "matchMax": 1000,
        "downsample_scale": 0.3,
        "SIFT_nfeature": 20001,
        "SIFT_noctave": 3,
        "SIFT_sigma": 1.5,
        "RANSAC_outlier": 5.0,
        "FLANN_ntree": 5,
        "FLANN_ncheck": 50,
        "ratio_of_dist": 0.8,
        "CLAHE_grid": 16,
        "CLAHE_clip": 2.5,
        "pairJson": "/allen/programs/celltypes/production/wijem/workflow_data/production/reference_2018_06_21_21_44_56_00_00/jobs/job_27418/tasks/task_25846/tile_pairs_em_2d_raw_lc_stack_z_2908_to_2908_dist_0.json",
        "input_stack": "em_2d_raw_lc_stack",
        "match_collection": "dev_collection_can_delete",
        "render": {
              "owner": "TEM",
              "project": "em_2d_montage_staging",
              "host": "em-131db",
              "port": 8080,
              "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts"
            },
        "ncpus": 7
        }


POINT_MATCH_OPTS_INPUT_STACK_TS = render_json_template(
        example_env,
        'point_match_opts_tilespecs.json',
        test_data_root=TEST_DATA_ROOT)


@pytest.fixture(scope='module')
def render():
    render_params['project'] = 'point_match_optimization'
    render = renderapi.connect(**render_params)
    return render


@pytest.fixture(scope='module')
def stack_from_json():
    tilespecs = [renderapi.tilespec.TileSpec(json=d)
                 for d in POINT_MATCH_OPTS_INPUT_STACK_TS]
    return tilespecs


@pytest.fixture(scope='module')
def pt_match_input_stack(render, stack_from_json):
    ptmatch_input_stack = "point_match_input_stack"
    renderapi.stack.create_stack(ptmatch_input_stack,
                                 render=render)
    renderapi.client.import_tilespecs(ptmatch_input_stack,
                                      stack_from_json,
                                      render=render)
    renderapi.stack.set_stack_state(ptmatch_input_stack,
                                    'COMPLETE',
                                    render=render)

    assert len({tspec.tileId for tspec
                in stack_from_json}.symmetric_difference(set(
                        renderapi.stack.get_stack_tileIds(
                            ptmatch_input_stack, render=render)))) == 0
    yield ptmatch_input_stack


@pytest.fixture(scope='module')
def tilepair_file(render, stack_from_json, tmpdir_factory):
    output_dir = str(tmpdir_factory.mktemp('tpairdir'))
    tile_pair_file = os.path.join(
            output_dir,
            "pt_match_opts_tilepair.json")
    tile_pairs = render_json_template(
            example_env, 'pt_match_opts_tilepairs.json',
            owner=render.DEFAULT_OWNER,
            project=render.DEFAULT_PROJECT,
            stack=pt_match_input_stack)
    with open(tile_pair_file, 'w') as f:
        json.dump(tile_pairs, f, indent=4)

    yield tile_pair_file


def test_read_etc(render, pt_match_input_stack, tilepair_file, tmpdir_factory):
    output_dir = str(tmpdir_factory.mktemp('for_masks'))

    with open(tilepair_file, 'r') as f:
        tpj = json.load(f)
    tid = tpj['neighborPairs'][0]['p']['id']
    impath = []
    tspec = renderapi.tilespec.get_tile_spec(
            pt_match_input_stack, tid, render=render)
    impath.append(
            urllib.parse.unquote(
                urllib.parse.urlparse(
                    tspec.ip[0].imageUrl).path))

    w = int(tspec.width)
    h = int(tspec.height)
    coords = [
        [0, 100], [100, 0], [w, 0], [w, h], [0, h]]
    mask = make_mask_from_coords(w, h, coords)
    maskUrl = os.path.join(output_dir, 'mask.png')
    cv2.imwrite(maskUrl, mask)
    impath.append(maskUrl)

    im = read_downsample_equalize_mask(
            impath, 0.5, CLAHE_grid=None, CLAHE_clip=None)
    assert (im.shape[0] == h/2)
    assert (im.shape[1] == w/2)
    read_downsample_equalize_mask(
            impath, 0.5, CLAHE_grid=4, CLAHE_clip=2.0)
    assert (im.shape[0] == h/2)
    assert (im.shape[1] == w/2)


def test_pt_match_opencv(
        render, pt_match_input_stack, tilepair_file, tmpdir_factory):
    output_dir = str(tmpdir_factory.mktemp('point_match_opts'))

    pt_match_opencv_example['render'] = render_params
    pt_match_opencv_example['input_stack'] = pt_match_input_stack
    pt_match_opencv_example['pairJson'] = tilepair_file

    out_json = os.path.join(output_dir, "pt_match_opencv_output.json")
    pmgen = GeneratePointMatchesOpenCV(
            input_data=pt_match_opencv_example,
            args=['--output_json', out_json])
    pmgen.run()

    with open(out_json, 'r') as f:
        js = json.load(f)

    with open(tilepair_file, 'r') as f:
        tpjs = json.load(f)

    assert(js['pairCount'] == len(tpjs['neighborPairs']))

    pt_match_opencv_example['CLAHE_grid'] = None
    pt_match_opencv_example['CLAHE_clip'] = None
    pt_match_opencv_example['ncpus'] = -1
    pt_match_opencv_example['matchMax'] = 50

    pmgen = GeneratePointMatchesOpenCV(
            input_data=pt_match_opencv_example,
            args=['--output_json', out_json])
    pmgen.run()

    with open(out_json, 'r') as f:
        js = json.load(f)

    with open(tilepair_file, 'r') as f:
        tpjs = json.load(f)

    assert(js['pairCount'] == len(tpjs['neighborPairs']))
