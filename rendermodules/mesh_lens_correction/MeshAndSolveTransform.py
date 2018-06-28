
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
import subprocess
import json
import datetime


class MeshAndSolveTransform:
    def load_matches(self):
        render = self.args['render']
        self.matches = \
            renderapi.pointmatch.get_matches_within_group(
                    self.args['match_collection'],
                    self.args['sectionId'],
                    render=render)
        self.tile_ids = np.array([[m['pId'], m['qId']] for m in self.matches])
        self.unique_ids = np.unique(self.tile_ids.flatten())
        # determine tile index per tile pair
        self.tile_index = np.zeros((
            self.tile_ids.shape[0],
            self.tile_ids.shape[1])).astype('int')
        for i in range(self.tile_ids.shape[0]):
            for j in range(self.tile_ids.shape[1]):
                self.tile_index[i, j] = np.argwhere(
                        self.unique_ids == self.tile_ids[i, j])

    def load_tilespecs(self):
        render = self.args['render']
        self.tilespecs = []
        for tid in self.unique_ids:
            # order is important
            self.tilespecs.append(
                    renderapi.tilespec.get_tile_spec_raw(
                        self.args['input_stack'],
                        tid,
                        render=render))
        self.tile_width = self.tilespecs[0].width
        self.tile_height = self.tilespecs[0].height

    def condense_coords(self):
        # condense point match structure into Nx2
        x = []
        y = []
        for m in self.matches:
            x += m['matches']['p'][0]
            x += m['matches']['q'][0]
            y += m['matches']['p'][1]
            y += m['matches']['q'][1]
        self.coords = np.transpose(np.vstack((np.array(x), np.array(y))))
        self.even_distribution()

    def even_distribution(self):
        n = 10
        min_count = np.Inf
        for i in range(n):
            r = np.arange(
                    (i*self.tile_width/n),
                    ((i+1)*self.tile_width/n))
            for j in range(n):
                c = np.arange(
                        (j*self.tile_height/n),
                        ((j+1)*self.tile_height/n))
                ind = np.argwhere(
                        (self.coords[:, 0] >= r.min()) &
                        (self.coords[:, 0] <= r.max()) &
                        (self.coords[:, 1] >= c.min()) &
                        (self.coords[:, 1] <= c.max())).flatten()
                if ind.size < min_count:
                    min_count = ind.size
        self.new_coords = []
        for i in range(n):
            r = np.arange(
                    (i*self.tile_width/n),
                    ((i+1)*self.tile_width/n))
            for j in range(n):
                c = np.arange(
                        (j*self.tile_height/n),
                        ((j+1)*self.tile_height/n))
                ind = np.argwhere(
                        (self.coords[:, 0] >= r.min()) &
                        (self.coords[:, 0] <= r.max()) &
                        (self.coords[:, 1] >= c.min()) &
                        (self.coords[:, 1] <= c.max())).flatten()
                a = np.arange(ind.size)
                np.random.shuffle(a)
                ind = ind[a[0:min_count]]
                self.new_coords.append(self.coords[ind])
        self.coords = np.concatenate(self.new_coords)

    def write_montage_qc_json(self):
        j = {}
        #j['render'] = self.args['render']
        j['prestitched_stack'] = self.args['input_stack']
        j['poststitched_stack'] = self.args['output_stack']
        j['match_collection'] = self.args['match_collection']
        j['out_html_dir'] = self.args['out_html_dir']
        j['output_json'] = os.path.join(
                self.args['out_html_dir'],
                self.args['sectionId']+'_output.json')
        j['plot_sections'] = "True"
        j['pool_size'] = 40
        j['minZ'] = int(self.tilespecs[0].z)
        j['maxZ'] = int(self.tilespecs[0].z)
        qcname = os.path.join(
                self.args['out_html_dir'],
                self.args['sectionId'] + "_input.json")
        json.dump(j, open(qcname, 'w'), indent=2)

    def add_center_point(self):
        # maybe don't need it
        return

    def create_PSLG(self):
        # define a PSLG for triangle
        # http://dzhelil.info/triangle/definitions.html
        # https://www.cs.cmu.edu/~quake/triangle.defs.html#pslg
        vertices = np.array([
                [0, 0],
                [0, self.tile_height],
                [self.tile_width, self.tile_height],
                [self.tile_width, 0]])
        segments = np.array([
                [0, 1],
                [1, 2],
                [2, 3],
                [3, 0]])
        # check if there is a hole (focuses elements for montage sets)
        self.has_hole = False
        hw = 0.5 * self.tile_width
        hh = 0.5 * self.tile_height
        r = np.sqrt(
                np.power(self.coords[:, 0] - hw, 2.0) +
                np.power(self.coords[:, 1] - hh, 2.0))
        if r.min() > 0.05 * 0.5 * (self.tile_width + self.tile_height):
            inbx = 50
            inby = 50
            while np.count_nonzero(
                    (np.abs(self.coords[:, 0] - hw) < inbx) &
                    (np.abs(self.coords[:, 1] - hh) < inby)
                                  ) == 0:
                inbx += 50
            inbx -= 50
            while np.count_nonzero(
                    (np.abs(self.coords[:, 0]-hw) < inbx) &
                    (np.abs(self.coords[:, 1]-hh) < inby)
                                   ) == 0:
                inby += 50
            inby -= 50
            vertices = np.append(
                        vertices,
                        np.array([
                            [hw - inbx, hh - inby],
                            [hw - inbx, hh + inby],
                            [hw + inbx, hh + inby],
                            [hw + inbx, hh - inby]])
                                ).reshape(8, 2)
            segments = np.append(
                        segments,
                        np.array([
                                  [4, 5],
                                  [5, 6],
                                  [6, 7],
                                  [7, 4]])
                                ).reshape(8, 2)
            self.has_hole = True
        self.bbox = {}
        self.bbox['vertices'] = vertices
        self.bbox['segments'] = segments
        if self.has_hole:
            self.bbox['holes'] = np.array([[hw, hh]])

    def calculate_mesh(self, a, target, get_t=False):
        t = triangle.triangulate(self.bbox, 'pqa%0.1f' % a)
        if get_t:
            # scipy.Delaunay has nice find_simplex method,
            # but, no obvious way to iteratively refine meshes, like triangle
            # numbering is different, so, switch here
            return Delaunay(t['vertices'])
        return target - len(t['vertices'])

    def force_vertices_with_npoints(self, npts):
        fac = 1.05
        count = 0
        while True:
            t = self.calculate_mesh(
                    self.area_triangle_par,
                    None,
                    get_t=True)
            pt_count = self.count_points_near_vertices(t)
            if pt_count.min() >= npts:
                break
            self.area_triangle_par *= fac
            count += 1
            if np.mod(count, 2) == 0:
                fac += 0.5
            if np.mod(count, 20) == 0:
                print('did not meet vertex requirement after 1000 iterations')
                break
        self.mesh = t
        return

    def find_delaunay_with_max_vertices(self):
        # find bracketing values
        a1 = a2 = 1e6
        t1 = self.calculate_mesh(a1, self.args['nvertex'])
        afac = np.power(10., -np.sign(t1))
        while (
                np.sign(t1) ==
                np.sign(self.calculate_mesh(a2, self.args['nvertex']))
              ):
            a2 *= afac
        val_at_root = -1
        nvtweak = self.args['nvertex']
        while val_at_root < 0:
            a = scipy.optimize.brentq(
                    self.calculate_mesh,
                    a1,
                    a2,
                    args=(nvtweak, ))
            val_at_root = self.calculate_mesh(a, self.args['nvertex'])
            a1 = a * 2
            a2 = a * 0.5
            nvtweak -= 1
        self.mesh = self.calculate_mesh(a, None, get_t=True)
        self.area_triangle_par = a
        return

    def compute_barycentrics(self, coords):
        # https://en.wikipedia.org/wiki/Barycentric_coordinate_system#Conversion_between_barycentric_and_Cartesian_coordinates
        triangle_indices = self.mesh.find_simplex(coords)
        vt = np.vstack((
            np.transpose(self.mesh.points),
            np.ones(self.mesh.points.shape[0])))
        mt = np.vstack((np.transpose(coords), np.ones(coords.shape[0])))
        bary = np.zeros((3, coords.shape[0]))
        self.Rinv = []
        for tri in self.mesh.simplices:
            self.Rinv.append(np.linalg.inv(vt[:, tri]))
        for i in range(self.mesh.nsimplex):
            ind = np.argwhere(triangle_indices == i).flatten()
            bary[:, ind] = self.Rinv[i].dot(mt[:, ind])
        return np.transpose(bary), triangle_indices

    def count_points_near_vertices(self, t):
        flat_tri = t.simplices.flatten()
        flat_ind = np.repeat(np.arange(t.nsimplex), 3)
        v_touches = []
        for i in range(t.npoints):
            v_touches.append(flat_ind[np.argwhere(flat_tri == i)])
        pt_count = np.zeros(t.npoints)
        found = t.find_simplex(self.coords, bruteforce=True)
        for i in range(t.npoints):
            for j in v_touches[i]:
                pt_count[i] += np.count_nonzero(found == j)
        return pt_count

    def create_regularization(self):
        # regularizations: [affine matrix, translation, lens]
        reg = np.ones(self.A.shape[1]).astype('float64') * (
          self.args['regularization']['default_lambda'])
        reg[0:self.unique_ids.size*3][2::3] *= (
          self.args['regularization']['translation_factor'])
        reg[self.unique_ids.size*3:] *= (
          self.args['regularization']['lens_lambda'])
        self.reg = sparse.eye(reg.size, format='csr')
        self.reg.data = reg
    '''
    def report_solution(self, pre='', x=None):
        def message(err, pre):
            m = pre + ':\n'
            for e, v in [[err[0], 'dx'], [err[1], 'dy']]:
                m += (
                      ' %s: [%8.2f,%8.2f] %8.2f+/-%8.2f pixels\n' %
                      (v, e.min(), e.max(), e.mean(), e.std()))
            return m
        err = []
        if x is None:
            x = self.solution
        for x0 in x:
            err.append(self.A.dot(x0))
        m = message(err, pre)
        if x is not None:
            scale = np.array([tf.scale for tf in self.transforms])
            m += ('xscale: [%8.2f,%8.2f] %8.2f+/-%8.2f\n' %
                  (scale[:, 0].min(), scale[:, 0].max(),
                   scale[:, 0].mean(), scale[:, 0].std()))
            m += ('yscale: [%8.2f,%8.2f] %8.2f+/-%8.2f\n' %
                  (scale[:, 1].min(), scale[:, 1].max(),
                   scale[:, 1].mean(), scale[:, 1].std()))
        print(m)

    def transform_pq(self):
        p = []
        q = []
        p_transf = []
        q_transf = []
        for mi in range(len(self.matches)):
            ip = np.transpose(
                  np.array(self.matches[mi]['matches']['p']))
            iq = np.transpose(
                  np.array(self.matches[mi]['matches']['q']))
            ip_transf = self.transforms[self.tile_index[mi, 0]].tform(ip)
            iq_transf = self.transforms[self.tile_index[mi, 1]].tform(iq)
            p.append(ip)
            q.append(iq)
            p_transf.append(ip_transf)
            q_transf.append(iq_transf)
        return [p, q, p_transf, q_transf]

    def compare_solutions(self):
        self.report_solution(pre='stage only', x=self.x0)

        # try without lens correction
        tmp = self.args['regularization']['lens_lambda']
        self.args['regularization']['lens_lambda'] = 1e10
        self.solve()
        self.report_solution(pre='affine only')

        # try with lens correction
        self.args['regularization']['lens_lambda'] = tmp
        self.solve()
        self.report_solution(pre='with lens correction')
    '''
    def estimate_polynomial(self, nx=500, ny=500, ndim=5):
        [xp, yp, idx, idy] = self.interpolate(nx=nx, ny=ny, flatten=True)
        src = np.transpose(np.vstack((xp, yp)))
        dst = np.transpose(np.vstack((xp+idx, yp+idy)))
        self.tf_poly = renderapi.transform.NonLinearCoordinateTransform()
        self.tf_poly.width = self.tile_width
        self.tf_poly.height = self.tile_height
        self.tf_poly.dimension = ndim
        self.tf_poly.length = (ndim+1)*(ndim+2)/2
        self.tf_poly.estimate(src, dst)
        dst_poly = self.tf_poly.tform(src)
        dxp = dst[:, 0].reshape(nx, ny)
        dyp = dst[:, 1].reshape(nx, ny)
        pxp = dst_poly[:, 0].reshape(nx, ny)
        pyp = dst_poly[:, 1].reshape(nx, ny)
        return [[xp.reshape(nx, ny), yp.reshape(nx, ny)],
                [dxp, dyp],
                [pxp, pyp]]

    def create_thinplatespline_tf(self):
        if self.args['outfile'] is None:
            fname = '%s/%s.json' % (
                    self.args['output_dir'],
                    self.args['sectionId'])
        else:
            fname = self.args['outfile']

        cmd = 'java -cp $RENDER_CLIENT_JAR '
        cmd += 'org.janelia.render.client.ThinPlateSplineClient '
        cmd += '--computeAffine false '
        cmd += '--numberOfDimensions 2 '
        cmd += '--outputFile %s ' % fname
        cmd += '--numberOfLandmarks %d ' % self.mesh.points.shape[0]
        for i in range(self.mesh.points.shape[0]):
            cmd += '%0.6f ' % self.mesh.points[i, 0]
            cmd += '%0.6f ' % self.mesh.points[i, 1]
        for i in range(self.mesh.points.shape[0]):
            cmd += '%0.6f ' % (
                    self.mesh.points[i, 0] +
                    self.solution[0][self.lens_dof_start + i])
            cmd += '%0.6f ' % (
                    self.mesh.points[i, 1] +
                    self.solution[1][self.lens_dof_start + i])
        self.cmd = cmd
        subprocess.check_call(cmd, shell=True)

        j = json.load(open(fname, 'r'))
        self.tf_thinplate = (
                renderapi.transform.ThinPlateSplineTransform(
                    dataString=j['dataString']))

    def new_stack_with_tf(self, tfchoice='thinplate'):
        if tfchoice == 'thinplate':
            tf = self.tf_thinplate
        else:
            tf = self.tf_poly

        sname = self.args['output_stack']
        render_target = self.args['render']
        renderapi.stack.create_stack(sname, render=render_target)

        refId = (self.args['sectionId'] +
                 datetime.datetime.now().strftime("_%Y%m%d%H%M%S"))
        tf.transformId = refId
        tf.labels = None

        newspecs = []
        for i in range(len(self.tilespecs)):
            newspecs.append(copy.deepcopy(self.tilespecs[i]))
            newspecs[-1].tforms.insert(0,
                                       renderapi.transform.ReferenceTransform(
                                        refId=refId))
            newspecs[-1].tforms[1].M00 = self.solution[0][i*3+0]
            newspecs[-1].tforms[1].M01 = self.solution[0][i*3+1]
            newspecs[-1].tforms[1].B0 = self.solution[0][i*3+2]
            newspecs[-1].tforms[1].M10 = self.solution[1][i*3+0]
            newspecs[-1].tforms[1].M11 = self.solution[1][i*3+1]
            newspecs[-1].tforms[1].B1 = self.solution[1][i*3+2]
            newspecs[-1].tforms[1].load_M()

        renderapi.client.import_tilespecs(
                sname,
                newspecs,
                sharedTransforms=[tf],
                render=render_target)
        renderapi.stack.set_stack_state(
                sname,
                'COMPLETE',
                render=render_target)

    def interpolate(self, xlim=None, ylim=None, nx=500, ny=500, flatten=False):
        if xlim is None:
            xlim = [0, self.tile_width]
        if ylim is None:
            ylim = [0, self.tile_height]
        x = np.linspace(xlim[0], xlim[1], nx)
        y = np.linspace(ylim[0], ylim[1], ny)
        xp, yp = np.meshgrid(x, y)
        xyint = np.transpose(np.vstack((xp.flatten(), yp.flatten())))
        z = self.compute_barycentrics(xyint)
        idx = (
            self.solution[0][self.lens_dof_start:][self.mesh.simplices[z[1]]] *
            z[0]
              ).sum(1).reshape(nx, ny)
        idy = (
            self.solution[1][self.lens_dof_start:][self.mesh.simplices[z[1]]] *
            z[0]
              ).sum(1).reshape(nx, ny)
        if flatten:
            return [xp.flatten(), yp.flatten(), idx.flatten(), idy.flatten()]
        else:
            return [xp, yp, idx, idy]

    def solve(self):
        self.create_regularization()
        ATW = self.A.transpose().dot(self.weights)
        K = ATW.dot(self.A) + self.reg
        K_factorized = factorized(K)
        self.solution = []
        for x0 in self.x0:
            Lm = self.reg.dot(x0)
            self.solution.append(K_factorized(Lm))

        self.errx = self.A.dot(self.solution[0])
        self.erry = self.A.dot(self.solution[1])

        self.transforms = []
        for i in range(len(self.unique_ids)):
            self.transforms.append(renderapi.transform.AffineModel(
                                    M00=self.solution[0][i*3+0],
                                    M01=self.solution[0][i*3+1],
                                    B0=self.solution[0][i*3+2],
                                    M10=self.solution[1][i*3+0],
                                    M11=self.solution[1][i*3+1],
                                    B1=self.solution[1][i*3+2]))

    def create_x0(self, nrows, ntiles):
        self.x0 = []
        self.x0.append(np.zeros(nrows).astype('float64'))
        self.x0.append(np.zeros(nrows).astype('float64'))
        self.x0[0][0:(3*ntiles)] = np.tile([1.0, 0.0, 0.0], ntiles)
        self.x0[1][0:(3*ntiles)] = np.tile([0.0, 1.0, 0.0], ntiles)
        for i in range(ntiles):
            self.x0[0][3*i+2] = self.tilespecs[i].minX
            self.x0[1][3*i+2] = self.tilespecs[i].minY

    def create_A(self):
        # let's assume affine_halfsize for now
        dof_per_tile = 3
        dof_per_vertex = 1
        vertex_per_patch = 3
        nnz_per_row = 2*(dof_per_tile + vertex_per_patch * dof_per_vertex)
        nrows = sum([len(m['matches']['p'][0]) for m in self.matches])
        nd = nnz_per_row*nrows
        self.lens_dof_start = dof_per_tile*self.unique_ids.size

        data = np.zeros(nd).astype('float64')
        indices = np.zeros(nd).astype('int64')
        indptr = np.zeros(nrows+1).astype('int64')
        indptr[1:] = np.arange(1, nrows+1)*nnz_per_row
        weights = np.ones(nrows).astype('float64')

        # nothing fancy here, row-by-row
        offset = 0
        for mi in range(len(self.matches)):
            m = self.matches[mi]
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
            pbary = self.compute_barycentrics(pcoords)
            qbary = self.compute_barycentrics(qcoords)

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

            indices[mstep+0] = self.tile_index[mi, 0]*dof_per_tile+0
            indices[mstep+1] = self.tile_index[mi, 0]*dof_per_tile+1
            indices[mstep+2] = self.tile_index[mi, 0]*dof_per_tile+2
            indices[mstep+3] = self.tile_index[mi, 1]*dof_per_tile+0
            indices[mstep+4] = self.tile_index[mi, 1]*dof_per_tile+1
            indices[mstep+5] = self.tile_index[mi, 1]*dof_per_tile+2
            indices[mstep+6] = (self.lens_dof_start +
                                self.mesh.simplices[pbary[1][:]][:, 0])
            indices[mstep+7] = (self.lens_dof_start +
                                self.mesh.simplices[pbary[1][:]][:, 1])
            indices[mstep+8] = (self.lens_dof_start +
                                self.mesh.simplices[pbary[1][:]][:, 2])
            indices[mstep+9] = (self.lens_dof_start +
                                self.mesh.simplices[qbary[1][:]][:, 0])
            indices[mstep+10] = (self.lens_dof_start +
                                 self.mesh.simplices[qbary[1][:]][:, 1])
            indices[mstep+11] = (self.lens_dof_start +
                                 self.mesh.simplices[qbary[1][:]][:, 2])

            offset += npoint_pairs*nnz_per_row

        self.data = data
        self.indices = indices
        self.indptr = indptr

        self.A = csr_matrix((data, indices, indptr))
        self.weights = sparse.eye(weights.size, format='csr')
        self.weights.data = weights
        self.create_x0(self.A.shape[1], self.unique_ids.size)

    def MeshAndSolve(self, render, 
                     input_stack, output_stack, 
                     match_collection, sectionId, 
                     nvertex, output_dir, outfile, default_lambda, 
                     translation_factor, lens_lambda):
        self.args = {}
        self.args['render'] = render
        self.args['input_stack'] = input_stack
        self.args['output_stack'] = output_stack
        self.args['match_collection'] = match_collection
        self.args['sectionId'] = sectionId
        self.args['nvertex'] = nvertex
        self.args['output_dir'] = output_dir
        self.args['out_html_dir'] = output_dir
        self.args['outfile'] = outfile
        self.args['regularization'] = {}
        self.args['regularization']['default_lambda'] = default_lambda
        self.args['regularization']['translation_factor'] = translation_factor
        self.args['regularization']['lens_lambda'] = lens_lambda

        # load the matches
        self.load_matches()

        # load tilespecs
        self.load_tilespecs()

        # condense coordinates
        self.condense_coords()

        # create PSLG
        self.create_PSLG()

        # find delaunay with max vertices
        self.find_delaunay_with_max_vertices()

        self.force_vertices_with_npoints(3)
        if self.has_hole:
            self.add_center_point()

        print('returned  %d vertices' % self.mesh.npoints)
        print('creating A...')
        self.create_A()
        
        print('solving...')
        self.solve()
        
        #self.report_solution()
        print('calling ThinPlateClient to create dataString')
        self.create_thinplatespline_tf()
        
        print('saving new stack entry')
        self.new_stack_with_tf()
        self.write_montage_qc_json()

        return self.args['outfile']