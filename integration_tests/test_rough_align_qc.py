import os
import pytest
import renderapi
import json
from test_data import (
    MONTAGE_SCAPES_TSPECS,
    ROUGH_QC_TEST_PT_MATCHES,
    ROUGH_QC_OUT_STACK,
    render_params
    )

IMPORT_ERROR = False
try:
    from asap.em_montage_qc.rough_align_qc import RoughAlignmentQC
except:
    IMPORT_ERROR = True


@pytest.fixture(scope='module')
def render():
    render_params['project'] = 'rough_align_test'
    render = renderapi.connect(**render_params)
    return render


@pytest.fixture(scope='module')
def downsample_stack(render):
    pre_rough_stack = "pre_rough_stack"

    renderapi.stack.create_stack(pre_rough_stack, render=render)
    renderapi.client.import_tilespecs(
        pre_rough_stack, MONTAGE_SCAPES_TSPECS, render=render)
    renderapi.stack.set_stack_state(pre_rough_stack, "COMPLETE", render=render)
    yield pre_rough_stack
    render.run(renderapi.stack.delete_stack, pre_rough_stack)


@pytest.fixture(scope='module')
def rough_pt_match_collection(render):
    pt_matches = []
    with open(ROUGH_QC_TEST_PT_MATCHES, 'r') as f:
        pt_matches = json.load(f)

    collection = "rough_pt_matches"
    renderapi.pointmatch.import_matches(collection, pt_matches, render=render)
    yield collection


@pytest.fixture(scope='module')
def outstack(render):
    output_stack = "rough_aligned_stack"

    renderapi.stack.create_stack(output_stack, render=render)
    renderapi.client.import_tilespecs(
        output_stack, ROUGH_QC_OUT_STACK, render=render)
    renderapi.stack.set_stack_state(output_stack, "COMPLETE", render=render)

    stacks = renderapi.render.get_stacks_by_owner_project(render=render)
    assert(output_stack in stacks)
    yield output_stack
    render.run(renderapi.stack.delete_stack, output_stack)


def test_rough_align_qc(
        render, downsample_stack, outstack, tmpdir_factory):
    outdir = str(tmpdir_factory.mktemp("rough_qc"))
    ex = {}
    ex['render'] = render_params
    ex['input_downsampled_stack'] = downsample_stack
    ex['output_downsampled_stack'] = outstack
    ex['minZ'] = 120214
    ex['maxZ'] = 120224
    ex['output_dir'] = outdir
    ex['out_file_format'] = 'pdf'

    outjson = os.path.join(outdir, "output.json")

    mod = RoughAlignmentQC(input_data=ex, args=['--output_json', outjson])
    mod.run()

    # check if there is a pdf file
    items = os.listdir(ex['output_dir'])

    assert(any([n.endswith("pdf") for n in items]))

    ex['out_file_format'] = 'html'

    mod = RoughAlignmentQC(input_data=ex, args=['--output_json', outjson])
    mod.run()

    # check if there is a html file

    items = os.listdir(ex['output_dir'])
    js = []
    with open(outjson, "r") as f:
        js = json.load(f)

    assert(os.path.basename(js['iou_plot']) in items and
           os.path.basename(js['distortion_plot']) in items)
    assert(any([n.endswith("html") for n in items]))
