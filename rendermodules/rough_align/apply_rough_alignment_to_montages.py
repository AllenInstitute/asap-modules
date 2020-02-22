
import os
import renderapi
import glob
import numpy as np
from ..module.render_module import RenderModule, RenderModuleException
from rendermodules.rough_align.schemas import (
        ApplyRoughAlignmentTransformParameters,
        ApplyRoughAlignmentOutputParameters)
from rendermodules.stack.consolidate_transforms import consolidate_transforms
from rendermodules.rough_align.downsample_mask_handler \
        import polygon_list_from_mask
from functools import partial
import logging
import requests
import pathlib2 as pathlib
import cv2
from six.moves import urllib
from shapely.geometry import Polygon

if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.rough_align.apply_rough_alignment_to_montages"
'''
example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "Tests",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "montage_stack": "rough_test_montage_stack",
    "prealigned_stack": "rough_test_montage_stack",
    "lowres_stack": "rough_test_downsample_rough_stack",
    "output_stack": "rough_test_rough_stack",
    "tilespec_directory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch/rough/jsonFiles",
    "map_z": "False",
    "map_z_start": 251,
    "consolidate_transforms": "True",
    "minZ": 1020,
    "maxZ": 1022,
    "scale": 0.1,
    "pool_size": 20
}
'''
example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "Tests",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "montage_stack": "rough_test_montage_stack",
    "prealigned_stack": "rough_test_montage_stack",
    "lowres_stack": "rough_test_downsample_rough_stack",
    "output_stack": "rough_test_rough_stack",
    "tilespec_directory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch",
    "map_z": "False",
    "new_z": [251, 252, 253],
    "remap_section_ids": "False",
    "consolidate_transforms": "True",
    "old_z": [1020, 1021, 1022],
    "scale": 0.1,
    "apply_scale": "False",
    "pool_size": 20
}


logger = logging.getLogger()


class ApplyRoughAlignmentException(RenderModuleException):
    """Something is wrong in ApplyRough...."""


def get_mask_paths(
        mask_input_dir,
        tilespecs,
        read_masks_from_lowres_stack,
        exts=['png', 'tif']):

    results = {}

    if read_masks_from_lowres_stack:
        for t in tilespecs:
            if t.ip[0].maskUrl is not None:
                results[t.tileId] = t.ip[0].maskUrl

    elif mask_input_dir is not None:
        for t in tilespecs:
            for ext in exts:
                e = os.path.join(
                        mask_input_dir,
                        t.tileId + os.extsep + ext)
                if os.path.isfile(e):
                    if t.tileId in results:
                        raise RenderModuleException(
                                "more than one mask in "
                                "directory %s matches tileId %s" %
                                (mask_input_dir, t))
                    results[t.tileId] = pathlib.Path(e).as_uri()

    return results


def add_masks_to_lowres(render, stack, z, mask_map):
    if len(mask_map) == 0:
        return

    tilespecs = renderapi.tilespec.get_tile_specs_from_z(
            stack, z, render=render)

    for t in tilespecs:
        if t.tileId in mask_map:
            t.ip['0'].maskUrl = mask_map[t.tileId]
            renderapi.client.import_tilespecs(
                    stack,
                    [t],
                    render=render)
    return


def filter_highres_with_masks(resolved_highres, tspec_lowres, mask_map):
    """function to return a filtered list of tilespecs from a
       ResolvedTiles object, based on a lowres mask

    Parameters
    ----------
    resolved_highres : renderapi.resolvedtiles.ResolvedTiles object
        tilespecs and transforms from a single section
    tspec_lowres: renderapi.tilespec.TileSpec object
        tilespec from a downsampled stack
    mask_map: dict
        keys should match lowres tileids, values are mask file URI

    Returns
    -------
    new_highres: List of renderapi.tilespec.TileSpec objects
        which highres specs are fully contained
        within the boundary of mask=255
    """

    if tspec_lowres.tileId not in mask_map.keys():
        return resolved_highres.tilespecs

    impath = urllib.parse.unquote(
                 urllib.parse.urlparse(
                     mask_map[tspec_lowres.tileId]).path)
    maskim = cv2.imread(impath, 0)

    # in this case, it is easiest to outline regions where
    # mask is zero, and then include tilespecs that do
    # not intersect the mask. I think this handles some
    # shapely cases where Polygon.contains() does not work
    # well with polygons that overlap exactly on one edge
    # or, there is some rounding/precision issue
    mask_polygons = polygon_list_from_mask(
            255 - maskim,
            transforms=tspec_lowres.tforms)

    new_highres = []
    for t in resolved_highres.tilespecs:
        tc = t.bbox_transformed(
                    reference_tforms=resolved_highres.transforms)
        tpoly = Polygon(tc).buffer(0)
        pint = [not p.intersects(tpoly) for p in mask_polygons]
        if np.all(pint):
        #for p in mask_polygons:
        #    if not p.intersects(tpoly):
                new_highres.append(t)

    return new_highres


def apply_rough_alignment(render,
                          input_stack,
                          prealigned_stack,
                          lowres_stack,
                          output_stack,
                          output_dir,
                          scale,
                          mask_input_dir,
                          update_lowres_with_masks,
                          read_masks_from_lowres_stack,
                          filter_montage_output_with_masks,
                          mask_exts,
                          Z,
                          apply_scale=False,
                          consolidateTransforms=True,
                          remap_section_ids=False):
    z = Z[0] # z value from the montage stack - to be mapped to the newz values in lowres stack
    newz = Z[1] # z value in the lowres stack for this montage

    session=requests.session()
    try:
        # get lowres stack tile specs
        logger.debug('getting tilespecs from {} z={}'.format(lowres_stack, z))
        lowres_ts = render.run(
                            renderapi.tilespec.get_tile_specs_from_z,
                            lowres_stack,
                            newz,
                            session=session)

        mask_map = get_mask_paths(
                mask_input_dir,
                lowres_ts,
                read_masks_from_lowres_stack)

        if (not read_masks_from_lowres_stack) & \
                update_lowres_with_masks:
            add_masks_to_lowres(render, lowres_stack, newz, mask_map)

        # get the lowres stack rough alignment transformation
        tforms = lowres_ts[0].tforms

        # if all_transforms:
        #     tforms = consolidate_transforms(tforms)

        # tf = tforms[-1]
        for i, tf in enumerate(tforms):
            if isinstance(tf, renderapi.transform.leaf.AffineModel):
                # apply_scale in montagescape stack means
                #   translation components are correct, otherwise
                #   nonhomogeneous are correct
                if apply_scale:
                    tf.M[0:2, 0:2] *= scale
                else:
                    tf.M[:2, -1] /= scale
            elif isinstance(
                    tf, renderapi.transform.leaf.ThinPlateSplineTransform):
                if apply_scale:
                    raise ApplyRoughAlignmentException(
                        "apply_scale is not implemented for "
                        "ThinPlateSplineTransform.")
                else:
                    tforms[i] = tf.scale_coordinates(1./scale)
            else:
                raise ApplyRoughAlignmentException(
                    "apply rough is not implemented for {}".format(
                        tf.className))

        sectionbounds = render.run(
                                renderapi.stack.get_bounds_from_z,
                                input_stack,
                                z,
                                session=session)

        presectionbounds = render.run(
                                    renderapi.stack.get_bounds_from_z,
                                    prealigned_stack,
                                    z,
                                    session=session)

        tx = 0
        ty = 0
        if input_stack == prealigned_stack:
            tx = -int(sectionbounds['minX'])  # - int(prestackbounds['minX'])
            ty = -int(sectionbounds['minY'])  # - int(prestackbounds['minY'])
        else:
            tx = int(sectionbounds['minX']) - int(presectionbounds['minX'])
            ty = int(sectionbounds['minY']) - int(presectionbounds['minY'])

        translation_tform = renderapi.transform.AffineModel(B0=tx, B1=ty)

        ftform = [translation_tform] + tforms
        logger.debug('getting tilespecs from {} z={}'.format(lowres_stack, z))
        """
        highres_ts1 = render.run(
                            renderapi.tilespec.get_tile_specs_from_z,
                            input_stack,
                            z,
                            session=session)
        """
        resolved_highrests1 = render.run(
            renderapi.resolvedtiles.get_resolved_tiles_from_z,
            input_stack, z, session=session)
        highres_ts1 = resolved_highrests1.tilespecs
        sharedTransforms_highrests1 = resolved_highrests1.transforms

        for t in highres_ts1:
            for f in ftform:
                t.tforms.append(f)
            if consolidateTransforms:
                newt = consolidate_transforms(
                    t.tforms, sharedTransforms_highrests1,
                    keep_ref_tforms=True)
                t.tforms = newt
            t.z = newz
            if remap_section_ids:
                t.layout.sectionId = "%s.0"%str(int(newz))

        if filter_montage_output_with_masks:
            # tf.M[0:2, 0:2] /= scale

            # prepend a scaling transformation to the scaled transforms
            #   to map mask coordinates correctly
            lowres_ts[0].tforms.insert(0, renderapi.transform.AffineModel(
               M00=1./scale, M11=1./scale))

            resolved_highrests1.tilespecs = highres_ts1
            highres_ts1 = filter_highres_with_masks(
                    resolved_highrests1,
                    lowres_ts[0],
                    mask_map)

        renderapi.client.import_tilespecs(
            output_stack, highres_ts1,
            sharedTransforms=sharedTransforms_highrests1, render=render)
        session.close()
        return None

    except Exception as e:
        return e


class ApplyRoughAlignmentTransform(RenderModule):
    default_schema = ApplyRoughAlignmentTransformParameters
    default_output_schema = ApplyRoughAlignmentOutputParameters

    def run(self):
        allzvalues = self.render.run(renderapi.stack.get_z_values_for_stack,
                                     self.args['montage_stack'])
        allzvalues = np.array(allzvalues)

        Z = [[a, b] for a, b in
             zip(self.args['old_z'], self.args['new_z'])
             if a in allzvalues]

        mypartial = partial(
                        apply_rough_alignment,
                        self.render,
                        self.args['montage_stack'],
                        self.args['prealigned_stack'],
                        self.args['lowres_stack'],
                        self.args['output_stack'],
                        self.args['tilespec_directory'],
                        self.args['scale'],
                        self.args['mask_input_dir'],
                        self.args['update_lowres_with_masks'],
                        self.args['read_masks_from_lowres_stack'],
                        self.args['filter_montage_output_with_masks'],
                        self.args['mask_exts'],
                        apply_scale=self.args['apply_scale'],
                        consolidateTransforms=self.args['consolidate_transforms'],
                        remap_section_ids=self.args['remap_section_ids'])

        # Create the output stack if it doesn't exist
        if self.args['output_stack'] not in self.render.run(
                renderapi.render.get_stacks_by_owner_project):
            # stack does not exist
            self.render.run(
                renderapi.stack.create_stack,
                self.args['output_stack'])
        else:
            # stack exists and has to be set to LOADING state
            self.render.run(renderapi.stack.set_stack_state,
                            self.args['output_stack'],
                            'LOADING')

        lowres_state = self.render.run(
                renderapi.stack.get_full_stack_metadata,
                self.args['lowres_stack'])['state']

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            results = pool.map(mypartial, Z)

        # raise an exception if all the z values to apply alignment were not
        if not all([r is None for r in results]):
            failed_zs = [(result, z)
                         for result, z in
                         zip(results, Z) if result is not None]
            raise RenderModuleException(
                    "Failed to rough align z values {}".format(failed_zs))

        if self.args["close_stack"]:
            # set stack state to complete
            self.render.run(
                renderapi.stack.set_stack_state,
                self.args['output_stack'],
                state='COMPLETE')

        if self.args['update_lowres_with_masks']:
            # return the lowres stack to original state
            # if any imports were done
            self.render.run(
                renderapi.stack.set_stack_state,
                self.args['lowres_stack'],
                state=lowres_state)

        self.output({
            'zs': np.array(Z),
            'output_stack': self.args['output_stack']})


if __name__ == "__main__":
    mod = ApplyRoughAlignmentTransform(input_data=example)
    mod.run()
