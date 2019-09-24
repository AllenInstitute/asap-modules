#!/usr/bin/env python
import os

import renderapi
from six.moves import urllib

from rendermodules.module.render_module import StackTransitionModule
from rendermodules.lens_correction.schemas import \
        ApplyLensCorrectionOutput, ApplyLensCorrectionParameters
from rendermodules.dataimport.create_mipmaps import create_mipmaps_uri
from rendermodules.utilities import uri_utils

example_input = {
    "render": {
        "host": "em-131fs",
        "port": 8080,
        "owner": "samk",
        "project": "RENDERAPI_TEST",
        "client_scripts": (
            "/allen/programs/celltypes/workgroups/"
            "em-connectomics/russelt/render_mc.old/render-ws-java-client/"
            "src/main/scripts")
    },
    "inputStack": "test_noLC",
    "outputStack": "test_LC",
    "pool_size": 10,
    "close_stack": True,
    "zs": [2266],
    "transform": {
        "type": "leaf",
        "className": "lenscorrection.NonLinearTransform",
        "dataString": (
            "5 21 1078.539787490504 5.9536401731869155 "
            "18.082459176969103 1078.355487979244 3.5307003058070348 "
            "11.64046339965791 -2.0439286697147363 -24.64074017045258 "
            "-41.26811513301735 -9.491349156078 -1.6954196055547417 "
            "-9.185363883704582 3.2959653136929163 16.063471152021727 "
            "16.294847510892705 11.433417367508135 31.814503296730077 "
            "8.568546283786144 1.1875763257283882 1.8390027135003706 "
            "4.811216491589896 -6.951845669522106 -12.267142955347461 "
            "-15.925381113080153 -14.870929614388771 -1.4936338107986824 "
            "-14.329785142195151 -10.312907851336057 -0.42262010802849903 "
            "-1.009175398784258 -3.2394612925182904 1.1172748871012366 "
            "3.675506795700918 4.147928095339033 4.180779006453825 "
            "2.3467092081149583 3.126555229782104 -0.7606672639855052 "
            "4.694244302355039 4.905604855794568 19.42462457061161 "
            "17.804784158940837 1942.4644352489915 1780.4747249033032 "
            "4947240.512601199 3472086.434895099 4297903.568850483 "
            "1.4156910200690086E10 8.869224932399399E9 8.401913335029685E9 "
            "1.184452643883111E10 4.326915271956289E13 "
            "2.5462360962795074E13 2.1493026326968934E13 "
            "2.3188186000529023E13 3.519602640946822E13 "
            "1.3795333182608984E17 7.805152532090952E16 "
            "6.180627842946396E16 5.937108087578708E16 "
            "6.8994694539978896E16 1.09803035347323568E17 100.0 "
            "1083.561059814147 1062.000092490804 4335259.912658479 "
            "3072116.6105437097 4089560.9959054096 1.588497037768282E10 "
            "1.054070313855633E10 1.0306317022320707E10 "
            "1.463025351609144E10 5.735536632714905E13 "
            "3.677632888097447E13 3.3248028854072227E13 "
            "3.53752851004701E13 5.205228949477172E13 "
            "2.06753448194955584E17 1.29851821487233248E17 "
            "1.12997804746083296E17 1.1130902498005392E17 "
            "1.23651446458254E17 1.85995206005396736E17 0.0 3840 3840 ")
    },
    "refId": None
}


class ApplyLensCorrection(StackTransitionModule):
    default_schema = ApplyLensCorrectionParameters
    default_output_schema = ApplyLensCorrectionOutput

    def run(self):
        outputStack = self.output_stack
        r = self.render
        refId = (r.run(renderapi.stack.likelyUniqueId)
                 if self.args['refId'] is None else self.args['refId'])

        lc_tform = renderapi.transform.load_transform_json(
            self.args['transform'])
        lc_tform.transformId = refId
        ref_lc = renderapi.transform.ReferenceTransform(
            refId=lc_tform.transformId)
        if lc_tform.labels is None:
            lc_tform.labels = self.args['labels']
        else:
            for label in self.args['labels']:
                if label not in lc_tform.labels:
                    lc_tform.labels.append(label)

        tspecs = renderapi.tilespec.get_tile_specs_from_z(
            self.input_stack, self.zValues[0], render=r)
        levels = [int(l) for l in tspecs[0].ip.levels]
        # make mask mipmaps
        mask_mm_list = {}
        if self.args['maskUrl'] is not None:
            root, ext = os.path.splitext(
                urllib.parse.unquote(urllib.parse.urlparse(
                    self.args['maskUrl']).path))
            mask_mm_list = create_mipmaps_uri(
                self.args['maskUrl_uri'],
                outputDirectory=uri_utils.uri_prefix(self.args['maskUrl_uri']),  # os.path.dirname(self.args['maskUrl']),
                mipmaplevels=levels,
                outputformat=ext.split('.')[-1],
                convertTo8bit=False,
                force_redo=True,
                block_func="min")

        # new tile specs for each z selected
        new_tspecs = []
        for z in self.zValues:
            tspecs = renderapi.tilespec.get_tile_specs_from_z(
                self.input_stack, z, render=r)

            for ts in tspecs:
                ts.tforms = [ref_lc] + ts.tforms
                for lvl, maskUrl in mask_mm_list.items():
                    ts.ip[lvl].maskUrl = maskUrl  # pathlib.Path(maskUrl).as_uri()
                new_tspecs.append(ts)

        renderapi.stack.create_stack(outputStack, render=r)
        renderapi.stack.set_stack_state(outputStack, 'LOADING', render=r)

        self.output_tilespecs_to_stack(new_tspecs, sharedTransforms=[lc_tform])

        missing_ts_zs = []
        for z in self.zValues:
            job_success = self.validate_tilespecs(self.input_stack, outputStack, z)
            if not job_success:
               missing_ts_zs.append(z)

        # output dict
        output = {}
        output['stack'] = outputStack
        output['refId'] = refId
        output['missing_ts_zs'] = missing_ts_zs

        try:
            self.output(output)
        except AttributeError as e:
            self.logger.error(e)


if __name__ == '__main__':
    module = ApplyLensCorrection(input_data=example_input)
    module.run()
