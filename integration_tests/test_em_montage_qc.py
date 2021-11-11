import os
import pytest
import renderapi
import json
import copy

from test_data import (PRESTITCHED_STACK_INPUT_JSON,
                       POSTSTITCHED_STACK_INPUT_JSON,
                       MONTAGE_QC_POINT_MATCH_JSON,
                       render_params,
                       montage_qc_project)

from asap.em_montage_qc.detect_montage_defects import (
    DetectMontageDefectsModule)
from asap.module.render_module import RenderModuleException
from asap.em_montage_qc import detect_montage_defects


@pytest.fixture(scope='module')
def render():
    render_params['project'] = montage_qc_project
    render = renderapi.connect(**render_params)
    return render


@pytest.fixture(scope='module')
def prestitched_stack_from_json():
    tilespecs = [renderapi.tilespec.TileSpec(json=d)
                 for d in PRESTITCHED_STACK_INPUT_JSON]
    return tilespecs


@pytest.fixture(scope='module')
def poststitched_stack_from_json():
    tilespecs = [renderapi.tilespec.TileSpec(json=d)
                 for d in POSTSTITCHED_STACK_INPUT_JSON]
    return tilespecs


@pytest.fixture(scope='module')
def point_matches_from_json():
    point_matches = [d for d in MONTAGE_QC_POINT_MATCH_JSON]
    return point_matches


@pytest.fixture(scope='module')
def prestitched_stack(render, prestitched_stack_from_json):
    test_prestitched_stack = 'prestitched_stack'
    renderapi.stack.create_stack(
                        test_prestitched_stack,
                        render=render)
    renderapi.client.import_tilespecs(
                        test_prestitched_stack,
                        prestitched_stack_from_json,
                        render=render)
    renderapi.stack.set_stack_state(
                        test_prestitched_stack,
                        'COMPLETE',
                        render=render)

    # assure stack is built correctly
    assert len({tspec.tileId for tspec
                in prestitched_stack_from_json}.symmetric_difference(set(
                    renderapi.stack.get_stack_tileIds(
                        test_prestitched_stack, render=render)))) == 0

    yield test_prestitched_stack
    renderapi.stack.delete_stack(
                        test_prestitched_stack,
                        render=render)


@pytest.fixture(scope='module')
def poststitched_stack(render, poststitched_stack_from_json):
    test_poststitched_stack = 'poststitched_stack'
    renderapi.stack.create_stack(
                        test_poststitched_stack,
                        render=render)
    renderapi.client.import_tilespecs(
                        test_poststitched_stack,
                        poststitched_stack_from_json,
                        render=render)
    renderapi.stack.set_stack_state(
                        test_poststitched_stack,
                        'COMPLETE',
                        render=render)

    # assure stack is built correctly
    assert len({tspec.tileId for tspec
                in poststitched_stack_from_json}.symmetric_difference(set(
                    renderapi.stack.get_stack_tileIds(
                        test_poststitched_stack, render=render)))) == 0

    yield test_poststitched_stack
    # renderapi.stack.delete_stack(
    #                     test_poststitched_stack,
    #                     render=render)


@pytest.fixture(scope='module')
def point_match_collection(render, point_matches_from_json):
    test_point_match_collection = 'point_match_collection'
    renderapi.pointmatch.import_matches(
                         test_point_match_collection,
                         point_matches_from_json,
                         render=render)

    # check if point matches have been imported properly
    groupIds = render.run(renderapi.pointmatch.get_match_groupIds, test_point_match_collection)
    assert(len(groupIds) == 2)
    yield test_point_match_collection
    # need to delete this collection but no api call exists in renderapi


def test_detect_montage_defects(render,
                                prestitched_stack,
                                poststitched_stack,
                                point_match_collection,
                                tmpdir_factory):
    output_directory = str(tmpdir_factory.mktemp('montage_qc_output'))

    ex = {}
    ex['render'] = render_params
    ex['prestitched_stack'] = prestitched_stack
    ex['poststitched_stack'] = poststitched_stack
    ex['match_collection'] = point_match_collection
    ex['minZ'] = 1028
    ex['maxZ'] = 1029
    ex['plot_sections'] = 'True'
    ex['out_html_dir'] = output_directory
    ex['residual_threshold'] = 4
    ex['neighbors_distance'] = 80
    ex['min_cluster_size'] = 12
    ex['output_json'] = os.path.join(output_directory, 'output.json')

    mod = DetectMontageDefectsModule(input_data=ex, args=[])
    mod.run()

    # check if the output json exists and out_html exists
    assert(
        os.path.exists(ex['output_json']) and
        os.path.isfile(ex['output_json']))

    # read the output json
    with open(ex['output_json'], 'r') as f:
        data = json.load(f)
    f.close()

    assert(len(data['output_html']) > 0)

    assert(len(data['seam_sections']) > 0)
    assert(len(data['hole_sections']) == 1)
    assert(len(data['seam_centroids']) > 0)
    assert(len(data['qc_passed_sections']) == 0)

    for s in data['seam_centroids']:
        assert(len(s) > 0)

    assert(len(data['gap_sections']) == 1)

    # code coverage
    ex['out_html_dir'] = None
    mod = DetectMontageDefectsModule(input_data=ex, args=[])
    mod.run()


def test_detect_montage_defects_fail(
        render,
        prestitched_stack,
        poststitched_stack,
        point_match_collection,
        tmpdir_factory):
    output_directory = str(tmpdir_factory.mktemp('montage_qc_output'))

    ex = copy.copy(detect_montage_defects.example)
    ex['render'] = render_params
    ex['prestitched_stack'] = prestitched_stack
    ex['poststitched_stack'] = poststitched_stack
    ex['match_collection'] = point_match_collection
    ex['minZ'] = 1000
    ex['maxZ'] = 1001
    ex['plot_sections'] = 'True'
    ex['out_html_dir'] = output_directory
    ex['residual_threshold'] = 4
    ex['neighbors_distance'] = 80
    ex['min_cluster_size'] = 12
    ex['output_json'] = os.path.join(output_directory, 'output.json')

    mod = DetectMontageDefectsModule(input_data=ex, args=[])
    with pytest.raises(RenderModuleException):
        mod.run()


def test_stack_in_loading_state(render,
                                prestitched_stack,
                                poststitched_stack,
                                point_match_collection,
                                tmpdir_factory):
    # also set pre and poststitched_stack to
    #   LOADING state to run the clone stack function
    render.run(renderapi.stack.set_stack_state, poststitched_stack, 'LOADING')
    render.run(renderapi.stack.set_stack_state, prestitched_stack, 'LOADING')

    output_directory = str(tmpdir_factory.mktemp('montage_qc_output'))
    ex = copy.copy(detect_montage_defects.example)
    ex['render'] = render_params
    ex['prestitched_stack'] = prestitched_stack
    ex['poststitched_stack'] = poststitched_stack
    ex['match_collection'] = point_match_collection
    ex['minZ'] = 1028
    ex['maxZ'] = 1029
    ex['plot_sections'] = 'False'
    ex['out_html_dir'] = None
    ex['residual_threshold'] = 4
    ex['neighbors_distance'] = 80
    ex['min_cluster_size'] = 12
    ex['output_json'] = os.path.join(output_directory, 'output.json')

    mod = DetectMontageDefectsModule(input_data=ex, args=[])
    mod.run()
