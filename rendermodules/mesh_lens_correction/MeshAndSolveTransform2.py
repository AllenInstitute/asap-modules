import numpy as np 
import triangle
import scipy.optimize 
from scipy.spatial import Delaunay
import scipy.sparse as sparse
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import factorized 
import argschema 
import renderapi
import copy
import os 
import subprocess 
import json 
import datetime 
import tempfile


def load_matches(render, match_collection, sectionId):
    matches = renderapi.pointmatch.get_matches_within_group(
                match_collection, sectionId, render=render)
    
    tile_ids = np.array([[m['pId'], m['qId']] for m in matches])
    unique_ids = np.unique(tile_ids.flatten())

    # determine tile index per tile pair
    tile_index = np.zeros((
        tile_ids.shape[0],
        tile_ids.shape[1])).astype('int')

    for i in range(tile_ids.shape[0]):
        for j in range(tile_ids.shape[1]):
            tile_index[i, j] = np.argwhere(unique_ids == tile_ids[i, j])
    
    return matches, unique_ids, tile_index


def load_tilespecs(render, input_stack, unique_ids):
    tilespecs = []
    for tid in unique_ids:
        # order is important
        tilespecs.append(
            renderapi.tilespec.get_tile_spec_raw(input_stack, tid, render=render))
        tile_width = tilespecs[0].width
        tile_height = tilespecs[0].height
    return tilespecs, tile_width, tile_height

def condense_coords(matches):
    x = []
    y = []
    for m in matches:
        x += m['matches']['p'][0]
        x += m['matches']['q'][0]
        y += m['matches']['p'][1]
        y += m['matches']['q'][1]

    coords = np.transpose(np.vstack((np.array(x), np.array(y))))
    return coords

def even_distribution(coords, tile_width, tile_height):
    n = 10
    min_count = np.Inf

    for i in range(n):
        r = np.arange((i*tile_width/n), ((i+1)*tile_width/n))
        for j in range(n):
            c = np.arange((j*tile_height/n), ((j+1)*tile_height/n))
            ind = np.argwhere(
                (coords[:, 0] >= r.min()) &
                (coords[:, 0] <= r.max()) &
                (coords[:, 1] >= c.min()) &
                (coords[:, 1] <= c.max())).flatten()
            if ind.size < min_count:
                min_count = ind.size
    
    new_coords = []
    for i in range(n):
        r = np.arange((i*tile_width/n), ((i+1)*tile_width/n))
        for j in range(n):
            c = np.arange((j*tile_height/n), ((j+1)*tile_height/n))
            ind = np.argwhere(
                (coords[:, 0] >= r.min()) &
                (coords[:, 0] <= r.max()) &
                (coords[:, 1] >= c.min()) &
                (coords[:, 1] <= c.max())).flatten()
            a = np.arange(ind.size)
            np.random.shuffle(a)
            ind = ind[a[0:min_count]]
            new_coords.append(coords[ind])
    coords = np.concatenate(new_coords)
    return coords    


def create_PSLG(coords, tile_width, tile_height):
    # define a PSLG for triangle
    # http://dzhelil.info/triangle/definitions.html
    # https://www.cs.cmu.edu/~quake/triangle.defs.html#pslg
    vertices = np.array([
                    [0, 0],
                    [0, tile_height],
                    [tile_width, tile_height],
                    [tile_width, 0]])
    segments = np.array([
                    [0, 1],
                    [1, 2],
                    [2, 3],
                    [3, 0]])
    
    # check if there is a hole (focuses elements for montage sets)
    has_hole = False
    hw = 0.5 * tile_width
    hh = 0.5 * tile_height
    r = np.sqrt(
                np.power(coords[:, 0] - hw, 2.) +
                np.power(coords[:, 1] - hh, 2.0))
    if r.min() > 0.05 * 0.5 * (tile_width + tile_height):
        inbx = 50
        inby = 50
        while np.count_nonzero(
                (np.abs(coords[:, 0] - hw) < inbx) &
                (np.abs(coords[:, 1] -hh) < inby)) == 0:
            inbx += 50
        inbx -= 50
        while np.count_nonzero(
            (np.abs(coords[:, 0] - hw) < inbx) &
            (np.abs(coords[:, 1] - hh) < inby)) == 0:
            inby += 50
        inby -= 50
        vertices = np.append(vertices,
                             np.array([
                                [hw - inbx, hh - inby],
                                [hw - inbx, hh + inby],
                                [hw + inbx, hh + inby],
                                [hw + inbx, hh + inby]])).reshape(8, 2)
        segments = np.append(segments,
                             np.array([[4, 5], [5, 6], [6, 7], [7, 4]])).reshape(8, 2)
        has_hole = True
    bbox = {}
    bbox['vertices'] = vertices
    bbox['segments'] = segments
    if has_hole:
        bbox['holes'] = np.array([[hw, hh]])

    return bbox, has_hole

'''
def calculate_mesh(bbox, a, target, get_t=False):
    t = triangle.triangulate(bbox, 'pqa%0.1f' % a)
    if get_t:
        # scipy.Delaunay has nice find_simplex method,
        # but, no obvious way to iteratively refine meshes, like triangle
        # numbering is different, so, switch here
        return Delaunay(t['vertices'])
    return target - len(t['vertices'])


def find_delaunay_with_max_vertices(bbox, nvertex):
    # find bracketing values
    a1 = a2 = 1e6
    t1 = calculate_mesh(bbox, a1, nvertex)
    afac = np.power(10., -np.sign(t1))
    while(np.sign(t1) == np.sign(calculate_mesh(bbox, a2, nvertex))):
        a2 *= afac
        val_at_root = -1
        nvtweak = nvertex
        
    while val_at_root < 0:
        a = scipy.optimize.brentq(calculate_mesh,
                                    a1,
                                    a2,
                                    args=(nvtweak, ))
        val_at_root = calculate_mesh(bbox, a, nvertex)
        a1 = a * 2
        a2 = a * 0.5
        nvtweak -= 1
    mesh = calculate_mesh(bbox, a, None, get_t=True)
    area_triangle_par = a
    return mesh, area_triangle_par
'''

def count_points_near_vertices(coords, t):
    flat_tri = t.simplices.flatten()
    flat_ind = np.repeat(np.arange(t.nsimplex), 3)
    v_touches = []
    for i in range(t.npoints):
        v_touches.append(flat_ind[np.argwhere(flat_tri == i)])
    pt_count = np.zeros(t.npoints)
    found = t.find_simplex(coords, bruteforce=True)
    for i in range(t.npoints):
        for j in v_touches[i]:
            pt_count[i] += np.count_nonzero(found == j)
    return pt_count




def add_center_point():
    # may be don't need it
    return


def compute_barycentrics(mesh, coords):
    # https://en.wikipedia.org/wiki/Barycentric_coordinate_system#Conversion_between_barycentric_and_Cartesian_coordinates
    triangle_indices = mesh.find_simplex(coords)
    vt = np.vstack((
        np.transpose(mesh.points),
        np.ones(mesh.points.shape[0])))
    mt = np.vstack((np.transpose(coords), np.ones(coords.shape[0])))
    bary = np.zeros((3, coords.shape[0]))
    Rinv = []
    for tri in mesh.simplices:
        Rinv.append(np.linalg.inv(vt[:, tri]))
    for i in range(mesh.nsimplex):
        ind = np.argwhere(triangle_indices == i).flatten()
        bary[:, ind] = Rinv[i].dot(mt[:, ind])
    return np.transpose(bary), triangle_indices, Rinv


def create_x0(tilespecs, nrows, ntiles):
    x0 = []
    x0.append(np.zeros(nrows).astype('float64'))
    x0.append(np.zeros(nrows).astype('float64'))
    x0[0][0:(3*ntiles)] = np.tile([1.0, 0.0, 0.0], ntiles)
    x0[1][0:(3*ntiles)] = np.tile([0.0, 1.0, 0.0], ntiles)
    for i in range(ntiles):
        x0[0][3*i+2] = tilespecs[i].minX
        x0[1][3*i+2] = tilespecs[i].minY

    return x0


def create_A(matches, tilespecs, tile_index, mesh, unique_id_size):
    # let's assume affine_halfsize for now
    dof_per_tile = 3
    dof_per_vertex = 1
    vertex_per_patch = 3
    nnz_per_row = 2 * (dof_per_tile + vertex_per_patch * dof_per_vertex)
    nrows = sum([len(m['matches']['p'][0]) for m in matches])
    nd = nnz_per_row * nrows
    lens_dof_start = dof_per_tile * unique_id_size

    data = np.zeros(nd).astype('float64')
    indices = np.zeros(nd).astype('int64')
    indptr = np.zeros(nrows+1).astype('int64')
    indptr[1:] = np.arange(1, nrows+1)*nnz_per_row
    weights = np.ones(nrows).astype('float64')

    # nothing fancy here, row-by-row
    offset = 0
    for mi in range(len(matches)):
        m = matches[mi]
        npoint_pairs = len(m['matches']['q'][0])

        # get barycentri coordinates ready
        pcoords = np.transpose(
                    np.vstack(
                        (m['matches']['p'][0],
                         m['matches']['p'][1])
                        )).astype('float64')
        qcoords = np.transpose(
                    np.vstack(
                        (m['matches']['q'][0],
                         m['matches']['q'][1])
                        )).astype('float64')
        pbary, ts, Rinv = compute_barycentrics(mesh, pcoords)
        qbary, ts, Rinv = compute_barycentrics(mesh, qcoords)

        mstep = np.arange(npoint_pairs) * nnz_per_row + offset

        data[mstep+0] = pcoords[:, 0]
        data[mstep+1] = pcoords[:, 1]
        data[mstep+2] = 1.0
        data[mstep+3] = -qcoords[:, 0]
        data[mstep+4] = -qcoords[:, 1]
        data[mstep+5] = -1.0
        data[mstep+6] = pbary[0][:, 0]
        data[mstep+7] = pbary[0][:, 1]
        data[mstep+8] = pbary[0][:, 2]
        data[mstep+9] = -qbary[0][:, 0]
        data[mstep+10] = -qbary[0][:, 1]
        data[mstep+11] = -qbary[0][:, 2]

        indices[mstep+0] = tile_index[mi, 0]*dof_per_tile+0
        indices[mstep+1] = tile_index[mi, 0]*dof_per_tile+1
        indices[mstep+2] = tile_index[mi, 0]*dof_per_tile+2
        indices[mstep+3] = tile_index[mi, 1]*dof_per_tile+0
        indices[mstep+4] = tile_index[mi, 1]*dof_per_tile+1
        indices[mstep+5] = tile_index[mi, 1]*dof_per_tile+2
        indices[mstep+6] = (lens_dof_start +
                            mesh.simplices[pbary[1][:]][:, 0])
        indices[mstep+7] = (lens_dof_start +
                            mesh.simplices[pbary[1][:]][:, 1])
        indices[mstep+8] = (lens_dof_start +
                            mesh.simplices[pbary[1][:]][:, 2])
        indices[mstep+9] = (lens_dof_start +
                            mesh.simplices[qbary[1][:]][:, 0])
        indices[mstep+10] = (lens_dof_start +
                                mesh.simplices[qbary[1][:]][:, 1])
        indices[mstep+11] = (lens_dof_start +
                                mesh.simplices[qbary[1][:]][:, 2])
        
        offset += npoint_pairs * nnz_per_row
    
    A = csr_matrix((data, indices, indptr))
    weights = sparse.eye(weights.size, format='csr')
    weights.data = weights
    x0 = create_x0(tilespecs, A.shape[1], unique_id_size)

    return A, x0, weights, data, indices, indptr, lens_dof_start


def create_regularization(A, unique_id_size, default_lambda, translation_factor, lens_lambda):
    reg = np.ones(A.shape[1]).astype('float64') * default_lambda
    reg[0:unique_id_size*3][2::3] *= translation_factor
    reg[unique_id_size*3:] *= lens_lambda
    reg1 = sparse.eye(reg.size, format='csr')
    reg1.data = reg

    return reg1


def solve(A, x0, weights, unique_ids, default_lambda, translation_factor, lens_lambda):
    reg = create_regularization(A, unique_ids.size, default_lambda, translation_factor, lens_lambda)
    ATW = A.transpose().dot(weights)
    K = ATW.dot(A) + reg
    K_factorized = factorized(K)
    solution = []

    for x in x0:
        Lm = reg.dot(x0)
        solution.append(K_factorized(Lm))

    errx = A.dot(solution[0])
    erry = A.dot(solution[1])

    transforms = []
    for i in range(len(unique_ids)):
        transforms.append(renderapi.transform.AffineModel(M00=solution[0][i*3+0],
                                                          M01=solution[0][i*3+1],
                                                          B0=solution[0][i*3+2],
                                                          M10=solution[1][i*3+0],
                                                          M11=solution[1][i*3+1],
                                                          B1=solution[1][i*3+2]))
    return solution, transforms


def create_thinplatespline_tf(solution, mesh, lens_dof_start, outfile=None):
    if outfile is None:
        out = tempfile.NamedTemporaryFile(suffix=".json", delete=False, dir=outdir)
        out.close()
        outfile = out.name
    
    cmd = 'java -cp $RENDER_CLIENT_JAR '
    cmd += 'org.janelia.render.client.ThinPlateSplineClient '
    cmd += '--computeAffine false '
    cmd += '--numberOfDimensions 2 '
    cmd += '--outputFile %s ' % outfile
    cmd += '--numberOfLandmarks %d ' % mesh.points.shape[0]
  
    for i in range(mesh.points.shape[0]):
        cmd += '%0.6f ' % mesh.points[i, 0]
        cmd += '%0.6f ' % mesh.points[i, 1]
    
    for i in range(mesh.points.shape[0]):
        cmd += '%0.6f ' % (mesh.points[i, 0] + solution[0][lens_dof_start + i])
        cmd += '%0.6f ' % (mesh.points[i, 1] + solution[1][lens_dof_start + i])
    
    subprocess.check_call(cmd, shell=True)

    j = json.load(open(outfile, 'r'))
    tf_thinplate = (renderapi.transform.ThinPlateSplineTransform(dataString=j['dataString']))
    return outfile, tf_thinplate


def new_stack_with_tf(render, output_stack, tilespecs, sectionId, solution, tf_thinplate, tfchoice='thinplate'):
    # change this to take tf_poly or tf_thinplate based on tfchoice
    tf = tf_thinplate

    renderapi.stack.create_stack(output_stack, render=render)
    refId = (sectionId + datetime.datetime.now().strftime("_%Y%m%d%H%M%S"))
    
    tf.transformId = refId
    tf.labels = None

    newspecs = []
    for i in range(len(tilespecs)):
        newspecs.append(copy.deepcopy(tilespecs[i]))
        newspecs[-1].tforms.insert(0, renderapi.transform.ReferenceTransform(refId=refId))    
        newspecs[-1].tforms[1].M00 = solution[0][i*3+0]
        newspecs[-1].tforms[1].M01 = solution[0][i*3+1]
        newspecs[-1].tforms[1].B0 = solution[0][i*3+2]
        newspecs[-1].tforms[1].M10 = solution[1][i*3+0]
        newspecs[-1].tforms[1].M11 = solution[1][i*3+1]
        newspecs[-1].tforms[1].B1 = solution[1][i*3+2]
        newspecs[-1].tforms[1].load_M()

    renderapi.client.import_tilespecs(output_stack,
                                      newspecs,
                                      sharedTransforms=[tf],
                                      render=render)
    renderapi.stack.set_stack_state(output_stack,
                                    'COMPLETE',
                                    render=render)



class MeshAndSolveClass:
    def calculate_mesh(self, a, target, get_t=False):
        t = triangle.triangulate(self.bbox, 'pqa%0.1f' % a)
        if get_t:
            # scipy.Delaunay has nice find_simplex method,
            # but, no obvious way to iteratively refine meshes, like triangle
            # numbering is different, so, switch here
            return Delaunay(t['vertices'])
        return target - len(t['vertices'])


    def find_delaunay_with_max_vertices(self, nvertex):
        # find bracketing values
        a1 = a2 = 1e6
        t1 = self.calculate_mesh(a1, nvertex)
        afac = np.power(10., -np.sign(t1))
        while(np.sign(t1) == np.sign(self.calculate_mesh(a2, nvertex))):
            a2 *= afac
            val_at_root = -1
            nvtweak = nvertex
            
        while val_at_root < 0:
            a = scipy.optimize.brentq(self.calculate_mesh,
                                        a1,
                                        a2,
                                        args=(nvtweak, ))
            val_at_root = self.calculate_mesh(a, nvertex)
            a1 = a * 2
            a2 = a * 0.5
            nvtweak -= 1
        mesh = self.calculate_mesh(a, None, get_t=True)
        area_triangle_par = a
        return mesh, area_triangle_par

    def force_vertices_with_npoints(self, coords, area_triangle_par, npts):
        fac = 10.05
        count = 0
        while True:
            t = self.calculate_mesh(area_triangle_par,
                                    None,
                                    get_t=True)
            pt_count = count_points_near_vertices(coords, t)
            if pt_count.min() >= npts:
                break
            area_triangle_par *= fac
            count += 1
            if np.mod(count, 2) == 0:
                fac += 0.5
            if np.mod(count, 20) == 0:
                print('Did not meet vertex requirement after 1000 iterations')
                break 
        mesh = t
        return mesh, area_triangle_par


    def MeshAndSolve(self, render, input_stack, output_stack, match_collection, sectionId, nvertex, outfile, default_lambda, translation_factor, lens_lambda):
        # load the matches
        matches, unique_ids, tile_index = load_matches(render, match_collection, sectionId)

        # load tilespecs
        tilespecs, tile_width, tile_height = load_tilespecs(render, input_stack, unique_ids)

        # condense coordinates and evenly distribute
        coords = condense_coords(matches)
        coords = even_distribution(coords, tile_width, tile_height)

        # create PSLG
        bbox, has_hole = create_PSLG(coords, tile_width, tile_height)
        self.bbox = bbox

        # find Delaunay with max vertices
        mesh, area_triangle_par = self.find_delaunay_with_max_vertices(nvertex)

        # force vertices with n points
        mesh, area_triangle_par = self.force_vertices_with_npoints(coords, area_triangle_par, 3)

        if has_hole:
            add_center_point()
        
        # create A matrix
        print('Returned %d vertices' % mesh.npoints)
        print('Creating A...')
        A, x0, weights, data, indices, indptr, lens_dof_start = create_A(matches, tilespecs, tile_index, mesh, unique_ids.size)

        print('Solving')
        solution, transforms = solve(A, x0, weights, unique_ids, default_lambda, translation_factor, lens_lambda)

        # Create ThinPlateSpline dataString
        outfile, tf_thinplate = create_thinplatespline_tf(solution, mesh, lens_dof_start, outfile)

        # create the output stack
        new_stack_with_tf(render, output_stack, tilespecs, sectionId, solution, tf_thinplate, tfchoice='thinplate')

        return outfile