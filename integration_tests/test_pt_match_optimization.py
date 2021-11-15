import os
import pytest
import renderapi
import json

from test_data import (
    render_params, example_env,
    render_json_template, TEST_DATA_ROOT)
from rendermodules.point_match_optimization.pt_match_optimization import (
    PtMatchOptimization
    )

pt_match_opts_example = {
    "render": render_params,
    "SIFT_options": {
        "SIFTfdSize": [4],
        "SIFTmaxScale": [0.82],
        "SIFTminScale": [0.28],
        "SIFTsteps": [8],
        "renderScale": [0.3],
        "matchModelType": ["AFFINE"]
    },
    "url_options": {
        "normalizeForMatching": "true",
        "renderWithFilter": "true",
        "renderWithoutMask": "true"
    },
    "outputDirectory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch/ptmatch",
    "tile_stack": "point_match_optimization_test",
    "stack": "em_2d_montage_apply_mipmaps",
    "tilepair_file": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch/17797_1R/tilepairs/temca4_tilepair_test.json",
    "filter_tilepairs": True,
    "no_tilepairs_to_test": 4,
    "max_tilepairs_with_matches": 4
}

POINT_MATCH_OPTS_INPUT_STACK_TS = render_json_template(
    example_env, 'point_match_opts_tilespecs.json',
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
    # renderapi.stack.delete_stack(ptmatch_input_stack, render=render)


@pytest.fixture(scope='module')
def tilepair_file(render, stack_from_json):
    tile_pair_file = "pt_match_opts_tilepair.json"
    tile_pairs = render_json_template(
        example_env, 'pt_match_opts_tilepairs.json',
        owner=render.DEFAULT_OWNER,
        project=render.DEFAULT_PROJECT,
        stack=pt_match_input_stack)
    with open(tile_pair_file, 'w') as f:
        json.dump(tile_pairs, f, indent=4)

    yield tile_pair_file


def test_pt_match_opts_module(render, pt_match_input_stack, tilepair_file,
                              tmpdir_factory):
    output_dir = str(tmpdir_factory.mktemp('point_match_opts'))

    pt_match_opts_example['render'] = render_params
    pt_match_opts_example['stack'] = pt_match_input_stack
    pt_match_opts_example['outputDirectory'] = output_dir

    pt_match_opts_example['tilepair_file'] = tilepair_file
    out_json = "pt_match_opts_output.json"
    mod = PtMatchOptimization(
        input_data=pt_match_opts_example, args=['--output_json', out_json])
    mod.run()

    with open(out_json, 'r') as f:
        js = json.load(f)

    assert(os.path.exists(js['output_html']) and
           os.path.isfile(js['output_html']))
