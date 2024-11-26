import numpy as np
import requests
import renderapi


def compute_residuals(tilespecs, matches, min_points=1, extra_statistics=None):
    """from compute_residuals_in_group for in-memory"""
    extra_statistics = extra_statistics or {}

    tId_to_tforms = {ts.tileId: ts.tforms for ts in tilespecs}

    tile_residuals = {key: np.empty((0, 1)) for key in tId_to_tforms.keys()}
    tile_rmse = {key: np.empty((0, 1)) for key in tId_to_tforms.keys()}
    pt_match_positions = {key: np.empty((0, 2)) for key in tId_to_tforms.keys()}

    statistics = {}

    for match in matches:
        pts_p = np.array(match['matches']['p'])
        pts_q = np.array(match['matches']['q'])
    
        if pts_p.shape[1] < min_points:
            continue

        try:
            t_p = tId_to_tforms[match['pId']][-1].tform(pts_p.T)
            t_q = tId_to_tforms[match['qId']][-1].tform(pts_q.T)
        except KeyError:
            continue

        positions = (t_p + t_q) / 2.
    
        res = np.linalg.norm(t_p - t_q, axis=1)
        rmse = np.true_divide(res, res.shape[0])

        tile_residuals[match['pId']] = np.append(
            tile_residuals[match['pId']], res)
        tile_rmse[match['pId']] = np.append(
            tile_rmse[match['pId']], rmse)
        pt_match_positions[match['pId']] = np.append(
            pt_match_positions[match['pId']], positions, axis=0)

    empty_keys = [k for k in tile_residuals if tile_residuals[k].size == 0]

    for k in empty_keys:
        tile_residuals.pop(k)
        tile_rmse.pop(k)
        pt_match_positions.pop(k)

    statistics['tile_rmse'] = tile_rmse
    statistics['tile_residuals'] = tile_residuals
    statistics['pt_match_positions'] = pt_match_positions

    statistics = {**extra_statistics, **statistics}
    
    return statistics, matches


def compute_residuals_within_group(render, stack, matchCollectionOwner,
                                   matchCollection, z, min_points=1,
                                   tilespecs=None):
    session = requests.session()

    # get the sectionID which is the group ID in point match collection
    groupId = render.run(
        renderapi.stack.get_sectionId_for_z, stack, z, session=session)

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

    statistics, allmatches = compute_residuals(
        tilespecs, allmatches, min_points=min_points,
        extra_statistics={"z": z})

    session.close()

    return statistics, allmatches


def compute_mean_tile_residuals(residuals):
    tile_mean = {
        tileId: (np.nanmean(tile_residuals) if tile_residuals.size else np.nan)
        for tileId, tile_residuals in residuals.items()
    }
    tile_residual_max = np.nanmax(tile_mean.values())

    return {
        tileId: (
            tile_residual if not np.isnan(tile_residual)
            else tile_residual_max)
        for tileId, tile_residual in tile_mean.items()
    }


def get_tile_centers(tilespecs):
    xc = []
    yc = []
    tileId = []
    for ts in tilespecs:
        xc.append(0.5*(ts.bbox[0]+ts.bbox[2]))
        yc.append(0.5*(ts.bbox[1]+ts.bbox[3]))
        tileId.append(ts.tileId)
    return np.array(xc), np.array(yc), np.array(tileId)
