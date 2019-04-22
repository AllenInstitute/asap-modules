import renderapi
from renderapi.errors import RenderError
from rendermodules.rough_align.schemas import (
        DownsampleMaskHandlerSchema)
from rendermodules.module.render_module import (
        RenderModule, RenderModuleException)
import glob
import os
import pathlib
import numpy as np
import cv2
from six.moves import urllib
from shapely.geometry import Polygon, Point


example = {
        "render": {
           "host": "em-131fs",
           "port": 8987,
           "owner": "TEM",
           "project": "17797_1R",
           "client_scripts": "/allen/aibs/pipeline/image_processing"
                             "/volume_assembly/render-jars/production/scripts"
        },
        "mask_dir": "/allen/programs/celltypes/workgroups/em-connectomics"
                    "/danielk/split_masks/section_masks",
        "stack": "em_2d_montage_solved_py_0_01_mapped",
        "collection": "chunk_rough_align_point_matches",
        "zMask": [10395, 10398],
        "zReset": None
        }


def polygon_list_from_mask(mask, transforms=None):
    """Shapely polygons from mask
    
    Parameters
    ----------
    mask : numpy array, uint8
    transforms: list of renderapi transforms to apply to the mask

    Returns
    -------
    list : 
        shapely polygons which outline regions where mask is non-zero
        Render retains parts of image where mask==255
    """
    # openCV >= 4.0:
    # contours, _ = cv2.findContours(
    #         mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    # openCV < 4.0:
    _, contours, _ = cv2.findContours(
            mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c.squeeze().astype('float') for c in contours]
    if transforms:
        for i in range(len(contours)):
            for tf in transforms:
                contours[i] = tf.tform(contours[i])
    mask_polygons = [Polygon(c).buffer(0) for c in contours]
    return mask_polygons


def points_in_mask(mask, pts):
    """Inlier list given a mask and pts
    Parameters
    ----------
    mask : numpy array, uint8
    pts : nested list
        as read from pointmatch json. i.e. match['matches']['p']

    Returns
    -------
    list : float
        as would be included in pointmatch json. i.e. match['matches']['w']
        1.0 = point is inside of non-zero mask region
        0.0 = point is inside of zero-value mask region
        Render retains parts of image where mask==255
    """
    mask_list = []
    for maskpoly in polygon_list_from_mask(mask):
        mask_list += [1.0 if maskpoly.contains(Point(pt)) else 0.0
                     for pt in np.array(pts).transpose()]
    return mask_list


def filter_match(m, tspecs):
    tgroups = np.array([t.layout.sectionId for t in tspecs])
    for pq in ['p', 'q']:
        tspec_ind = np.argwhere(tgroups == m[pq + 'GroupId']).flatten()
        if tspec_ind.size > 0:
            mask_path = urllib.parse.unquote(urllib.parse.urlparse(
                tspecs[tspec_ind[0]].ip['0'].maskUrl).path)
            mask = cv2.imread(mask_path, 0)
            m['matches']['w'] = points_in_mask(mask, m['matches'][pq])
    return m


def reset_match(m):
    m['matches']['w'] = [1.0] * len(m['matches']['w'])
    return m


class DownsampleMaskHandler(RenderModule):
    default_schema = DownsampleMaskHandlerSchema

    def get_tilespec(self, z):
        try:
            tspecs = renderapi.tilespec.get_tile_specs_from_z(
                    self.args['stack'],
                    z,
                    render=self.render)
        except RenderError:
            return None

        if len(tspecs) != 1:
            raise RenderModuleException(
                "Expected 1 tilespec for z=%d, found %d" % (z, len(tspecs)))

        return tspecs[0]

    def add_mask_to_tilespec(self, z, exts):
        tspec = self.get_tilespec(z)
        if not tspec:
            return tspec

        if tspec.ip[0].maskUrl is not None:
            raise RenderModuleException(
                    "Tilespec already has a mask for z = %d" % (z))

        fnames = []
        for ext in exts:
            fnames += glob.glob(
                        os.path.join(
                            self.args['mask_dir'],
                            '%d_*' % z + os.extsep + ext))

        if len(fnames) != 1:
            raise RenderModuleException(
                    "Expected 1 mask file for z = %d, found %d in %s" %
                    (z, len(fnames), self.args['mask_dir']))

        tspec.ip['0'].maskUrl = pathlib.Path(fnames[0]).as_uri()

        return tspec

    def remove_mask_from_tilespec(self, z):
        tspec = self.get_tilespec(z)
        if not tspec:
            return tspec

        if tspec.ip[0].maskUrl is None:
            raise RenderModuleException(
                "Tilespec does not have a mask for z = %d" % (z))

        tspec.ip[0].maskUrl = None

        return tspec

    def run(self):
        tspecs = []
        # add a mask for any zMask not in zReset
        if self.args['zMask']:
            for z in np.setdiff1d(self.args['zMask'], self.args['zReset']):
                tspec = self.add_mask_to_tilespec(z, self.args['mask_exts'])
                if tspec:
                    tspecs.append(tspec)

        # remove a mask for any zReset
        for z in np.setdiff1d(self.args['zReset'], None):
            tspec = self.remove_mask_from_tilespec(z)
            if tspec:
                tspecs.append(tspec)

        if len(tspecs) > 0:
            renderapi.client.import_tilespecs(
                    self.args['stack'],
                    tspecs,
                    render=self.render)
            if self.args['close_stack']:
                renderapi.stack.set_stack_state(
                        self.args['stack'],
                        state='COMPLETE',
                        render=self.render)

        # filter point matches based on zMask
        tspecs = []
        if self.args['zMask']:
            for z in np.setdiff1d(self.args['zMask'], self.args['zReset']):
                tspec = self.get_tilespec(z)
                if tspec:
                    tspecs.append(tspec)
            groups = [t.layout.sectionId for t in tspecs]
            matches = []
            for g in groups:
                matches += renderapi.pointmatch.get_matches_outside_group(
                        self.args['collection'],
                        g,
                        render=self.render)
            for m in matches:
                m = filter_match(m, tspecs)

            renderapi.pointmatch.import_matches(
                    self.args['collection'],
                    matches,
                    render=self.render)

        # remove any masking for each zReset
        tspecs = []
        for z in np.setdiff1d(self.args['zReset'], None):
            tspec = self.get_tilespec(z)
            if tspec:
                tspecs.append(tspec)
            groups = [t.layout.sectionId for t in tspecs]
            matches = []
            for g in groups:
                matches += renderapi.pointmatch.get_matches_outside_group(
                        self.args['collection'],
                        g,
                        render=self.render)
                for m in matches:
                    m = reset_match(m)

            renderapi.pointmatch.import_matches(
                    self.args['collection'],
                    matches,
                    render=self.render)


if __name__ == "__main__":
    dsmod = DownsampleMaskHandler(input_data=example, args=[])
    dsmod.run()
