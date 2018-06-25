import numpy as np
import argschema
from .schema import LensPointMatchSchema
import json
import renderapi
import cv2
import multiprocessing

example = {
  "render": {
    "host": "em-131snb1",
    "port": 8080,
    "owner": "danielk",
    "project": "lens_corr",
    "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
    "memGB": "2G"
  },
  "close_stack": "True",
  "metafile": "/allen/programs/celltypes/production/wijem/long_term/reference_2018_02_21_01_56_45_00_00/_metadata_20180220175645_247488_8R_tape070A_05_20180220175645_reference_0_.json",
  "match_collection": "raw_lens_matches",
  "regularization": {
    "default_lambda": 1e5,
    "translation_factor": 1e-5,
    "lens_lambda": 1e-5
  },
  "output_dir": "/allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/output",
  "out_html_dir": "/allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/qc"
}


def ransac_chunk(fargs):
    [k1xy, k2xy, des1, des2, k1ind] = fargs

    FLANN_INDEX_KDTREE = 0
    index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)
    MIN_MATCH_COUNT = 10

    matches = flann.knnMatch(des1[k1ind, :], des2, k=2)

    # store all the good matches as per Lowe's ratio test.
    good = []
    k1 = []
    k2 = []
    for m, n in matches:
        if m.distance < 0.7*n.distance:
            good.append(m)
    if len(good) > MIN_MATCH_COUNT:
        src_pts = np.float32(
                [k1xy[k1ind, :][m.queryIdx] for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32(
                [k2xy[m.trainIdx] for m in good]).reshape(-1, 1, 2)
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
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


def read_and_downsample(impath, scale):
    im = cv2.imread(impath, 0)
    im = cv2.equalizeHist(im)
    im = cv2.resize(im, (0, 0),
                    fx=scale,
                    fy=scale,
                    interpolation=cv2.INTER_CUBIC)
    return im


def find_matches(fargs):
    [impaths, ids, gids, ndiv, args] = fargs
    pim = read_and_downsample(impaths[0], args['downsample_scale'])
    qim = read_and_downsample(impaths[1], args['downsample_scale'])
    # Initiate SIFT detector
    sift = cv2.xfeatures2d.SIFT_create()
    # find the keypoints and descriptors with SIFT
    kp1, des1 = sift.detectAndCompute(pim, None)
    kp2, des2 = sift.detectAndCompute(qim, None)
    print('found %d and %d features for 2 images' %
            (len(kp1), len(kp2)))

    # limit to 50k random
    i1 = np.arange(len(kp1))
    i2 = np.arange(len(kp2))

    if len(kp1) > args['nfeature_limit']:
        np.random.shuffle(i1)
        i1 = i1[0:args['nfeature_limit']]
    if len(kp2) > args['nfeature_limit']:
        np.random.shuffle(i2)
        i2 = i2[0:args['nfeature_limit']]

    k1xy = np.array([np.array(k.pt) for k in kp1])[i1, :]
    k2xy = np.array([np.array(k.pt) for k in kp2])[i2, :]
    des1 = des1[i1, :]
    des2 = des2[i2, :]
    print('limiting to %d each' % args['nfeature_limit'])

    nr, nc = pim.shape
    k1 = []
    k2 = []
    fargs = []
    results = []
    for i in range(ndiv):
        r = np.arange(nr*i/ndiv, nr*(i+1)/ndiv)
        for j in range(ndiv):
            c = np.arange(nc*j/ndiv, nc*(j+1)/ndiv)
            k1ind = np.argwhere(
                    (k1xy[:, 0] >= r.min()) &
                    (k1xy[:, 0] <= r.max()) &
                    (k1xy[:, 1] >= c.min()) &
                    (k1xy[:, 1] <= c.max())).flatten()
            fargs.append([k1xy, k2xy, des1, des2, k1ind])
            results.append(ransac_chunk(fargs[-1]))

    for result in results:
        k1 += result[0]
        k2 += result[1]

    k1 = np.array(k1) / args['downsample_scale']
    k2 = np.array(k2) / args['downsample_scale']
    print('found %d matches' % k1.shape[0])

    if k1.shape[0] > args['matchMax']:
        a = np.arange(k1.shape[0])
        np.random.shuffle(a)
        k1 = k1[a[0: args['matchMax']], :]
        k2 = k2[a[0: args['matchMax']], :]
        print('  keeping %d' % k1.shape[0])

    render = renderapi.connect(**args['render'])
    pm_dict = make_pm(ids, gids, k1, k2)
    renderapi.pointmatch.import_matches(
      args['match_collection'],
      [pm_dict],
      render=render)


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


class LensPointMatches(argschema.ArgSchemaParser):
    default_schema = LensPointMatchSchema

    def run(self):
        self.load_pairjson()
        self.load_tilespecs()
        self.match_image_pairs(ndiv=8)

    def load_pairjson(self):
        if self.args["tilepair_output"] != "":
            tmp = json.load(open(self.args['tilepair_output'], 'r'))
            self.args['pairJson'] = tmp['tile_pair_file']
        self.tpjson = json.load(open(self.args['pairJson'], 'r'))
        self.parse_tileids()

    def parse_tileids(self):
        self.tile_ids = np.array(
                [[m['p']['id'], m['q']['id']]
                    for m in self.tpjson['neighborPairs']])
        self.unique_ids = np.unique(self.tile_ids.flatten())
        # determine tile index per tile pair
        self.tile_index = np.zeros(
                (self.tile_ids.shape[0], self.tile_ids.shape[1])
                ).astype('int')
        for i in range(self.tile_ids.shape[0]):
            for j in range(self.tile_ids.shape[1]):
                self.tile_index[i, j] = \
                  np.argwhere(self.unique_ids == self.tile_ids[i, j])

    def load_tilespecs(self):
        render = renderapi.render.connect(**self.args['render'])
        self.tilespecs = []
        for tid in self.unique_ids:
            # order is important
            self.tilespecs.append(
                    renderapi.tilespec.get_tile_spec_raw(
                        self.args['stack'], tid, render=render))
        self.tilespecs = np.array(self.tilespecs)

    def match_image_pairs(self, ndiv=1, index_list=None):
        ncpus = self.args['ncpus']
        if self.args['ncpus'] == -1:
            ncpus = multiprocessing.cpu_count()
        pool = multiprocessing.Pool(ncpus)
        fargs = []
        if index_list is None:
            index_list = range(self.tile_index.shape[0])
        for i in index_list:
            impaths = [
                    t.ip.mipMapLevels[0].imageUrl.split('file://')[-1]
                    for t in self.tilespecs[self.tile_index[i]]]
            ids = [t.tileId
                   for t in self.tilespecs[self.tile_index[i]]]
            gids = [t.layout.sectionId
                    for t in self.tilespecs[self.tile_index[i]]]
            fargs.append([impaths, ids, gids, ndiv, self.args])
        pool.map(find_matches, fargs)


if __name__ == '__main__':
    mod = LensPointMatches(input_data=example)
    mod.run()
