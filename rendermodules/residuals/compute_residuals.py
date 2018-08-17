import numpy as np
import requests
import renderapi


def compute_residuals_within_group(render, stack, matchCollectionOwner, matchCollection, z, min_points=1, tilespecs=None):
    session = requests.session()

    # get the sectionID which is the group ID in point match collection
    groupId = render.run(renderapi.stack.get_sectionId_for_z, stack, z, session=session)

    # get matches within the group for this section
    allmatches = render.run(
                    renderapi.pointmatch.get_matches_within_group,
                    matchCollection,
                    groupId,
                    owner=matchCollectionOwner,
                    session=session)

    # get the tilespecs to extract the transformations
    if tilespecs is None:
        tilespecs = render.run(renderapi.tilespec.get_tile_specs_from_z,
                               stack, z, session=session)
    tforms = {ts.tileId: ts.tforms for ts in tilespecs}

    # transformed_pts = np.zeros((1,2))
    tile_residuals = {key: np.empty((0,1)) for key in tforms.keys()}
    tile_rmse = {key: np.empty((0,1)) for key in tforms.keys()}
    pt_match_positions = {key: np.empty((0,2)) for key in tforms.keys()}

    statistics = {}
    for i, match in enumerate(allmatches):
        pts_p = np.array(match['matches']['p'])
        pts_q = np.array(match['matches']['q'])

        if pts_p.shape[1] < min_points:
            continue
        try:
            t_p = tforms[match['pId']][-1].tform(pts_p.T)
            t_q = tforms[match['qId']][-1].tform(pts_q.T)
        except KeyError:
            continue
        # if ((match['pId'] in tforms.keys()) and (match['qId'] in tforms.keys())):
        # t_p = (tforms[match['pId']])[-1].tform(pts_p.T)
        # t_q = (tforms[match['qId']])[-1].tform(pts_q.T)

        # find the mean spatial location of the point matches
        # needed for seam detection
        # positions = [[(a[0]+b[0])/2, (a[1]+b[1])/2] for a,b in zip(t_p, t_q)]
        # TODO add this
        positions = (t_p + t_q) / 2.

        res = np.linalg.norm(t_p - t_q, axis=1)
        rmse = np.true_divide(res, res.shape[0])

        tile_residuals[match['pId']] = np.append(tile_residuals[match['pId']], res)
        tile_rmse[match['pId']] = np.append(tile_rmse[match['pId']], rmse)
        pt_match_positions[match['pId']] = np.append(pt_match_positions[match['pId']], positions, axis=0)

    # remove empty entries from these dicts
    empty_keys = [k for k in tile_residuals if tile_residuals[k].size == 0]
    for k in empty_keys:
        tile_residuals.pop(k)
        tile_rmse.pop(k)
        pt_match_positions.pop(k)

    statistics['tile_rmse'] = tile_rmse
    statistics['z'] = z
    statistics['tile_residuals'] = tile_residuals
    statistics['pt_match_positions'] = pt_match_positions

    session.close()

    return statistics, allmatches

def compute_mean_tile_residuals(residuals):
    tile_mean = {}
    
    # loop over each tile and compute the mean residual for each tile
    # iteritems is specific to py2.7
    #print(residuals)
    maxes = [np.nanmean(v) for v in residuals.values() if len(v) > 0]
    #print(maxes)
    maximum = np.max(maxes)

    for key in residuals:
        if len(residuals[key]) == 0:
            #tile_mean[key] = np.nan
            tile_mean[key] = maximum
        else:
            tile_mean[key] = np.nanmean(residuals[key])

    return tile_mean

def get_tile_centers(tilespecs):
    xc = []
    yc = []
    tileId = []
    for ts in tilespecs:
        xc.append(0.5*(ts.bbox[0]+ts.bbox[2]))
        yc.append(0.5*(ts.bbox[1]+ts.bbox[3]))
        tileId.append(ts.tileId)
    return np.array(xc), np.array(yc), np.array(tileId)
