#!/usr/bin/env python
import json
import re

from lxml import etree
import renderapi

from asap.module.render_module import (
        StackTransitionModule, RenderModuleException)
from asap.rough_align.schemas import (
        MakeAnchorStackSchema)


example = {
        "render": {
            "host": "em-131fs",
            "port": 8987,
            "owner": "TEM",
            "project": "17797_1R",
            "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
            },
        "transform_xml": "/allen/programs/celltypes/workgroups/em-connectomics/danielk/pre_align_rigid/manual_images/minnie_plus.xml",
        "input_stack": "em_2d_montage_solved_py_0_01_mapped",
        "output_stack": "full_rough_anchor_stack_tmp",
        "close_stack": True
        }


def get_affinemodel_from_tformstr(s):
    return renderapi.transform.AffineModel(
        json={"dataString": s.lstrip("matrix(").rstrip(")").replace(",", " "),
              "className": 'mpicbg.trakem2.transform.AffineModel2D'})


def get_patch_transforms_from_tree(t):
    return {p.attrib['title']: get_affinemodel_from_tformstr(
        p.attrib["transform"]) for p in t.findall('.//t2_patch')}


def get_patch_transforms_from_xml(x):
    return get_patch_transforms_from_tree(etree.parse(x))


class RegexDict(dict):
    def get_matching(self, event):
        return (self[key] for key in self if re.match(event, key))


class MakeAnchorStack(StackTransitionModule):
    default_schema = MakeAnchorStackSchema

    def run(self):
        if self.args['transform_json']:
            with open(self.args['transform_json'], 'r') as f:
                j = json.load(f)
            tfj = RegexDict({
                k: renderapi.transform.AffineModel(json=v)
                for (k, v) in j.items()})
        else:
            tfj = RegexDict(
                    get_patch_transforms_from_xml(
                        self.args['transform_xml']))
        transform_zs = [int(k.split('_')[0]) for k in tfj]
        z_overlap = self.get_overlapping_inputstack_zvalues(
                zValues=transform_zs)

        new_specs = []
        for z in z_overlap:
            tilespec = renderapi.tilespec.get_tile_specs_from_z(
                    self.args['input_stack'],
                    z,
                    render=self.render)
            if len(tilespec) != 1:
                raise RenderModuleException(
                        "expected 1 tilespec for z = %d in stack %s, "
                        "found %d" %
                        (z, self.args['input_stack'], len(tilespec)))
            tilespec[0].tforms = list(tfj.get_matching('%d_*' % z))
            new_specs.append(tilespec[0])

        self.output_tilespecs_to_stack(new_specs)


if __name__ == "__main__":
    mmod = MakeAnchorStack()
    mmod.run()
