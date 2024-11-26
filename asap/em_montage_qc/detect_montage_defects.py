from functools import partial
import time

import igraph
import networkx as nx
import numpy as np
import renderapi
import renderapi.utils
import requests
from rtree import index as rindex
from six import viewkeys
from scipy.spatial import cKDTree
import shapely
import shapely.strtree

from asap.residuals import compute_residuals as cr
from asap.em_montage_qc.schemas import (
    DetectMontageDefectsParameters, DetectMontageDefectsParametersOutput)
from asap.module.render_module import (
    RenderModule, RenderModuleException)
from asap.em_montage_qc.plots import plot_section_maps

from asap.em_montage_qc.distorted_montages import (
    do_get_z_scales_nopm,
    get_z_scales_nopm,
    get_scale_statistics_mad
    )

example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "danielk",
        "project": "Seams",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "prestitched_stack": "2_sections_near_crack_fine_lam_1e3",
    "poststitched_stack": "2_sections_near_crack_fine_lam_1e3_omitted_auto",
    "match_collection": "NewPMS_combined_with_montage",
    "out_html_dir": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch",
    "plot_sections": "True",
    "minZ": 1028,
    "maxZ": 1029,
    "pool_size": 20
}


# TODO methods for tile borders/boundary points should go in render-python
def determine_numX_numY_rectangle(width, height, meshcellsize=32):
    numX = max([2, np.around(width / meshcellsize)])
    numY = max([2, np.around(height / meshcellsize)])
    return int(numX), int(numY)


def determine_numX_numY_triangle(width, height, meshcellsize=32):
    # TODO do we always want width to define the geometry?
    numX = max([2, np.around(width / meshcellsize)])
    numY = max([
        2,
        np.around(
            height /
            (
                2 * np.sqrt(3. / 4. * (width / (numX - 1)) ** 2)
            ) + 1)
    ])
    return int(numX), int(numY)


def generate_border_mesh_pts(
        width, height, meshcellsize=64, mesh_type="square", **kwargs):
    numfunc = {
        "square": determine_numX_numY_rectangle,
        "triangle": determine_numX_numY_triangle
    }[mesh_type]
    numX, numY = numfunc(width, height, meshcellsize)

    xs = np.linspace(0, width - 1, numX).reshape(-1, 1)
    ys = np.linspace(0, height - 1, numY).reshape(-1, 1)
    
    perim = np.vstack([
        np.hstack([xs, np.zeros(xs.shape)]),
        np.hstack([np.ones(ys.shape) * float(height - 1), ys])[1:-1],
        np.hstack([xs, np.ones(xs.shape) * float(width - 1)])[::-1],
        np.hstack([np.zeros(ys.shape), ys])[1:-1][::-1],

    ])
    return perim


def polygon_from_ts(ts, ref_tforms, **kwargs):
    tsarr = generate_border_mesh_pts(ts.width, ts.height, **kwargs)
    return shapely.geometry.Polygon(
        renderapi.transform.estimate_dstpts(
            ts.tforms, src=tsarr, reference_tforms=ref_tforms))


def polygons_from_rts(rts, **kwargs):
    return [
        polygon_from_ts(ts, rts.transforms, **kwargs)
        for ts in rts.tilespecs
    ]


def strtree_query_geometries(tree, q):
    res = tree.query(q)
    return tree.geometries[res]


def pair_clusters_networkx(pairs, min_cluster_size=25):
    G = nx.Graph()
    G.add_edges_from(pairs)

    # get the connected subraphs from G
    Gc = nx.connected_components(G)
    # get the list of nodes in each component
    fnodes = sorted((list(n) for n in Gc if len(n) > min_cluster_size),
                    key=len, reverse=True)
    return fnodes


def pair_clusters_igraph(pairs, min_cluster_size=25):
    G_ig = igraph.Graph(edges=pairs, directed=False)

    # get the connected subraphs from G
    cc_ig = G_ig.connected_components(mode='strong')
    # filter nodes list with min_cluster_size
    fnodes = sorted((c for c in cc_ig if len(c) > min_cluster_size),
                    key=len, reverse=True)
    return fnodes


def detect_seams(tilespecs, matches, residual_threshold=10,
                 distance=80, min_cluster_size=25, cluster_method="igraph"):
    stats, allmatches = cr.compute_residuals(tilespecs, matches)

    # get mean positions of the point matches as numpy array
    pt_match_positions = np.concatenate(
        list(stats['pt_match_positions'].values()), 0
    )
    # get the tile residuals
    tile_residuals = np.concatenate(
        list(stats['tile_residuals'].values())
    )

    # threshold the points based on residuals
    new_pts = pt_match_positions[
        np.where(tile_residuals >= residual_threshold), :
    ][0]

    # construct a KD Tree using these points
    tree = cKDTree(new_pts)
    # construct a networkx graph

    # find the pairs of points within a distance to each other
    pairs = tree.query_pairs(r=distance)

    fnodes = {
        "igraph": pair_clusters_igraph,
        "networkx": pair_clusters_networkx
    }[cluster_method](pairs, min_cluster_size=min_cluster_size)

    # get pts list for each filtered node list
    points_list = [new_pts[mm, :] for mm in fnodes]
    centroids = np.array([(np.sum(pt, axis=0) / len(pt)).tolist()
                          for pt in points_list])
    return centroids, allmatches, stats


def detect_seams_from_collections(
        render, stack, match_collection, match_owner, z,
        residual_threshold=8, distance=60, min_cluster_size=15, tspecs=None):
    session = requests.session()

    groupId = render.run(
        renderapi.stack.get_sectionId_for_z, stack, z, session=session)
    allmatches = render.run(
        renderapi.pointmatch.get_matches_within_group,
        match_collection,
        groupId,
        owner=match_owner,
        session=session)
    if tspecs is None:
        tspecs = render.run(
            renderapi.tilespec.get_tile_specs_from_z,
            stack, z, session=session)
    session.close()

    return detect_seams(
        tspecs, allmatches,
        residual_threshold=residual_threshold,
        distance=distance,
        min_cluster_size=min_cluster_size)


def detect_disconnected_tiles(pre_tilespecs, post_tilespecs):
    pre_tileIds = {ts.tileId for ts in pre_tilespecs}
    post_tileIds = {ts.tileId for ts in post_tilespecs}
    missing_tileIds = list(pre_tileIds - post_tileIds)
    return missing_tileIds


def detect_disconnected_tiles_from_collections(
        render, prestitched_stack, poststitched_stack,
        z, pre_tilespecs=None, post_tilespecs=None):
    session = requests.session()
    # get the tilespecs for both prestitched_stack and poststitched_stack

    if pre_tilespecs is None:
        pre_tilespecs = render.run(
            renderapi.tilespec.get_tile_specs_from_z,
            prestitched_stack,
            z,
            session=session)
    if post_tilespecs is None:
        post_tilespecs = render.run(
            renderapi.tilespec.get_tile_specs_from_z,
            poststitched_stack,
            z,
            session=session)
    session.close()
    return detect_disconnected_tiles(pre_tilespecs, post_tilespecs)


def detect_stitching_gaps(pre_rts, post_rts, polygon_kwargs={}, use_bbox=False):
    tId_to_pre_polys = {
        ts.tileId: (
            polygon_from_ts(
                ts, pre_rts.transforms, **polygon_kwargs)
            if not use_bbox else shapely.geometry.box(*ts.bbox)
        )
        for ts in pre_rts.tilespecs
    }

    tId_to_post_polys = {
        ts.tileId: (
            polygon_from_ts(
                ts, post_rts.transforms, **polygon_kwargs)
            if not use_bbox else shapely.geometry.box(*ts.bbox)
        )
        for ts in post_rts.tilespecs
    }

    poly_id_to_tId = {
        id(p): tId for tId, p in
        (i for l in (
            tId_to_pre_polys.items(), tId_to_post_polys.items())
         for i in l)
    }

    pre_polys = [*tId_to_pre_polys.values()]
    post_polys = [*tId_to_post_polys.values()]    

    pre_tree = shapely.strtree.STRtree(pre_polys)
    post_tree = shapely.strtree.STRtree(post_polys)

    pre_graph = nx.Graph({
        poly_id_to_tId[id(p)]: [
            poly_id_to_tId[id(r)]
            for r in strtree_query_geometries(pre_tree, p)
        ]
        for p in pre_polys})
    post_graph = nx.Graph({
        poly_id_to_tId[id(p)]: [
            poly_id_to_tId[id(r)]
            for r in strtree_query_geometries(post_tree, p)
        ]
        for p in post_polys})

    diff_g = nx.Graph(pre_graph.edges - post_graph.edges)
    gap_tiles = [n for n in diff_g.nodes() if diff_g.degree(n) > 0]
    return gap_tiles


def detect_stitching_gaps_legacy(render, prestitched_stack, poststitched_stack,
                                 z, pre_tilespecs=None, tilespecs=None):
    session = requests.session()

    if pre_tilespecs is None:
        pre_tilespecs = render.run(
            renderapi.tilespec.get_tile_specs_from_z,
            prestitched_stack,
            z,
            session=session)
    if tilespecs is None:
        tilespecs = render.run(
            renderapi.tilespec.get_tile_specs_from_z,
            poststitched_stack,
            z,
            session=session)

    gap_tiles = detect_stitching_gaps(
        renderapi.resolvedtiles.ResolvedTiles(tilespecs=pre_tilespecs),
        renderapi.resolvedtiles.ResolvedTiles(tilespecs=tilespecs),
        use_bbox=True)
    session.close()
    return gap_tiles


def detect_distortion(render, poststitched_stack, zvalue, threshold_cutoff=[0.005, 0.005], pool_size=20):
    #z_to_scales = {zvalue: do_get_z_scales_nopm(zvalue, [poststitched_stack], render)}
    z_to_scales = {}

    # check if any scale is None
    #zs = [z for z, scales in z_to_scales.items() if scales is None]
    #for z in zs:
    #    z_to_scales[z] = get_z_scales_nopm(z, [poststitched_stack], render)

    try:
        z_to_scales[zvalue] = get_z_scales_nopm(zvalue, [poststitched_stack], render)
    except Exception:
        z_to_scales[zvalue] = None

    # get the mad statistics
    z_to_scalestats = {z: get_scale_statistics_mad(scales) for z, scales in z_to_scales.items() if scales is not None}

    # find zs that fall outside cutoff
    badzs_cutoff = [z for z, s in z_to_scalestats.items() if s[0] > threshold_cutoff[0] or s[1] > threshold_cutoff[1]]
    return badzs_cutoff


def get_pre_post_tspecs(render, prestitched_stack, poststitched_stack, z):
    session = requests.session()
    pre_tilespecs = render.run(
                        renderapi.tilespec.get_tile_specs_from_z,
                        prestitched_stack,
                        z,
                        session=session)
    post_tilespecs = render.run(
                        renderapi.tilespec.get_tile_specs_from_z,
                        poststitched_stack,
                        z,
                        session=session)
    session.close()
    return pre_tilespecs, post_tilespecs


def run_analysis(
        render, prestitched_stack, poststitched_stack, match_collection,
        match_collection_owner, residual_threshold, neighbor_distance,
        min_cluster_size, threshold_cutoff, z):
    pre_tspecs, post_tspecs = get_pre_post_tspecs(
        render, prestitched_stack, poststitched_stack, z)
    disconnected_tiles = detect_disconnected_tiles_from_collections(
        render, prestitched_stack, poststitched_stack, z, pre_tspecs,
        post_tspecs)
    gap_tiles = detect_stitching_gaps_legacy(
        render, prestitched_stack, poststitched_stack, z,
        pre_tspecs, post_tspecs)
    seam_centroids, matches, stats = detect_seams_from_collections(
        render, poststitched_stack, match_collection, match_collection_owner,
        z, residual_threshold=residual_threshold, distance=neighbor_distance,
        min_cluster_size=min_cluster_size, tspecs=post_tspecs)
    distorted_zs = detect_distortion(
        render, poststitched_stack, z, threshold_cutoff=threshold_cutoff)

    return (disconnected_tiles, gap_tiles, seam_centroids,
            distorted_zs, post_tspecs, matches, stats)


def detect_stitching_mistakes(
        render, prestitched_stack, poststitched_stack, match_collection,
        match_collection_owner, threshold_cutoff, residual_threshold, neighbor_distance,
        min_cluster_size, zvalues, pool_size=20):
    mypartial0 = partial(
        run_analysis, render, prestitched_stack, poststitched_stack,
        match_collection, match_collection_owner, residual_threshold,
        neighbor_distance, min_cluster_size, threshold_cutoff)

    with renderapi.client.WithPool(pool_size) as pool:
        (disconnected_tiles, gap_tiles, seam_centroids,
         distorted_zs, post_tspecs, matches, stats) = zip(*pool.map(
            mypartial0, zvalues))

    return (disconnected_tiles, gap_tiles, seam_centroids,
            distorted_zs, post_tspecs, matches, stats)


def check_status_of_stack(render, stack, zvalues):
    status = render.run(renderapi.stack.get_full_stack_metadata,
                        stack)
    new_stack = stack

    if status['state'] == 'LOADING':
        # clone the stack
        new_stack = "{}_zs{}_ze{}_t{}".format(
            stack,
            min(zvalues),
            max(zvalues),
            time.strftime("%m%d%y_%H%M%S"))
        renderapi.stack.clone_stack(stack,
                                    new_stack,
                                    zs=zvalues,
                                    render=render)

    return status['state'], new_stack


class DetectMontageDefectsModule(RenderModule):
    default_output_schema = DetectMontageDefectsParametersOutput
    default_schema = DetectMontageDefectsParameters

    def run(self):
        zvalues1 = self.render.run(renderapi.stack.get_z_values_for_stack,
                                   self.args['poststitched_stack'])
        zrange = range(self.args['minZ'], self.args['maxZ'] + 1)
        zvalues = list(set(zvalues1).intersection(set(zrange)))
        if len(zvalues) == 0:
            raise RenderModuleException(
                ('No valid zvalues found in stack '
                 'for given range {} - {}').format(
                     self.args['minZ'], self.args['maxZ']))

        # check if pre or post stitched stack is in LOADING state.
        # if so, clone them to new stacks
        status1, new_prestitched = check_status_of_stack(
            self.render,
            self.args['prestitched_stack'],
            zvalues)

        status2, new_poststitched = check_status_of_stack(
            self.render,
            self.args['poststitched_stack'],
            zvalues)
        (disconnected_tiles, gap_tiles, seam_centroids,
         distorted_zs, post_tspecs, matches, stats) = detect_stitching_mistakes(
            self.render,
            new_prestitched,
            new_poststitched,
            self.args['match_collection'],
            self.args['match_collection_owner'],
            self.args['threshold_cutoff'],
            self.args['residual_threshold'],
            self.args['neighbors_distance'],
            self.args['min_cluster_size'],
            zvalues,
            pool_size=self.args['pool_size'])

        # find the indices of sections having holes
        hole_indices = [i for i, dt in enumerate(disconnected_tiles)
                        if len(dt) > 0]
        gaps_indices = [i for i, gt in enumerate(gap_tiles) if len(gt) > 0]
        seams_indices = [i for i, sm in enumerate(seam_centroids)
                         if len(sm) > 0]
        holes = [zvalues[i] for i in hole_indices]
        gaps = [zvalues[i] for i in gaps_indices]
        seams = [zvalues[i] for i in seams_indices]
        distorted_zs = [z[0] for z in distorted_zs if len(z) > 0]

        combinedz = list(set(holes + gaps + seams + distorted_zs))
        qc_passed_sections = set(zvalues) - set(combinedz)
        centroids = [seam_centroids[i] for i in seams_indices]
        print(distorted_zs)
        self.args['output_html'] = []
        if self.args['plot_sections']:
            self.args['output_html'] = plot_section_maps(
                self.render,
                self.args['poststitched_stack'],
                post_tspecs,
                matches,
                disconnected_tiles,
                gap_tiles,
                seam_centroids,
                stats,
                zvalues,
                out_html_dir=self.args['out_html_dir'])

        self.output({'output_html': self.args['output_html'],
                     'qc_passed_sections': qc_passed_sections,
                     'hole_sections': holes,
                     'gap_sections': gaps,
                     'seam_sections': seams,
                     'distorted_sections': distorted_zs,
                     'seam_centroids': np.array(centroids, dtype=object)},
                    cls=renderapi.utils.RenderEncoder)
        # delete the stacks that were cloned
        if status1 == 'LOADING':
            self.render.run(renderapi.stack.delete_stack, new_prestitched)

        if status2 == 'LOADING':
            self.render.run(renderapi.stack.delete_stack, new_poststitched)


if __name__ == "__main__":
    mod = DetectMontageDefectsModule()
    mod.run()
