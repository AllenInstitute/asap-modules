import numpy as np
import json
import renderapi
import cv2
import multiprocessing
from six.moves import urllib
import logging
from argschema import ArgSchemaParser
import os
import gzip
import time
from .schemas import \
        PointMatchOpenCVParameters, \
        PointMatchClientOutputSchema


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

    index_params = dict(
            algorithm=args['FLANN_algorithm'],
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


def read_downsample_equalize_mask(impath, scale, CLAHE_grid=None, CLAHE_clip=None):
    im = cv2.imread(impath[0], 0)

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
        mask = cv2.imread(impath[1], 0)
        mask = cv2.resize(mask, (0, 0),
                          fx=scale,
                          fy=scale,
                          interpolation=cv2.INTER_CUBIC)
        im = cv2.bitwise_and(im, im, mask=mask)

    return im


def make_mask(im, contour, downsample_scale):
    mask = np.zeros_like(im)

    cv2.fillConvexPoly(
            mask,
            (np.array(contour) * downsample_scale).astype('int32'),
            1)

    return mask


def get_image(tspec, args):
    if args['use_render_client']:
        if args['transform_labels']:
            tform_list = []
            for tf in tspec.tforms:
                if tf.labels:
                    if set(tf.labels) & set(args['transform_labels']):
                        tform_list.append(tf)
            tspec.tforms = tform_list
        render = renderapi.connect(**args['render'])
        im = renderapi.client.render_tilespec(
                tspec,
                render=render,
                res=32)[:, :, 0]
        im = cv2.resize(im, (0, 0),
                        fx=args['downsample_scale'],
                        fy=args['downsample_scale'],
                        interpolation=cv2.INTER_CUBIC)

        im_m = np.ma.masked_equal(im, 0).astype('float')
        im_m = (im_m - im_m.min())*255/(im_m.max()-im_m.min())
        im = np.ma.filled(im_m, 0).astype('uint8')
    else:
        impaths = [
            urllib.parse.unquote(
                urllib.parse.urlparse(url).path)
            if url is not None else None 
            for url in [tspec.ip[0].imageUrl, tspec.ip[0].maskUrl]]
        im = read_downsample_equalize_mask(
               impaths,
               args['downsample_scale'],
               CLAHE_grid=args['CLAHE_grid'],
               CLAHE_clip=args['CLAHE_clip'])
    return im


def find_matches(fargs):
    [ptspec, qtspec, args, neighborPair] = fargs

    pim = get_image(ptspec, args)
    qim = get_image(qtspec, args)

    sift = cv2.xfeatures2d.SIFT_create(
            nfeatures=args['SIFT_nfeature'],
            nOctaveLayers=args['SIFT_noctave'],
            sigma=args['SIFT_sigma'])

    pmask = None
    qmask = None
    if not args['ignore_filter_contours']:
        if 'filter_contour' in neighborPair['p']:
            pmask = make_mask(
                    pim,
                    neighborPair['p']['filter_contour'],
                    args['downsample_scale'])
        if 'filter_contour' in neighborPair['q']:
            qmask = make_mask(
                    qim,
                    neighborPair['q']['filter_contour'],
                    args['downsample_scale'])

    # find the keypoints and descriptors
    p_points, p_des = sift.detectAndCompute(pim, pmask)
    q_points, q_des = sift.detectAndCompute(qim, qmask)

    pxy = np.array([np.array(k.pt) for k in p_points])
    qxy = np.array([np.array(k.pt) for k in q_points])

    nr, nc = pim.shape
    kp = []
    kq = []
    ransac_args = []
    results = []
    ndiv = args['ndiv']
    for i in range(ndiv):
        r = np.arange(nr*i/ndiv, nr*(i+1)/ndiv)
        for j in range(ndiv):
            c = np.arange(nc*j/ndiv, nc*(j+1)/ndiv)
            kpind = np.argwhere(
                    (pxy[:, 0] >= r.min()) &
                    (pxy[:, 0] <= r.max()) &
                    (pxy[:, 1] >= c.min()) &
                    (pxy[:, 1] <= c.max())).flatten()
            ransac_args.append([pxy, qxy, p_des, q_des, kpind, args])
            results.append(ransac_chunk(ransac_args[-1]))

    for result in results:
        kp += result[0]
        kq += result[1]

    if len(kp) >= 1:
        kp = np.array(kp) / args['downsample_scale']
        kq = np.array(kq) / args['downsample_scale']

        if kp.shape[0] > args['matchMax']:
            a = np.arange(kp.shape[0])
            np.random.shuffle(a)
            kp = kp[a[0: args['matchMax']], :]
            kq = kq[a[0: args['matchMax']], :]

        render = renderapi.connect(**args['render'])
        pm_dict = make_pm(ptspec, qtspec, kp, kq)

        renderapi.pointmatch.import_matches(
          args['match_collection'],
          [pm_dict],
          render=render)

    return [[ptspec.tileId, qtspec.tileId], len(p_points), len(q_points), len(kp), len(kq)]


def make_pm(ptspec, qtspec, kp, kq):
    pm = {}
    pm['pId'] = ptspec.tileId
    pm['qId'] = qtspec.tileId
    pm['pGroupId'] = ptspec.layout.sectionId
    pm['qGroupId'] = qtspec.layout.sectionId
    pm['matches'] = {'p': [], 'q': [], 'w': []}
    pm['matches']['p'].append(kp[:, 0].tolist())
    pm['matches']['p'].append(kp[:, 1].tolist())
    pm['matches']['q'].append(kq[:, 0].tolist())
    pm['matches']['q'].append(kq[:, 1].tolist())
    pm['matches']['w'] = np.ones(kp.shape[0]).tolist()
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
        raise(e)

    for i in range(tile_ids.shape[0]):
        for j in range(tile_ids.shape[1]):
            tile_index[i, j] = np.argwhere(unique_ids == tile_ids[i, j])

    return unique_ids, tile_index


def load_pairjson(tilepair_file, logger=logging.getLogger()):
    tpjson = []
    ext = os.path.splitext(tilepair_file)[1]
    if ext=='.gz':
        f = gzip.open(tilepair_file, 'r')
    else:
        f = open(tilepair_file, 'r')
    tpjson = json.load(f)
    f.close()

    return tpjson


def load_tilespecs(render, input_stack, unique_ids):
    tilespecs = []
    for tid in unique_ids:
        tilespecs.append(
            renderapi.tilespec.get_tile_spec(
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
                tile_index,
                tpjson)

    def match_image_pairs(self, tilespecs, tile_index, tpjson):
        ncpus = self.args['ncpus']
        if self.args['ncpus'] == -1:
            ncpus = multiprocessing.cpu_count()

        fargs = []
        for i in range(tile_index.shape[0]):
            fargs.append([
                tilespecs[tile_index[i][0]],
                tilespecs[tile_index[i][1]],
                self.args,
                tpjson['neighborPairs'][i]])

        with renderapi.client.WithPool(ncpus) as pool:
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
    t0 = time.time()
    pm_mod = GeneratePointMatchesOpenCV(input_data=example)
    pm_mod.run()
    print(time.time() - t0)
