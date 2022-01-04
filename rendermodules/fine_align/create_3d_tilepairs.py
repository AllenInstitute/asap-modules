import argschema
import json
import os
import numpy as np 
from functools import partial
import renderapi
from shapely.geometry import Polygon, box
import rtree.index as rindex
import gzip
import time
import psutil
from itertools import combinations, chain, product
from rendermodules.fine_align.schemas import (
    MakePairJsonShapelySchema,
    MakePairJsonShapelyOutputSchema)
import ray

import warnings
#warnings.filterwarnings("ignore", message="numpy.dtype size changed")
#warnings.filterwarnings("ignore", message="numpy.ufunc size changed")
import sys
if not sys.warnoptions:
    warnings.simplefilter("ignore")

example = {
    "render":{
        "host": "em-131fs",
        "port": 8988,
        "owner": "TEM",
        "project": "17797_1R",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
        },
    "output_dir": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch/tilepairs",
    "zNeighborDistance": 2,
    "excludeSameLayerNeighbors": True,
    "input_stack": "em_rough_align_zs11357_ze11838_sub_fine_input",
    "minZ": 11593,
    "maxZ": 11594,
    "buffer_pixels": 200,
    "pool_size": 4,
    "compress_output": False
}

MBFACTOR = float(1<<20)


def get_z_pairs(zValues, zNeighborDistance, excludeSameLayerNeighbors):
    comb = combinations(zValues, 2)
    Z = [(a,b) for a, b in comb if a <= b and np.abs(a-b) <= zNeighborDistance]
    return Z


def overlap_polygons(ts1, ts2, buffer=0):
    # find the overlap in rough aligned coordinates
    p1 = Polygon(ts1.bbox_transformed(ndiv_inner=1))
    p2 = Polygon(ts2.bbox_transformed(ndiv_inner=1))
    overlap = p1.intersection(p2)

    if overlap.area <= 1.0:
        return None, None
    
    # get the polygons in lens-corrected space
    p1 = inverse(ts1, overlap)
    p2 = inverse(ts2, overlap)
    return p1, p2


def polygon_list(resolved_tiles, buffer_pixels):
    pl = []
    for t in resolved_tiles.tilespecs:
        p = Polygon(
                t.bbox_transformed(reference_tforms=resolved_tiles.transforms)
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

@ray.remote
def get_overlap_polygons(resolved_tiles, poly_list, centroids, mx, zpairs):
    #overlap_polys = {}
    #overlap_area_indices = {}
    pds = []
    #for z1, z2 in zpairs:
    z1,z2 = zpairs
    p0 = poly_list[z1]
    p1 = poly_list[z2]
    c0 = [list(c) for c in centroids[z1]]
    c1 = [list(c) for c in centroids[z2]]
    mxs = max(mx[z1], mx[z2])

    print(z1, z2)

    # check if the centroid distance between a pair of polygons is close enough
    dist = lambda x: np.linalg.norm(np.array(x[0])-np.array(x[1]))

    alist = [c0, c1]
    #[print(dist(a)) for a in list(product(*alist))]
    clist = [a for a in list(product(*alist)) if dist(a) <= (2.0*mxs)]
    index = [list(a) for a in product(*[range(len(x)) for x in alist])]
    indices = [i for i in index if dist((alist[0][i[0]], alist[1][i[1]])) <= (2.0*mxs)]
    
    #overlap_polys[z1, z2] = indices
    index0 = list(zip(*indices))[0]
    index1 = list(zip(*indices))[1]
    
    # for those close polygon pairs check if there overlap area is above a threshold
    overlap_area = lambda x: p0[x[0]].intersection(p1[x[1]])
    #[print(x) for x in indices]
    overlap_area_index = [(x, overlap_area(x)) 
                            for x in indices
                                if overlap_area(x).area > 50000]
    #overlap_area_indices[z1,z2] = overlap_area_index

    # for those that overlap compute their overlapping bounds
    bnds = [o[1].bounds for o in overlap_area_index]
    overlap_boxes = [box(bnd[0], bnd[1], bnd[2], bnd[3]) for bnd in bnds]
    
    bblc0 = [inverse(resolved_tiles[z1].tilespecs[oai[0][0]], 
                        ob, 
                        sharedTransforms=resolved_tiles[z1].transforms) 
                for oai, ob in zip(overlap_area_index, overlap_boxes)]

    # slower option
    #bblc0, bblc1 = zip(*[(inverse(resolved_tiles[z1].tilespecs[oai[0][0]], 
    #                        ob, 
    #                        sharedTransforms=resolved_tiles[z1].transforms), 
    #                     inverse(resolved_tiles[z2].tilespecs[oai[0][1]],
    #                        ob,
    #                        sharedTransforms=resolved_tiles[z2].transforms))
    #                    for oai, ob in zip(overlap_area_index, overlap_boxes)])

    intersec = lambda x,y: x.intersection(Polygon(y.bbox_transformed(tf_limit=0)))
    
    bblc0 = [intersec(bbl, resolved_tiles[z1].tilespecs[ind[0][0]]) 
                for bbl, ind in zip(bblc0, overlap_area_index)]
    
    checkarea = lambda x: x.area >= 1000 and (x.bounds[2]-x.bounds[0]) >= 200 and (x.bounds[3]-x.bounds[1]) >= 200
    #bblc0 = list(map(lambda x: x.area >= 1000, bblc0))

    b0_index = [i for i, x in enumerate(bblc0) if checkarea(x)]
    
    bblc1 = [inverse(resolved_tiles[z2].tilespecs[oai[0][1]],
                        ob,
                        sharedTransforms=resolved_tiles[z2].transforms)
                for oai, ob in zip(overlap_area_index, overlap_boxes)]
    
    bblc1 = [intersec(bbl, resolved_tiles[z2].tilespecs[ind[0][1]])
                for bbl, ind in zip(bblc1, overlap_area_index)]
    
    b1_index = [i for i, x in enumerate(bblc1) if checkarea(x)]

    final_bounds = list(set(b0_index).intersection(set(b1_index)))
    
    pd = {'p': {}, 'q': {}}
    for b in final_bounds:
        i,j = overlap_area_index[b][0]
        pd['p']['groupId'] = resolved_tiles[z1].tilespecs[i].layout.sectionId
        pd['p']['id'] = resolved_tiles[z1].tilespecs[i].tileId
        pd['p']['filter_contour'] = np.array(bblc0[b].boundary.coords).astype('int').tolist()
        pd['q']['groupId'] = resolved_tiles[z2].tilespecs[j].layout.sectionId
        pd['q']['id'] = resolved_tiles[z2].tilespecs[j].tileId
        pd['q']['filter_contour'] = np.array(bblc1[b].boundary.coords).astype('int').tolist()
        pds.append(pd)
    
    return pds


def get_resolved_tiles(input_stack, zpairs, render):
    uniquez = list(set(chain(*zpairs)))
    zvalues = renderapi.stack.get_z_values_for_stack(
                input_stack, 
                render=render)
    inz = [z for z in uniquez if float(z) in zvalues]
    
    resolved_tiles = {}
    for z in inz:
        resolved_tiles[z] = renderapi.resolvedtiles.get_resolved_tiles_from_z(
                                input_stack, z, render=render)
    return resolved_tiles


def get_polygons(resolved_tiles, buffer_pixels):
    poly_list = {}
    centroids = {}
    mx = {}
    for z in resolved_tiles:
        poly_list[z] = polygon_list(resolved_tiles[z], buffer_pixels)
        centroids[z] = [np.array(p.centroid) for p in poly_list[z]]
        mx[z] = np.array([[t.width, t.height] for t in resolved_tiles[z].tilespecs]).max()

    return poly_list, centroids, mx


class FilterTilePairs(argschema.ArgSchemaParser):
    default_schema = MakePairJsonShapelySchema
    default_output_schema = MakePairJsonShapelyOutputSchema

    def run(self):
        self.render = renderapi.connect(**self.args['render'])
        zpairs = get_z_pairs(self.args['zValues'],
                             self.args['zNeighborDistance'],
                             self.args['excludeSameLayerNeighbors'])

        resolved_tiles = get_resolved_tiles(self.args['input_stack'],
                                            zpairs, 
                                            self.render)
        poly_list, centroids, mx = get_polygons(resolved_tiles, self.args['buffer_pixels'])
        
        #mypartial = partial(get_overlap_polygons, resolved_tiles, poly_list, centroids, mx)

        #pairs = []
        #with renderapi.client.WithPool(self.args['pool_size']) as pool:
        #    for r in pool.imap(mypartial, zpairs):
        #        pairs += r
        #
        
        pairs_list = [get_overlap_polygons.remote(resolved_tiles, poly_list, centroids, mx, zpair) for zpair in zpairs]

        pairs = ray.get(pairs_list)
        
        # pairs = get_overlap_polygons(resolved_tiles, poly_list, centroids, mx, zpairs)
        
        print(len(pairs))


if __name__ == '__main__':
    ray.init(object_store_memory=100000000)

    t0 = time.time()
    mod = FilterTilePairs(input_data=example)
    mod.run()
    
    print('%0.1f sec' % (time.time() - t0))
    process = psutil.Process(os.getpid())
    print("Memory usage: {} MB".format((process.memory_info().rss)/MBFACTOR))