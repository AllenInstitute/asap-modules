#!/usr/bin/env python

import json
import logging
import multiprocessing

from argschema import ArgSchemaParser
import cv2
import numpy as np
import pathlib2 as pathlib
import renderapi

import imageio

from asap.pointmatch.schemas import (
    PointMatchOpenCVParameters,
    PointMatchClientOutputSchema)
from asap.utilities import uri_utils


example = {
        "ndiv": 8,
        "matchMax": 10000,
        "downsample_scale": 0.3,
        "SIFT_nfeature": 50001,
        "SIFT_noctave": 8,
        "SIFT_sigma": 2.5,
        "RANSAC_outlier": 5.0,
        "FLANN_ntree": 5,
        "FLANN_ncheck": 50,
        "ratio_of_dist": 0.8,
        "CLAHE_grid": 16,
        "CLAHE_clip": 2.5,
        "pairJson": "/allen/programs/celltypes/production/wijem/workflow_data/production/reference_2018_06_21_21_44_56_00_00/jobs/job_27418/tasks/task_25846/tile_pairs_em_2d_raw_lc_stack_z_2908_to_2908_dist_0.json",
        "input_stack": "em_2d_raw_lc_stack",
        "match_collection": "dev_collection_can_delete",
        "render": {
              "owner": "TEM",
              "project": "em_2d_montage_staging",
              "host": "em-131db",
              "port": 8080,
              "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts"
            },
        "ncpus": 7
        }


def ransac_chunk(fargs):
    [k1xy, k2xy, des1, des2, k1ind, args] = fargs

    FLANN_INDEX_KDTREE = 1
    index_params = dict(
            algorithm=FLANN_INDEX_KDTREE,
            trees=args['FLANN_ntree'])
    search_params = dict(checks=args['FLANN_ncheck'])
    flann = cv2.FlannBasedMatcher(index_params, search_params)
    MIN_MATCH_COUNT = 10

    matches = flann.knnMatch(des1[k1ind, :], des2, k=2)

    # store all the good matches as per Lowe's ratio test.
    good = []
    k1 = []
    k2 = []
    for m, n in matches:
        if m.distance < args['ratio_of_dist']*n.distance:
            good.append(m)
    if len(good) > MIN_MATCH_COUNT:
        src_pts = np.float32(
                [k1xy[k1ind, :][m.queryIdx] for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32(
                [k2xy[m.trainIdx] for m in good]).reshape(-1, 1, 2)
        M, mask = cv2.findHomography(
                src_pts,
                dst_pts,
                cv2.RANSAC,
                args['RANSAC_outlier'])
        matchesMask = mask.ravel().tolist()

        good = np.array(good)[np.array(matchesMask).astype('bool')]
        imgIdx = np.array([g.imgIdx for g in good])
        tIdx = np.array([g.trainIdx for g in good])
        qIdx = np.array([g.queryIdx for g in good])
        for i in range(len(tIdx)):
            if imgIdx[i] == 1:
                k1.append(k1xy[k1ind, :][tIdx[i]])
                k2.append(k2xy[qIdx[i]])
            else:
                k1.append(k1xy[k1ind, :][qIdx[i]])
                k2.append(k2xy[tIdx[i]])

    return k1, k2


# FIXME work w/ tile min/max in layout
def to_8bpp(im, min_val=None, max_val=None):
    if im.dtype == np.uint16:
        if max_val is not None or min_val is not None:
            min_val = min_val or 0
            max_val = max_val or 65535
            scale_factor = 255 / (max_val - min_val)
            im = ((np.clip(im, min_val, max_val) - min_val) * scale_factor)
        return (im).astype(np.uint8)
    return im


def read_downsample_equalize_mask_uri(
        impath, scale, CLAHE_grid=None, CLAHE_clip=None, min_val=None, max_val=None):
    # im = cv2.imdecode(
    #     np.fromstring(uri_utils.uri_readbytes(impath[0]), np.uint8),
    #     0)
    im = imageio.v3.imread(uri_utils.uri_readbytes(impath[0]))
    # FIXME this should be read from tilespec
    max_val = max_val or im.max()
    im = to_8bpp(im, min_val, max_val)

    im = cv2.resize(im, (0, 0),
                    fx=scale,
                    fy=scale,
                    interpolation=cv2.INTER_CUBIC)

    if (CLAHE_grid is not None) & (CLAHE_clip is not None):
        clahe = cv2.createCLAHE(
            clipLimit=CLAHE_clip,
            tileGridSize=(CLAHE_grid, CLAHE_grid))
        im = clahe.apply(im)
    else:
        im = cv2.equalizeHist(im)

    if impath[1] is not None:
        # mask = cv2.imdecode(
        #     np.fromstring(uri_utils.uri_readbytes(impath[1]), np.uint8),
        #     0)
        mask = imageio.v3.imread(uri_utils.uri_readbytes(impath[1]))

        mask = cv2.resize(mask, (0, 0),
                          fx=scale,
                          fy=scale,
                          interpolation=cv2.INTER_CUBIC)
        im = cv2.bitwise_and(im, im, mask=mask)

    return im
    # return to_8bpp(im, min_val, max_val)


def read_downsample_equalize_mask(
        impath, *args, **kwargs):
    uri_impath = [pathlib.Path(fn).as_uri() for fn in impath]
    return read_downsample_equalize_mask_uri(uri_impath, *args, **kwargs)


FLANN_INDEX_KDTREE = 1


# TODO take this from existing ransac_chunk
def match_and_ransac(
        loc_p, des_p, loc_q, des_q,
        FLANN_ntree=5, ratio_of_dist=0.7,
        FLANN_ncheck=50, RANSAC_outlier=5.0,
        min_match_count=10, FLANN_index=FLANN_INDEX_KDTREE, **kwargs):
    
    index_params = dict(
        algorithm=FLANN_INDEX_KDTREE,
        trees=FLANN_ntree)
    search_params = dict(checks=FLANN_ncheck)
    flann = cv2.FlannBasedMatcher(index_params, search_params)

    matches = flann.knnMatch(des_p, des_q, k=2)

    # store all the good matches as per Lowe's ratio test.
    good = []
    k1 = []
    k2 = []
    for m, n in matches:
        if m.distance < ratio_of_dist * n.distance:
            good.append(m)
    if len(good) > min_match_count:
        src_pts = np.float32(
            [loc_p[m.queryIdx] for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32(
            [loc_q[m.trainIdx] for m in good]).reshape(-1, 1, 2)
        M, mask = cv2.findHomography(
            src_pts,
            dst_pts,
            cv2.RANSAC,
            RANSAC_outlier)
        matchesMask = mask.ravel().tolist()

        good = np.array(good)[np.array(matchesMask).astype('bool')]
        imgIdx = np.array([g.imgIdx for g in good])
        tIdx = np.array([g.trainIdx for g in good])
        qIdx = np.array([g.queryIdx for g in good])
        for i in range(len(tIdx)):
            if imgIdx[i] == 1:
                k1.append(loc_p[tIdx[i]])
                k2.append(loc_q[qIdx[i]])
            else:
                k1.append(loc_p[qIdx[i]])
                k2.append(loc_q[tIdx[i]])

    return k1, k2


# TODO change this to pq terminology
def chunk_match_keypoints(
        loc1, des1, loc2, des2, ndiv=1, full_shape=None,
        ransac_kwargs=None, **kwargs):
    ransac_kwargs = ransac_kwargs or {}
    if full_shape is None:
        full_shape = np.ptp(np.concatenate([loc1, loc2]), axis=0)

    nr, nc = full_shape

    chunk_results = []

    # FIXME better way than doing min and max of arrays
    for i in range(ndiv):
        r = np.arange(nr * i / ndiv, nr * (i + 1) / ndiv)
        for j in range(ndiv):
            c = np.arange(nc * j / ndiv, nc * (j + 1) / ndiv)
            k1ind = np.argwhere(
                (loc1[:, 0] >= r.min()) &
                (loc1[:, 0] <= r.max()) &
                (loc1[:, 1] >= c.min()) &
                (loc1[:, 1] <= c.max())).flatten()

            chunk_results.append(match_and_ransac(
                loc1[k1ind, ...], des1[k1ind, ...],
                loc2, des2,
                **{**ransac_kwargs, **kwargs}))

    p_results, q_results = zip(*chunk_results)
    p_results = np.concatenate([i for i in p_results if len(i)])
    q_results = np.concatenate([i for i in q_results if len(i)])
    return p_results, q_results


def sift_match_images(
        pim, qim, sift_kwargs=None,
        ransac_kwargs=None, match_kwargs=None,
        return_num_features=False,
        **kwargs):
    sift_kwargs = sift_kwargs or {}
    match_kwargs = match_kwargs or {}

    sift = cv2.SIFT_create(**sift_kwargs)

    # find the keypoints and descriptors
    kp1, des1 = sift.detectAndCompute(pim, None)
    kp2, des2 = sift.detectAndCompute(qim, None)

    k1xy = np.array([np.array(k.pt) for k in kp1])
    k2xy = np.array([np.array(k.pt) for k in kp2])

    k1, k2 = chunk_match_keypoints(
        k1xy, des1, k2xy, des2,
        full_shape=pim.shape,
        ransac_kwargs=ransac_kwargs,
        **{**match_kwargs, **kwargs}
    )
    if return_num_features:
        return (k1, k2), (len(kp1), len(kp2))
    return k1, k2


def locs_to_dict(
        pGroupId, pId, loc_p,
        qGroupId, qId, loc_q,
        scale_factor=1.0, match_max=1000):
    if loc_p.shape[0] < 0:
        return
    loc_p *= scale_factor
    loc_q *= scale_factor

    if loc_p.shape[0] > match_max:
        ind = np.arange(loc_p.shape[0])
        np.random.shuffle(ind)
        ind = ind[0:match_max]
        loc_p = loc_p[ind, ...]
        loc_q = loc_q[ind, ...]

    return make_pm(
        (pId, qId),
        (pGroupId, qGroupId),
        loc_p, loc_q)


def process_matches(
        pId, pGroupId, p_image_uri,
        qId, qGroupId, q_image_uri,
        downsample_scale=1.0,
        CLAHE_grid=None, CLAHE_clip=None,
        matchMax=1000,
        sift_kwargs=None,
        **kwargs):

    pim = read_downsample_equalize_mask_uri(
        p_image_uri,
        downsample_scale,
        CLAHE_grid=CLAHE_grid,
        CLAHE_clip=CLAHE_clip)
    qim = read_downsample_equalize_mask_uri(
        q_image_uri,
        downsample_scale,
        CLAHE_grid=CLAHE_grid,
        CLAHE_clip=CLAHE_clip)

    (loc_p, loc_q), (num_features_p, num_features_q) = sift_match_images(
        pim, qim, sift_kwargs=sift_kwargs,
        return_num_features=True,
        **kwargs)

    pm_dict = locs_to_dict(
        pGroupId, pId, loc_p,
        qGroupId, qId, loc_q,
        scale_factor=(1. / downsample_scale),
        match_max=matchMax)

    return pm_dict, len(loc_p), num_features_p, num_features_q


def find_matches(fargs):
    [impaths, ids, gids, args] = fargs

    pm_dict, num_matches, num_features_p, num_features_q = process_matches(
        ids[0], gids[0], impaths[0],
        ids[1], gids[1], impaths[1],
        downsample_scale=args["downsample_scale"],
        CLAHE_grid=args["CLAHE_grid"],
        CLAHE_clip=args["CLAHE_clip"],
        sift_kwargs={
            "nfeatures": args["SIFT_nfeature"],
            "nOctaveLayers": args['SIFT_noctave'],
            "sigma": args['SIFT_sigma']
        },
        match_kwargs={
            "ndiv": args["ndiv"],
            "FLANN_ntree": args["FLANN_ntree"],
            "ratio_of_dist": args["ratio_of_dist"],
            "FLANN_ncheck": args["FLANN_ncheck"]
        },
        ransac_kwargs={
            "RANSAC_outlier": args["RANSAC_outlier"]
        },
        matchMax=args["matchMax"]
    )

    render = renderapi.connect(**args['render'])

    renderapi.pointmatch.import_matches(
        args['match_collection'],
        [pm_dict],
        render=render)

    return [impaths, num_features_p, num_features_q, num_matches, num_matches]


def make_pm(ids, gids, k1, k2):
    pm = {}
    pm['pId'] = ids[0]
    pm['qId'] = ids[1]
    pm['pGroupId'] = gids[0]
    pm['qGroupId'] = gids[1]
    pm['matches'] = {'p': [], 'q': [], 'w': []}
    pm['matches']['p'].append(k1[:, 0].tolist())
    pm['matches']['p'].append(k1[:, 1].tolist())
    pm['matches']['q'].append(k2[:, 0].tolist())
    pm['matches']['q'].append(k2[:, 1].tolist())
    pm['matches']['w'] = np.ones(k1.shape[0]).tolist()
    return pm


def parse_tileids(tpjson, logger=logging.getLogger()):
    tile_ids = np.array(
                [[m['p']['id'], m['q']['id']]
                    for m in tpjson['neighborPairs']])

    unique_ids = np.unique(tile_ids.flatten())

    # determine tile index per tile pair
    try:
        tile_index = np.zeros(
                        (tile_ids.shape[0], tile_ids.shape[1])
                        ).astype('int')
    except IndexError as e:
        logger.error('%s : probably no tilepairs' % str(e))

    for i in range(tile_ids.shape[0]):
        for j in range(tile_ids.shape[1]):
            tile_index[i, j] = np.argwhere(unique_ids == tile_ids[i, j])

    return unique_ids, tile_index


def load_pairjson(tilepair_file, logger=logging.getLogger()):
    tpjson = []
    try:
        tpjson = json.load(open(tilepair_file, 'r'))
    except TypeError as e:
        logger.error(e)

    return tpjson


def load_tilespecs(render, input_stack, unique_ids):
    tilespecs = []
    for tid in unique_ids:
        tilespecs.append(
            renderapi.tilespec.get_tile_spec_raw(
                input_stack, tid, render=render))

    return np.array(tilespecs)


class GeneratePointMatchesOpenCV(ArgSchemaParser):
    default_schema = PointMatchOpenCVParameters
    default_output_schema = PointMatchClientOutputSchema

    def run(self):
        render = renderapi.connect(**self.args['render'])
        tpjson = load_pairjson(self.args['pairJson'], logger=self.logger)

        unique_ids, tile_index = parse_tileids(tpjson, logger=self.logger)

        tilespecs = load_tilespecs(
                render,
                self.args['input_stack'],
                unique_ids)

        self.match_image_pairs(
                tilespecs,
                tile_index)

    def match_image_pairs(self, tilespecs, tile_index):
        ncpus = self.args['ncpus']
        if self.args['ncpus'] == -1:
            ncpus = multiprocessing.cpu_count()

        with renderapi.client.WithPool(ncpus) as pool:
            index_list = range(tile_index.shape[0])

            fargs = []
            for i in index_list:
                impaths = [[t.ip[0].imageUrl, t.ip[0].maskUrl]
                           for t in tilespecs[tile_index[i]]]
                ids = [t.tileId for t in tilespecs[tile_index[i]]]
                gids = [t.layout.sectionId
                        for t in tilespecs[tile_index[i]]]
                fargs.append([impaths, ids, gids, self.args])

            for r in pool.imap_unordered(find_matches, fargs):
                log = "\n%s\n%s\n" % (r[0][0], r[0][1])
                log += "  (%d, %d) features found" % (r[1], r[2])
                log += "  (%d, %d) matches made" % (r[3], r[4])
                self.logger.debug(log)

        output = {}
        output['collectionId'] = {}
        output['collectionId']['owner'] = self.args['render']['owner']
        output['collectionId']['name'] = self.args['match_collection']
        output['pairCount'] = tile_index.shape[0]
        self.output(output)


if __name__ == '__main__':
    pm_mod = GeneratePointMatchesOpenCV()
    pm_mod.run()
