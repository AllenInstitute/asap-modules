#!/usr/bin/env python
import logging

import numpy as np
import renderapi
from renderapi.transform import AffineModel, RigidModel, SimilarityModel

from asap.module.render_module import RenderModule
from asap.registration.schemas import (
    RegisterSectionSchema, RegisterSectionOutputSchema)
from asap.stack.consolidate_transforms import consolidate_transforms

example = {
    "render": {
        'host': 'em-131db',
        'port': 8080,
        'owner': "TEM",
        'project': "247488_8R",
        'client_scripts': "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
        'memGB': '2G'
    },
    "reference_stack": "combined_133_pre_fix",
    "moving_stack": "combined_133_pre_fix",
    "output_stack": "output_stack",
    "match_collection": "rough_align_fixes",
    "registration_model": "Similarity",
    "reference_z": 1000,
    "moving_z": 1001,
    "overwrite_output": True,
    "consolidate_transforms": True
}

logger = logging.getLogger(__name__)


def fit_model_to_points(render, ref_stack, moving_stack, match_collection,
                        match_owner, Transform, ref_z, moving_z, consolidate):
    # tilespecs for both sections
    ref_tspecs = renderapi.tilespec.get_tile_specs_from_z(
        ref_stack, ref_z, render=render)
    moving_tspecs = renderapi.tilespec.get_tile_specs_from_z(
        moving_stack, moving_z, render=render)

    for i, tspec in enumerate(ref_tspecs):
        pid = tspec.tileId
        pgroup = tspec.layout.sectionId
        match = renderapi.pointmatch.get_matches_involving_tile(
            match_collection, pgroup, pid, owner=match_owner, render=render)[0]
        p_pts = []
        q_pts = []
        if match['pId'] == pid:
            qid = match['qId']
            p_pts = np.array(match['matches']['p']).T
            q_pts = np.array(match['matches']['q']).T
        else:
            qid = match['pId']
            pid = match['qId']
            p_pts = np.array(match['matches']['q']).T
            q_pts = np.array(match['matches']['p']).T

        tspecq = next(ts for ts in moving_tspecs if ts.tileId == qid)

        B = renderapi.transform.estimate_dstpts(
            tspecq.tforms, q_pts)  # source points (moving points)
        A = renderapi.transform.estimate_dstpts(
            tspec.tforms, p_pts)  # dest points (ref points)

        final_transform = Transform()
        final_transform.estimate(B, A)

        tspecq.tforms.append(final_transform)
        if consolidate:
            newt = consolidate_transforms(tspecq.tforms, keep_ref_tforms=True)
            tspecq.tforms = newt
    return moving_tspecs


class RegisterSectionByPointMatch(RenderModule):
    default_schema = RegisterSectionSchema
    default_output_schema = RegisterSectionOutputSchema

    def run(self):
        if self.args['registration_model'] == "Affine":
            Transform = AffineModel
        if self.args['registration_model'] == "Rigid":
            print("rigid")
            Transform = RigidModel
        elif self.args['registration_model'] == "Similarity":
            Transform = SimilarityModel

        tilespecs = fit_model_to_points(self.render,
                                        self.args['reference_stack'],
                                        self.args['moving_stack'],
                                        self.args['match_collection'],
                                        self.args['match_owner'],
                                        Transform,
                                        self.args['reference_z'],
                                        self.args['moving_z'],
                                        self.args['consolidate_transforms'])

        stacks = self.render.run(
            renderapi.render.get_stacks_by_owner_project,
            owner=self.render.DEFAULT_OWNER,
            project=self.render.DEFAULT_PROJECT)
        if not(self.args['output_stack'] in stacks):
            self.render.run(
                renderapi.stack.create_stack, self.args['output_stack'])
        elif self.args['overwrite_output']:
            self.render.run(
                renderapi.stack.set_stack_state, self.args['output_stack'],
                'LOADING')
            self.render.run(
                renderapi.stack.delete_section, self.args['output_stack'],
                self.args['moving_z'])

        renderapi.client.import_tilespecs_parallel(self.args['output_stack'],
                                                   tilespecs,
                                                   render=self.render,
                                                   close_stack=True)
        self.output({
            'out_stack': self.args['output_stack'],
            'registered_z': self.args['moving_z']})


if __name__ == "__main__":
    mod = RegisterSectionByPointMatch()
    mod.run()
