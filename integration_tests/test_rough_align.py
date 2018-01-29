
import os
import pytest
import logging
import renderapi
import json
import glob
from test_data import (ROUGH_MONTAGE_TILESPECS_JSON,
                       ROUGH_POINT_MATCH_COLLECTION,
                       render_params,
                       test_rough_parameters as solver_example)

from rendermodules.materialize.render_downsample_sections import RenderSectionAtScale
from rendermodules.dataimport.make_montage_scapes_stack import MakeMontageScapeSectionStack
from rendermodules.rough_align.do_rough_alignment import SolveRoughAlignmentModule
from rendermodules.rough_align.apply_rough_alignment_to_montages import ApplyRoughAlignmentTransform, example as ex1


logger = renderapi.client.logger
logger.setLevel(logging.DEBUG)


@pytest.fixture(scope='module')
def render():
    render_params['project'] = 'rough_align_test'
    render = renderapi.connect(**render_params)
    return render


@pytest.fixture(scope='module')
def tspecs_from_json():
    tilespecs = [renderapi.tilespec.TileSpec(json=d)
        for d in ROUGH_MONTAGE_TILESPECS_JSON]
    return tilespecs


# A stack with multiple sections montaged
@pytest.fixture(scope='module')
def montage_stack(render,tspecs_from_json):
    test_montage_stack = 'input_montage_stack'
    renderapi.stack.create_stack(test_montage_stack, render=render)
    renderapi.client.import_tilespecs(test_montage_stack, 
                                      tspecs_from_json, 
                                      render=render)
    renderapi.stack.set_stack_state(test_montage_stack, 
                                    'COMPLETE', 
                                    render=render)

    # assure stack is built correctly
    assert len({tspec.tileId for tspec
                in tspecs_from_json}.symmetric_difference(set(
                    renderapi.stack.get_stack_tileIds(
                        test_montage_stack, render=render)))) == 0
    yield test_montage_stack
    renderapi.stack.delete_stack(test_montage_stack, render=render)


@pytest.fixture(scope='module')
def point_matches_from_json():
    point_matches = [d for d in ROUGH_POINT_MATCH_COLLECTION]
    return point_matches
