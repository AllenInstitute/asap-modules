import json
import renderapi
import numpy as np
from rendermodules.module.render_module import RenderModule
from .schemas import FilterSchema, FilterOutputSchema
import logging

example = {
    "render": {
        "host": "em-131db.corp.alleninstitute.org",
        "port": 8080,
        "owner": "TEM",
        "project": "17797_1R",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
        "memGB": "2G"},
    "input_stack": "em_2d_montage_lc",
    "input_match_collection": "default_point_matches",
    "output_match_collection": None,
    "resmax": 5.0,
    "transmax": 500.0,
    "minZ": 120581,
    "maxZ": 120583,
    "filter_output_file": "./filter_output.json",
    "output_json": "./tmpout.json"
}

logger = logging.getLogger()


def filter_plot(fig, result_json, fs=14):

    z = result_json['z']
    tmax = result_json['transmax']
    rmax = result_json['resmax']
    cnt = np.array([i['count'] for i in result_json['filter']])
    nres = np.array([i['nres'] for i in result_json['filter']])
    dr = np.array([i['translation'] for i in result_json['filter']])

    fig.clf()
    fig.set_size_inches(12, 12/1.618)

    ax = fig.add_subplot(221)
    ax.scatter(cnt, nres, marker='.', s=10.3, color='k')
    ax.set_yscale('log')
    ax.set_title('z = %d' % z)
    ax.legend(['mean(resid)\n%0.2f [px]' % nres.mean()])
    ax.set_xlabel('# of point pairs', fontsize=fs)
    ax.set_ylabel('average residual per tilepair', color='b', fontsize=fs)
    ax.tick_params('y', colors='b')

    ax = fig.add_subplot(223)
    ax.hist(dr, bins=np.logspace(
        np.log10(dr.min()), np.log10(dr.max()), 100), color='k')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.legend(['mean(trans)\n%0.1f [px]' % dr.mean()])
    ax.tick_params('x', colors='r')
    ax.set_xlabel('translation [pixels]', color='r', fontsize=fs)
    ax.set_ylabel('# of point pairs', fontsize=fs)

    ax = fig.add_subplot(122)
    ax.scatter(dr, nres, marker='.', s=10.3, color='k')
    ax.set_yscale('log')
    ax.set_xscale('log')
    ax.set_xlabel('translation [pixels]', color='r', fontsize=fs)
    ax.set_ylabel('average residuals [pixels]', color='b', fontsize=fs)
    ax.tick_params('x', colors='r')
    ax.tick_params('y', colors='b')
    ax.set_title('%d tile pairs' % len(result_json['filter']))
    ax.plot([tmax, tmax], [ax.get_ylim()[0], rmax], '--r', alpha=0.5)
    ax.plot([ax.get_xlim()[0], tmax], [rmax, rmax], '--b', alpha=0.5)


def proc_job(fargs):
    [input_match_collection, output_match_collection,
        input_stack, z, resmax, transmax, rpar, inverse] = fargs

    render = renderapi.connect(**rpar)
    try:
        matches = renderapi.pointmatch.get_matches_within_group(
                input_match_collection,
                str(float(z)),
                render=render)
        tspecs = renderapi.tilespec.get_tile_specs_from_z(
                input_stack,
                float(z),
                render=render)
    except renderapi.errors.RenderError as e:
        logger.warning(str(e))
        return None

    if len(matches) == 0:
        return None

    tids = np.array([t.tileId for t in tspecs])

    residuals = []
    translations = []
    counts = []
    pids = [m['pId'] for m in matches]
    qids = [m['qId'] for m in matches]
    tf = renderapi.transform.AffineModel()

    for m in matches:
        A = np.transpose(np.array(m['matches']['p']))
        B = np.transpose(np.array(m['matches']['q']))
        tvec, res, _, _ = tf.fit(A, B, return_all=True)

        pi = np.argwhere(tids == m['pId'])[0][0]
        qi = np.argwhere(tids == m['qId'])[0][0]
        dx = tspecs[pi].tforms[-1].B0 - tspecs[qi].tforms[-1].B0
        dy = tspecs[pi].tforms[-1].B1 - tspecs[qi].tforms[-1].B1

        residuals.append(res)
        counts.append(len(m['matches']['w']))
        translations.append(
                np.sqrt(
                    np.power(dx - tvec[4][0], 2.0) +
                    np.power(dy - tvec[5][0], 2.0)))

    residuals = np.array(residuals).squeeze()
    counts = np.array(counts)
    nres = np.round(np.sqrt(residuals/counts), 3)
    translations = np.round(np.array(translations), 3)

    w = []
    cmax = float(counts.max())
    updated_matches = []

    def new_match(match, new_w, copy=False):
        changed = not np.all(np.isclose(
            np.array(new_w),
            np.array(match['matches']['w'])))
        if (not copy) & (not changed):
            return None

        nmatch = dict(match)
        nmatch['matches']['w'] = new_w
        return nmatch

    for i in range(len(matches)):
        w.append(1.0)
        if (nres[i] > resmax) | (translations[i] > transmax):
            # solver will ignore
            w[-1] = 0.0
        if inverse:
            w.append(cmax/counts[i])
        if output_match_collection is not None:
            new_w = [w[-1]] * counts[i]
            if(output_match_collection != input_match_collection):
                # copy over everything, modified or not
                updated_matches.append(new_match(matches[i], new_w, copy=True))
            else:
                # only copy over modified
                nmatch = new_match(matches[i], new_w, copy=False)
                if nmatch is not None:
                    updated_matches.append(nmatch)

    if output_match_collection is not None:
        logger.info(
                "updating weights for %d of %d matches for z=%d in %s" % (
                    len(updated_matches),
                    len(matches),
                    int(z),
                    output_match_collection))
        renderapi.pointmatch.import_matches(
                output_match_collection,
                updated_matches,
                render=render)

    result = {}
    result['z'] = z
    result['transmax'] = transmax
    result['resmax'] = resmax
    result['filter'] = []
    for i in range(len(pids)):
        result['filter'].append(
                {
                    'pId': pids[i],
                    'qId': qids[i],
                    'nres': nres[i],
                    'translation': translations[i],
                    'count': counts[i],
                    'weight': w[i]})
    return result


class FilterMatches(RenderModule):
    default_schema = FilterSchema
    default_output_schema = FilterOutputSchema

    def run(self):
        fargs = []
        for z in self.args['zValues']:
            fargs.append([
                self.args['input_match_collection'],
                self.args['output_match_collection'],
                self.args['input_stack'],
                z,
                self.args['resmax'],
                self.args['transmax'],
                self.args['render'],
                self.args['inverse_weighting']])

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            results = pool.map(proc_job, fargs)

        with open(self.args['filter_output_file'], 'w') as f:
            json.dump(
                    [x for x in results if x is not None],
                    f,
                    indent=2)

        with open(self.args['output_json'], 'w') as f:
            outj = {'filter_output_file': self.args['filter_output_file']}
            json.dump(outj, f, indent=2)


if __name__ == '__main__':
    fmod = FilterMatches(input_data=example)
    fmod.run()
