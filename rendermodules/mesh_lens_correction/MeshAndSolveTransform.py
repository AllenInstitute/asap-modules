
import numpy as np
import triangle
import scipy.optimize
from scipy.spatial import Delaunay
import scipy.sparse as sparse
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import factorized
import renderapi
import copy
import os
import json
import datetime
import cv2
from six.moves import urllib
from argschema import ArgSchemaParser
from .schemas \
        import MeshLensCorrectionSchema, MeshAndSolveOutputSchema
from ..module.render_module import RenderModuleException


class MeshLensCorrectionException(RenderModuleException):
    """Exception raised when there is a \
            problem creating a mesh lens correction"""
    pass


def get_tspecs_and_matches(render, collection, stack, z, sectionId):
    # load the specs and matches
    tspecs = np.array(
            renderapi.tilespec.get_tile_specs_from_z(
                stack,
                z,
                render=render))
    stack_ids = np.array([t.tileId for t in tspecs])

    matches = renderapi.pointmatch.get_matches_within_group(
            collection,
            sectionId,
            render=render)
    match_ids = np.array(
                [[m['pId'], m['qId']] for m in matches]).flatten()

    unique_ids = np.intersect1d(stack_ids, match_ids)
    if unique_ids.size == 0:
        raise MeshLensCorrectionException(
                "no tileId overlap between stack %s and collection %s" %
                (stack, collection))

    utspecs = []
    for uid in unique_ids:
        ind = np.argwhere(stack_ids == uid).flatten()[0]
        utspecs.append(tspecs[ind])

    umatches = []
    for m in matches:
        if (m['pId'] in unique_ids) & (m['qId'] in unique_ids):
            umatches.append(m)

    return utspecs, umatches


def condense_coords(matches):
    # condense point match structure into Nx2
    x = []
    y = []
    for m in matches:
        x += m['matches']['p'][0]
        x += m['matches']['q'][0]
        y += m['matches']['p'][1]
        y += m['matches']['q'][1]
    coords = np.transpose(np.vstack((np.array(x), np.array(y))))
    return coords


def even_distribution(coords, tile_width, tile_height, n):
    # n: area divided into nxn
    min_count = np.Inf
    for i in range(n):
        r = np.arange(
                (i*tile_width/n),
                ((i+1)*tile_width/n))
        for j in range(n):
            c = np.arange(
                    (j*tile_height/n),
                    ((j+1)*tile_height/n))
            ind = np.argwhere(
                    (coords[:, 0] >= r.min()) &
                    (coords[:, 0] <= r.max()) &
                    (coords[:, 1] >= c.min()) &
                    (coords[:, 1] <= c.max())).flatten()
            if ind.size < min_count:
                min_count = ind.size
    new_coords = []
    for i in range(n):
        r = np.arange(
                (i*tile_width/n),
                ((i+1)*tile_width/n))
        for j in range(n):
            c = np.arange(
                    (j*tile_height/n),
                    ((j+1)*tile_height/n))
            ind = np.argwhere(
                    (coords[:, 0] >= r.min()) &
                    (coords[:, 0] <= r.max()) &
                    (coords[:, 1] >= c.min()) &
                    (coords[:, 1] <= c.max())).flatten()
            a = np.arange(ind.size)
            np.random.shuffle(a)
            ind = ind[a[0:min_count]]
            new_coords.append(coords[ind])
    return np.concatenate(new_coords)


def create_montage_qc_dict(args, tilespecs):
    j = {}
    j['prestitched_stack'] = args['input_stack']
    j['poststitched_stack'] = args['output_stack']
    j['match_collection'] = args['match_collection']
    j['out_html_dir'] = args['output_dir']
    j['output_json'] = os.path.join(
            args['output_dir'],
            args['sectionId']+'_output.json')
    j['plot_sections'] = "True"
    j['pool_size'] = 40
    j['minZ'] = int(tilespecs[0].z)
    j['maxZ'] = int(tilespecs[0].z)
    qcname = os.path.join(
            args['output_dir'],
            args['sectionId'] + "_input.json")
    return qcname, j


def approx_snap_contour(contour, width, height, epsilon=20, snap_dist=5):
    # approximate contour within epsilon pixels,
    # so it isn't too fine in the corner
    # and snap to edges
    approx = cv2.approxPolyDP(contour, epsilon, True)
    for i in range(approx.shape[0]):
        for j in [0, width]:
            if np.abs(approx[i, 0, 0] - j) <= snap_dist:
                approx[i, 0, 0] = j
        for j in [0, height]:
            if np.abs(approx[i, 0, 1] - j) <= snap_dist:
                approx[i, 0, 1] = j
    return approx


def create_PSLG(tile_width, tile_height, maskUrl):
    # define a PSLG for triangle
    # http://dzhelil.info/triangle/definitions.html
    # https://www.cs.cmu.edu/~quake/triangle.defs.html#pslg
    if maskUrl is None:
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
    else:
        mpath = urllib.parse.unquote(
                    urllib.parse.urlparse(maskUrl).path)
        im = cv2.imread(mpath, 0)
        im2, contours, h = cv2.findContours(
                im, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        approx = approx_snap_contour(contours[0], tile_width, tile_height)
        vertices = np.array(approx).squeeze()
        segments = np.zeros((vertices.shape[0], 2))
        segments[:, 0] = np.arange(vertices.shape[0])
        segments[:, 1] = segments[:, 0] + 1
        segments[-1, 1] = 0
    bbox = {}
    bbox['vertices'] = vertices
    bbox['segments'] = segments

    return bbox


def calculate_mesh(a, bbox, target, get_t=False):
    t = triangle.triangulate(bbox, 'pqa%0.1f' % a)
    if get_t:
        # scipy.Delaunay has nice find_simplex method,
        # but, no obvious way to iteratively refine meshes, like triangle
        # numbering is different, so, switch here
        return Delaunay(t['vertices'])
    return target - len(t['vertices'])


def force_vertices_with_npoints(area_par, bbox, coords, npts):
    fac = 1.02
    count = 0
    max_iter = 20
    while True:
        t = calculate_mesh(
                area_par,
                bbox,
                None,
                get_t=True)
        pt_count = count_points_near_vertices(t, coords)
        print(pt_count.min(), area_par, t.npoints)
        if pt_count.min() >= npts:
            break
        area_par *= fac
        count += 1
        if np.mod(count, 2) == 0:
            fac += 0.5
        if np.mod(count, max_iter) == 0:
            e = ("did not meet vertex requirement "
                 "after %d iterations" % max_iter)
            raise MeshLensCorrectionException(e)
    return t, area_par


def find_delaunay_with_max_vertices(bbox, nvertex):
    # find bracketing values
    a1 = a2 = 1e6
    t1 = calculate_mesh(a1, bbox, nvertex)
    afac = np.power(10., -np.sign(t1))
    while (
            np.sign(t1) ==
            np.sign(calculate_mesh(a2, bbox, nvertex))
          ):
        a2 *= afac
    val_at_root = -1
    nvtweak = nvertex
    while val_at_root < 0:
        a = scipy.optimize.brentq(
                calculate_mesh,
                a1,
                a2,
                args=(bbox, nvtweak, ))
        val_at_root = calculate_mesh(a, bbox, nvertex)
        a1 = a * 2
        a2 = a * 0.5
        nvtweak -= 1
    mesh = calculate_mesh(a, bbox, None, get_t=True)
    return mesh, a


def compute_barycentrics(coords, mesh):
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
    return np.transpose(bary), triangle_indices


def count_points_near_vertices(t, coords):
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


def create_regularization(ncols, ntiles, defaultL, transL, lensL):
    # regularizations: [affine matrix, translation, lens]
    reg = np.ones(ncols).astype('float64') * defaultL
    reg[0:ntiles*3][2::3] *= transL
    reg[ntiles*3:] *= lensL
    rmat = sparse.eye(reg.size, format='csr')
    rmat.data = reg
    return rmat


def create_thinplatespline_tf(
        render, args, mesh, solution,
        lens_dof_start, common_transform,
        compute_affine=True):

    dst = np.zeros_like(mesh.points)
    dst[:, 0] = mesh.points[:, 0] + solution[0][lens_dof_start:]
    dst[:, 1] = mesh.points[:, 1] + solution[1][lens_dof_start:]

    if common_transform is not None:
        # average affine result
        dst = common_transform.tform(dst)

    transform = renderapi.transform.ThinPlateSplineTransform()
    transform.estimate(mesh.points, dst, computeAffine=compute_affine)
    transform.transformId = (
            args['sectionId'] +
            datetime.datetime.now().strftime("_%Y%m%d%H%M%S"))
    transform.labels = None
    if args['transform_label'] is not None:
        transform.labels = [args['transform_label']]

    with open(args['outfile'], 'w') as f:
        json.dump(transform.to_dict(), f, indent=2)

    return transform


def new_stack_with_tf(
        render, stack,
        ref_transform, tilespecs,
        transforms, close_stack):

    renderapi.stack.create_stack(stack, render=render)

    newspecs = []
    for i in range(len(tilespecs)):
        newspecs.append(copy.deepcopy(tilespecs[i]))
        newspecs[-1].tforms.insert(0,
                                   renderapi.transform.ReferenceTransform(
                                    refId=ref_transform.transformId))
        newspecs[-1].tforms[1] = transforms[i]

    renderapi.client.import_tilespecs(
            stack,
            newspecs,
            sharedTransforms=[ref_transform],
            render=render)
    if close_stack:
        renderapi.stack.set_stack_state(
                stack,
                'COMPLETE',
                render=render)


def solve(A, weights, reg, x0):
    ATW = A.transpose().dot(weights)
    K = ATW.dot(A) + reg
    K_factorized = factorized(K)
    solution = []
    for x in x0:
        Lm = reg.dot(x)
        solution.append(K_factorized(Lm))

    errx = A.dot(solution[0])
    erry = A.dot(solution[1])

    return solution, errx, erry


def report_solution(errx, erry, transforms, criteria):
    message = '\n'
    for e, v in [[errx, 'dx'], [erry, 'dy']]:
        message += (
              ' %s: [%8.2f,%8.2f] %8.2f +/-%8.2f pixels\n' %
              (v, e.min(), e.max(), e.mean(), e.std()))
    message += 'dx/dy criteria [ < %0.3f ] +/- [ < %0.3f ]]\n' % \
        (criteria['error_mean'], criteria['error_std'])

    scale = np.array([tf.scale for tf in transforms])
    message += ('xscale: [%8.2f,%8.2f] %8.2f +/-%8.2f\n' %
                (scale[:, 0].min(), scale[:, 0].max(),
                 scale[:, 0].mean(), scale[:, 0].std()))
    message += ('yscale: [%8.2f,%8.2f] %8.2f +/-%8.2f\n' %
                (scale[:, 1].min(), scale[:, 1].max(),
                 scale[:, 1].mean(), scale[:, 1].std()))
    message += 'scale criteria [ < %0.3f ] +/- [ no criteria ]' % \
        (criteria['scale_dev'])
    return scale, message


def create_x0(nrows, tilespecs):
    ntiles = len(tilespecs)
    x0 = []
    x0.append(np.zeros(nrows).astype('float64'))
    x0.append(np.zeros(nrows).astype('float64'))
    x0[0][0:(3*ntiles)] = np.tile([1.0, 0.0, 0.0], ntiles)
    x0[1][0:(3*ntiles)] = np.tile([0.0, 1.0, 0.0], ntiles)
    for i in range(ntiles):
        x0[0][3*i+2] = tilespecs[i].minX
        x0[1][3*i+2] = tilespecs[i].minY
    return x0


def create_A(matches, tilespecs, mesh):
    # let's assume affine_halfsize
    dof_per_tile = 3
    dof_per_vertex = 1
    vertex_per_patch = 3
    nnz_per_row = 2*(dof_per_tile + vertex_per_patch * dof_per_vertex)
    nrows = sum([len(m['matches']['p'][0]) for m in matches])
    nd = nnz_per_row*nrows
    lens_dof_start = dof_per_tile*len(tilespecs)

    data = np.zeros(nd).astype('float64')
    indices = np.zeros(nd).astype('int64')
    indptr = np.zeros(nrows+1).astype('int64')
    indptr[1:] = np.arange(1, nrows+1)*nnz_per_row
    weights = np.ones(nrows).astype('float64')

    unique_ids = np.array(
            [t.tileId for t in tilespecs])

    # nothing fancy here, row-by-row
    offset = 0
    for mi in range(len(matches)):
        m = matches[mi]
        pindex = np.argwhere(unique_ids == m['pId'])
        qindex = np.argwhere(unique_ids == m['qId'])

        npoint_pairs = len(m['matches']['q'][0])
        # get barycentric coordinates ready
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
        pbary = compute_barycentrics(pcoords, mesh)
        qbary = compute_barycentrics(qcoords, mesh)

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

        indices[mstep+0] = pindex*dof_per_tile+0
        indices[mstep+1] = pindex*dof_per_tile+1
        indices[mstep+2] = pindex*dof_per_tile+2
        indices[mstep+3] = qindex*dof_per_tile+0
        indices[mstep+4] = qindex*dof_per_tile+1
        indices[mstep+5] = qindex*dof_per_tile+2
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

        offset += npoint_pairs*nnz_per_row

    A = csr_matrix((data, indices, indptr))
    wts = sparse.eye(weights.size, format='csr')
    wts.data = weights
    return A, wts, lens_dof_start


def create_transforms(ntiles, solution, get_common=True):
    rtransforms = []
    for i in range(ntiles):
        rtransforms.append(renderapi.transform.AffineModel(
                           M00=solution[0][i*3+0],
                           M01=solution[0][i*3+1],
                           B0=solution[0][i*3+2],
                           M10=solution[1][i*3+0],
                           M11=solution[1][i*3+1],
                           B1=solution[1][i*3+2]))

    if get_common:
        transforms = []
        # average without translations
        common = np.array([t.M for t in rtransforms]).mean(0)
        common[0, 2] = 0.0
        common[1, 2] = 0.0
        for r in rtransforms:
            transforms.append(renderapi.transform.AffineModel())
            transforms[-1].M = r.M.dot(np.linalg.inv(common))
        ctform = renderapi.transform.AffineModel()
        ctform.M = common
    else:
        ctform = None
        transforms = rtransforms

    return ctform, transforms


class MeshAndSolveTransform(ArgSchemaParser):
    default_schema = MeshLensCorrectionSchema
    default_output_schema = MeshAndSolveOutputSchema

    def run(self):
        self.render = renderapi.connect(**self.args['render'])

        self.tilespecs, self.matches = get_tspecs_and_matches(
            self.render,
            self.args['match_collection'],
            self.args['input_stack'],
            self.args['z_index'],
            self.args['sectionId'])

        self.tile_width = self.tilespecs[0].width
        self.tile_height = self.tilespecs[0].height
        maskUrl = self.tilespecs[0].ip[0].maskUrl

        # condense coordinates
        self.coords = condense_coords(self.matches)
        self.coords = even_distribution(
            self.coords,
            self.tile_width,
            self.tile_height,
            10)

        if self.coords.shape[0] == 0:
            raise MeshLensCorrectionException(
                    "no point matches left after evening distribution, \
                     probably some sparse areas of matching")

        # create PSLG
        self.bbox = create_PSLG(
                self.tile_width,
                self.tile_height,
                maskUrl)

        # find delaunay with max vertices
        self.mesh, self.area_triangle_par = \
            find_delaunay_with_max_vertices(
                self.bbox,
                self.args['nvertex'])

        # and enforce neighboring matches to vertices
        self.mesh, self.area_triangle_par = \
            force_vertices_with_npoints(
                self.area_triangle_par,
                self.bbox,
                self.coords,
                3)

        if self.mesh.points.shape[0] < 0.5*self.args['nvertex']:
            raise MeshLensCorrectionException(
                    "mesh coarser than intended")

        # prepare the linear algebra and solve
        self.A, self.weights, self.lens_dof_start = \
            create_A(
                self.matches,
                self.tilespecs,
                self.mesh)
        self.x0 = create_x0(
                self.A.shape[1],
                self.tilespecs)
        self.reg = create_regularization(
                self.A.shape[1],
                len(self.tilespecs),
                self.args['regularization']['default_lambda'],
                self.args['regularization']['translation_factor'],
                self.args['regularization']['lens_lambda'])
        self.solution, self.errx, self.erry = solve(
                self.A,
                self.weights,
                self.reg,
                self.x0)

        self.common_transform, self.transforms = create_transforms(
                len(self.tilespecs), self.solution)

        tf_scale, message = report_solution(
                self.errx,
                self.erry,
                self.transforms,
                self.args['good_solve'])

        # check quality of solution
        if not all([
                    self.errx.mean() <
                    self.args['good_solve']['error_mean'],

                    self.erry.mean() <
                    self.args['good_solve']['error_mean'],

                    self.errx.std() <
                    self.args['good_solve']['error_std'],

                    self.erry.std() <
                    self.args['good_solve']['error_std'],

                    np.abs(tf_scale[:, 0].mean() - 1.0) <
                    self.args['good_solve']['scale_dev'],

                    np.abs(tf_scale[:, 1].mean() - 1.0) <
                    self.args['good_solve']['scale_dev']]):

            raise MeshLensCorrectionException(
                    "Solve not good: %s" % message)

        self.logger.debug(message)

        self.new_ref_transform = create_thinplatespline_tf(
                self.render,
                self.args,
                self.mesh,
                self.solution,
                self.lens_dof_start,
                self.common_transform)

        new_stack_with_tf(
                self.render,
                self.args['output_stack'],
                self.new_ref_transform,
                self.tilespecs,
                self.transforms,
                self.args['close_stack'])

        self.qc_path, self.qc_dict = create_montage_qc_dict(
                self.args,
                self.tilespecs)

        try:
            self.output(
                {'output_json': self.args['outfile']})
        except AttributeError as e:
            self.logger.error(e)

        with open(self.qc_path, 'w') as f:
            json.dump(self.qc_dict, f)

        return
