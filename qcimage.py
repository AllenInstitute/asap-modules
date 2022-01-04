import renderapi
import matplotlib.pyplot as plt
import numpy as np
import cv2

example = {
        "stack": "em_2d_lc_corrected",
        "collection": "em_2d_lens_matches",
        "z": 5920,
        "kernel_size": 30,
        "match_index": 43,
        "render_params": {
            "owner": "TEM",
            "project": "em_2d_montage_staging",
            "host": "em-131db",
            "port": 8080,
            "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
        }
}


class AlignmentByImage():
    def run(self, example):
        # get the tilespecs
        render = renderapi.connect(**example['render_params'])
        ims = []
        tspecs = []
        resolved = renderapi.resolvedtiles.get_resolved_tiles_from_z(
                example['stack'],
                example['z'],
                render=render)
        ids = np.array([t.tileId for t in resolved.tilespecs])
        sectionId = resolved.tilespecs[0].layout.sectionId

        # get matches to know tilepairs
        matches = renderapi.pointmatch.get_matches_within_group(
                example['collection'],
                sectionId,
                render=render)

        # render the images for the specified point match tile pair
        for a in ['pId','qId']:
            tid = matches[example['match_index']][a]
            ind = np.argwhere(ids == tid)[0][0]
            tspecs.append(
                    resolved.tilespecs[ind])
            ims.append(
                    renderapi.image.get_tile_image_data(
                        example['stack'],
                        tid,
                        render=render,
                        img_format='.tif',
                        excludeAllTransforms=False,
                        normalizeForMatching=False)[:,:,0])

        # translate the two images into the same coordinates
        dx = tspecs[1].tforms[-1].B0 - \
                tspecs[0].tforms[-1].B0
        dy = tspecs[1].tforms[-1].B1 - \
                tspecs[0].tforms[-1].B1
        trans0 = np.float32([ [1,0,0], [0,1,0]])
        trans1 = np.float32([ [1,0,dx], [0,1,dy]])
        (num_rows, num_cols) = ims[1].shape
        ic0 = cv2.equalizeHist(
                cv2.warpAffine(
                    ims[0],
                    trans0,
                    (num_cols + np.int(np.ceil(dx)),
                    num_rows + np.int(np.ceil(dy)))))
        ic1 = cv2.equalizeHist(
                cv2.warpAffine(
                    ims[1],
                    trans1,
                    (num_cols + np.int(np.ceil(dx)),
                    num_rows + np.int(np.ceil(dy)))))
       
        # mask out the non-overlapping area
        m0 = np.ma.masked_where(ic0 == 0, ic0)
        m1 = np.ma.masked_where(ic1 == 0, ic1)
        plt.figure(1)
        plt.clf()
        ax1 = plt.subplot(121)
        ax1.imshow(m0, cmap='gray', alpha=0.5)
        ax1.imshow(m1, cmap='gray', alpha=0.5)
        common_mask = ~((~m0.mask) & (~m1.mask))
        m0.mask = common_mask
        m1.mask = common_mask
        plt.title('tile pair', fontsize=18)
       
        # compute correlations and average
        kern = (example['kernel_size'], example['kernel_size'])
        m0 = np.array(m0.filled(fill_value=0), dtype=float)
        m1 = np.array(m1.filled(fill_value=0), dtype=float)
        ave_m0 = cv2.blur(m0, kern)
        ave_m1 = cv2.blur(m1, kern)
        pr = (m0-ave_m0)*(m1-ave_m1)
        cpr = cv2.blur(pr, kern)
        ax2 = plt.subplot(122, sharex=ax1, sharey=ax1)
        plt.imshow(cpr, vmin=0, vmax=100)
        plt.title('match quality', fontsize=18)
	plt.show()

if __name__ == '__main__':
    mod = AlignmentByImage()
    mod.run(example)

