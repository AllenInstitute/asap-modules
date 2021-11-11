#!/usr/bin/env python
from functools import partial
import logging

import numpy as np
import renderapi
from renderapi.transform import (
    AffineModel, ReferenceTransform, Polynomial2DTransform, TransformList)

from asap.stack.schemas import (
    ConsolidateTransformsOutputParameters, ConsolidateTransformsParameters)
from asap.module.render_module import (
    RenderModule, RenderModuleException)

example_json = {
    "render": {
        "host": "http://ibs-forrestc-ux1",
        "port": 80,
        "owner": "Forrest",
        "project": "M247514_Rorb_1",
        "client_scripts": "/pipeline/render/render-ws-java-client/src/main/scripts"
    },
    "stack": "ROUGHALIGN_LENS_DAPI_1_deconvnew",
    "output_stack": "ROUGHALIGN_LENS_DAPI_1_deconvnew_CONS",
    "transforms_slice": ":",
    "pool_size": 10,
    "close_stack": True
}


def flatten_tforms(tforms):
    flat_tforms = []
    for tf in tforms:
        if isinstance(tf, TransformList):
            flat_tforms += flatten_tforms(tf.tforms)
        else:
            flat_tforms.append(tf)
    return flat_tforms


def dereference_tforms(tforms, ref_tforms):
    deref_tforms = []
    for tf in tforms:
        if isinstance(tf, ReferenceTransform):
            try:
                mtf = next(
                    mt for mt in ref_tforms if mt.transformId == tf.refId)
                deref_tforms.append(mtf)
            except StopIteration:
                raise RenderModuleException(
                    ("reference transform: {} not found in provided "
                     "reference transforms {}".format(tf.refId, ref_tforms)))
        else:
            deref_tforms.append(tf)
    return deref_tforms


def flatten_and_dereference_tforms(tforms, ref_tforms):
    flat_tforms = flatten_tforms(tforms)
    deref_tforms = dereference_tforms(flat_tforms, ref_tforms)
    deref_tforms = flatten_tforms(deref_tforms)
    return deref_tforms


def consolidate_transforms(tforms, ref_tforms=[], logger=logging.getLogger(),
                           makePolyDegree=0, keep_ref_tforms=False):
    # first flatten and dereference this transform list
    tforms = (flatten_and_dereference_tforms(tforms, ref_tforms)
              if not keep_ref_tforms else flatten_tforms(tforms))
    tform_total = AffineModel()
    total_affines = 0
    new_tform_list = []

    for i, tform in enumerate(tforms):
        try:
            isaffine = 'AffineModel2D' in tform.className
        except AttributeError:
            isaffine = False
        if isaffine:
            total_affines += 1
            tform_total = tform.concatenate(tform_total)
        else:
            logger.debug('consolidate_transforms: non affine {}'.format(tform))
            if total_affines > 0:
                if makePolyDegree > 0:
                    polyTform = Polynomial2DTransform().fromAffine(tform_total)
                    polyTform = polyTform.asorder(makePolyDegree)
                    new_tform_list.append(polyTform)
                else:
                    new_tform_list.append(tform_total)
                tform_total = AffineModel()
                total_affines = 0
            new_tform_list.append(tform)
    if total_affines > 0:
        if makePolyDegree > 0:
            polyTform = Polynomial2DTransform().fromAffine(tform_total)
            polyTform = polyTform.asorder(makePolyDegree)
            new_tform_list.append(polyTform)
        else:
            new_tform_list.append(tform_total)
    return new_tform_list


def process_z(render, stack, outstack, transform_slice, z):
    resolved_tiles = renderapi.resolvedtiles.get_resolved_tiles_from_z(
        stack, z, render=render)

    for ts in resolved_tiles.tilespecs:
        ts.tforms[transform_slice] = consolidate_transforms(
            ts.tforms[transform_slice], resolved_tiles.transforms)

    renderapi.client.import_tilespecs(outstack, resolved_tiles.tilespecs,
                                      resolved_tiles.transforms, render=render)
    return resolved_tiles


class ConsolidateTransforms(RenderModule):
    default_schema = ConsolidateTransformsParameters
    default_output_schema = ConsolidateTransformsOutputParameters

    def run(self):
        stack = self.args['stack']
        outstack = self.args.get('output_stack', None)
        if outstack is None:
            outstack = stack + self.args['postfix']

        # get z values in z value range specified or dynamically
        #   choose
        zvalues = np.array(self.render.run(
            renderapi.stack.get_z_values_for_stack, stack))
        minZ = self.args.get('minZ', np.min(zvalues))
        maxZ = self.args.get('maxZ', np.max(zvalues))
        zvalues = zvalues[zvalues >= minZ]
        zvalues = zvalues[zvalues <= maxZ]

        self.render.run(renderapi.stack.create_stack, outstack)
        if self.args['overwrite_zlayer']:
            for z in zvalues:
                try:
                    renderapi.stack.delete_section(
                        outstack, z, render=self.render)
                except renderapi.errors.RenderError as e:
                    self.logger.error(e)

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            mypartial = partial(
                process_z,
                self.render,
                stack,
                outstack,
                self.args['transforms_slice'])
            resolved_tiles_list = pool.map(mypartial, zvalues)

        if self.args['close_stack']:
            renderapi.stack.set_stack_state(
                outstack,
                'COMPLETE',
                render=self.render)

        output_d = {
            "output_stack": outstack,
            "numZ": len(zvalues)
        }
        self.output(output_d)


if __name__ == "__main__":
    mod = ConsolidateTransforms()
    mod.run()
