import argschema
import json
import os
import numpy as np
import multiprocessing
from functools import partial
import renderapi
from shapely.geometry import Polygon, box
import gzip
import time
from rendermodules.fine_align.schemas import (
        MakePairJsonShapelySchema,
        MakePairJsonShapelyOutputSchema)


example = {
        "render":{
            "host": "em-131fs",
            "port": 8988,
            "owner": "TEM",
            "project": "17797_1R",
            "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
            },
        "output_dir": "/allen/programs/celltypes/workgroups/em-connectomics/danielk/fine_stack/tpjson",
        "zNeighborDistance": 2,
        "excludeSameLayerNeighbors": True,
        "input_stack": "em_rough_align_zs11357_ze11838_sub_fine_input",
        "minZ": 11593,
        "maxZ": 11602,
        "buffer_pixels": 200,
        "pool_size": 4
        }
#example = {
#        "render":{
#            "host": "em-131fs",
#            "port": 8987,
#            "owner": "TEM",
#            "project": "17797_1R",
#            "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
#            },
#        "output_dir": "/allen/programs/celltypes/workgroups/em-connectomics/danielk/fine_stack/tpjson",
#        "zNeighborDistance": 2,
#        "excludeSameLayerNeighbors": True,
#        "input_stack": "em_rough_align_zs11357_ze11838",
#        "minZ": 11593,
#        "maxZ": 11602,
#        "buffer_pixels": 200,
#        "pool_size": 8
#        }


def get_z_pairs(zValues, zNeighborDistance, excludeSameLayerNeighbors):
    z1, z2 = np.meshgrid(zValues, zValues)
    ind = (z1 <= z2)
    if excludeSameLayerNeighbors:
        ind = (z1 < z2)
    ind = ind & (np.abs(z1 - z2) <= zNeighborDistance)
    return np.vstack((z1[ind].flatten(), z2[ind].flatten())).transpose()


def overlap_polys(ts1,ts2,buffer=0):
    #find the overlap in rough-aligned coordinates
    p1 = Polygon(ts1.bbox_transformed(ndiv_inner=1))
    p2 = Polygon(ts2.bbox_transformed(ndiv_inner=1))
    overlap = p1.intersection(p2)
    if overlap.area<=1.0:
        return None,None
    #get the polygons in lens-corrected space
    p1 = inverse(ts1,overlap)
    p2 = inverse(ts2,overlap)
    return p1,p2


def polygon_list(resolved, buffer_pixels):
    pl = []
    for t in resolved.tilespecs:
        p = Polygon(
                t.bbox_transformed(reference_tforms=resolved.transforms)
                ).buffer(buffer_pixels)
        pl.append(p)
    return pl


def inverse(ts, p, sharedTransforms=None):
    # transform backwards to lens-corrected coordinates
    refids = None
    if sharedTransforms is not None:
        refids = np.array([r.transformId for r in sharedTransforms])

    xy = np.asarray(p.exterior.coords)
    for transform in ts.tforms[::-1][:-1]:
        if isinstance(transform, renderapi.transform.ReferenceTransform):
            rind = np.argwhere(refids == transform.refId)
            if rind.size == 0:
                raise RenderModuleException("no matching sharedTransforms in inverse()")
            xy = sharedTransforms[rind[0][0]].inverse_tform(xy)
        else:
            xy = transform.inverse_tform(xy)
    return Polygon(xy)


def find_pairs(res0, res1, buffer_pixels):
    pds = []
    p0 = polygon_list(res0, buffer_pixels)
    p1 = polygon_list(res1, buffer_pixels)
    centroids0 = [np.array(p.centroid) for p in p0]
    centroids1 = [np.array(p.centroid) for p in p1]
    mx0 = np.array([[t.width, t.height] for t in res0.tilespecs]).max()
    mx1 = np.array([[t.width, t.height] for t in res1.tilespecs]).max()
    mx = max(mx0, mx1)

    for i in range(len(p0)):
        for j in range(len(p1)):
            dist = np.linalg.norm(centroids0[i] - centroids1[j])
            if dist > (2.0 * mx):
                # if they aren't even close, don't even try
                continue

            overlap = p0[i].intersection(p1[j])
            if overlap.area <= 100:
                continue

            bnds = overlap.bounds
            overlap_box = box(bnds[0], bnds[1], bnds[2], bnds[3])
            bblc0 = inverse(res0.tilespecs[i], overlap_box, sharedTransforms=res0.transforms)
            bblc1 = inverse(res1.tilespecs[j], overlap_box, sharedTransforms=res1.transforms)

            pd = {'p':{}, 'q': {}}
            pd['p']['groupId'] = res0.tilespecs[i].layout.sectionId
            pd['p']['id'] = res0.tilespecs[i].tileId
            pd['p']['filter_contour'] = np.array(bblc0.boundary.coords).astype('int').tolist()
            pd['q']['groupId'] = res1.tilespecs[j].layout.sectionId
            pd['q']['id'] = res1.tilespecs[j].tileId
            pd['q']['filter_contour'] = np.array(bblc1.boundary.coords).astype('int').tolist()

            pds.append(pd)
    return pds


def pair_job(render_params, input_stack, buffer_pixels, zpair):
    render = renderapi.connect(**render_params)
    res0 = renderapi.resolvedtiles.get_resolved_tiles_from_z(
            input_stack, zpair[0], render=render)
    res1 = renderapi.resolvedtiles.get_resolved_tiles_from_z(
            input_stack, zpair[1], render=render)

    pairs = find_pairs(res0, res1, buffer_pixels)

    return pairs


class MakePairJsonShapely(argschema.ArgSchemaParser):
    default_schema = MakePairJsonShapelySchema
    default_output_schema = MakePairJsonShapelyOutputSchema


    def run(self):
        zpairs = get_z_pairs(
                self.args['zValues'],
                self.args['zNeighborDistance'],
                self.args['excludeSameLayerNeighbors'])

        mypartial = partial(
                pair_job,
                self.args['render'],
                self.args['input_stack'],
                self.args['buffer_pixels'])


        pairs = []

        #pairs = mypartial(zpairs[1])
        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            for r in pool.imap(mypartial, zpairs):
                pairs += r
        
        outd = {}
        outd['neighborPairs'] = pairs
        outd['renderParametersUrlTemplate'] = (
                "{baseDataUrl}/owner/%s" % self.args['render']['owner'] + 
                "/project/%s" % self.args['render']['project'] +
                "/stack/%s"% self.args['input_stack'] +
                "/tile/{id}/render-parameters")

        fname = ('tile_pairs_' +
                 self.args['input_stack'] +
                 '_z_%d_to_%d' % (self.args['minZ'], self.args['maxZ']) +
                 '_dist_%d.json' % self.args['zNeighborDistance'])
        self.tilepairfile = os.path.join(
                self.args['output_dir'],
                fname)
        if self.args['compress_output']:
            self.tilepairfile += '.gz'
            fout = gzip.open(self.tilepairfile, 'w')
        else:
            fout = open(self.tilepairfile, 'w')
        json.dump(outd, fout, indent=2)
        fout.close()
        
        try:
            self.output({'tile_pair_file': self.tilepairfile})
        except AttributeError as e:
            self.logger.error(e)


if __name__ == '__main__':
    t0 = time.time()
    mmod = MakePairJsonShapely(input_data=example)
    mmod.run()
    print('%0.1f sec' % (time.time() - t0))
