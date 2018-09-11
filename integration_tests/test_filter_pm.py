import os
import pytest
import renderapi
import json
import numpy as np
from rendermodules.pointmatch_filter.filter_point_matches \
        import FilterMatches, filter_plot
from matplotlib.figure import Figure
from test_data import (PRESTITCHED_STACK_INPUT_JSON,
                       MONTAGE_QC_POINT_MATCH_JSON,
                       render_params,
                       montage_qc_project)


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
def point_match_collection(render, point_matches_from_json):
    test_point_match_collection = 'point_match_collection'
    renderapi.pointmatch.import_matches(
                         test_point_match_collection,
                         point_matches_from_json,
                         render=render)

    # check if point matches have been imported properly
    groupIds = render.run(
            renderapi.pointmatch.get_match_groupIds,
            test_point_match_collection)
    assert(len(groupIds) == 2)
    yield test_point_match_collection


def test_filter_pm(prestitched_stack, point_match_collection, tmpdir_factory):

    output_directory = str(tmpdir_factory.mktemp('filter_output'))

    ex = {}
    ex['render'] = render_params
    ex['input_stack'] = prestitched_stack
    ex['input_match_collection'] = point_match_collection
    ex['output_match_collection'] = point_match_collection
    ex['overwrite_collection_section'] = True
    ex['resmax'] = 5.0
    ex['transmax'] = 500.0
    ex['minZ'] = 1028
    ex['maxZ'] = 1029
    ex['filter_output_file'] = os.path.join(
            output_directory, 'filter_out.json')
    ex['output_json'] = os.path.join(output_directory, 'output.json')

    fmod = FilterMatches(input_data=ex, args=[])
    fmod.run()

    with open(ex['filter_output_file'], 'r') as f:
        fj = json.load(f)
    assert(len(fj) == len(fmod.args['zValues']))
    for i in range(len(fj)):
        assert(fj[i]['z'] == fmod.args['zValues'][i])

    # pick up some ones to filter
    fmod.args['resmax'] = 1.2
    fmod.args['transmax'] = 100.0
    fmod.run()
    with open(ex['filter_output_file'], 'r') as f:
        fj = json.load(f)
    for f in fj:
        weights = np.array([i['weight'] for i in f['filter']])
        assert(not np.all(weights != 0.0))

    # write to a new collection
    fmod.args['output_match_collection'] = 'something_new'
    fmod.run()
    for z in fmod.args['zValues']:
        m0 = renderapi.pointmatch.get_matches_within_group(
                fmod.args['input_match_collection'],
                str(float(z)),
                render=renderapi.connect(**ex['render']))
        m1 = renderapi.pointmatch.get_matches_within_group(
                fmod.args['output_match_collection'],
                str(float(z)),
                render=renderapi.connect(**ex['render']))
        assert(len(m0) == len(m1))

    # test the plot
    with open(ex['filter_output_file'], 'r') as f:
        fj = json.load(f)
    fig = Figure()
    filter_plot(fig, fj[0])
