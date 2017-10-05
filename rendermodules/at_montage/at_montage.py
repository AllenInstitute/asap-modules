if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.at_montage.at_montage"

import os
import json
from rendermodules.module.render_module import RenderModule
from rendermodules.at_montage.schemas import ATMontageParams
import subprocess

example_input = {
    "render": {
        "host": "ibs-forrestc-ux1",
        "port": 8080,
        "owner": "6_ribbon_expts",
        "project":"M335503_Ai139_smallvol",
        "client_scripts": "/var/www/render/render-ws-java-client/src/main/scripts"
    },
    "baseDataUrl": "http://ibs-forrestc-ux1.corp.alleninstitute.org/render-ws/v1",
    "maxEpsilon": 2.5,
    "initialSigma": 2.5,
    "section": 506,
    "modelType": 1,
    "steps": 3,
    "outputStack": "Stitched_1_DAPI_1",
    "percentSaturated": 0.9,
    "stack": "Flatfieldcorrected_1_DAPI_1",
    "jar_file": "/pipeline/sharmi/at_modules/allen/target/allen-1.0-SNAPSHOT-jar-with-dependencies.jar",
    "stitching_json": "/pipeline/forcron/stitching/log/stitching_M335503_Ai139_smallvol_DAPI_1_5_1_6TEST12.json"
}

def create_stitching_json(args):
    donotcopy = ['render','jar_file','stitching_json']
    d =  dict()

    for key in args.keys():
        if key not in donotcopy:
            d[key]=args[key]
    d['owner'] = args['render']['owner']
    d['project'] = args['render']['project']

    with open(args['stitching_json'], 'w') as outfile:
        json.dump(d, outfile,indent=4)

class ATMontage(RenderModule):
    default_schema = ATMontageParams

    def run(self):
        mod = "at_modules.StitchImagesByCC"
        create_stitching_json(self.args)
        subprocess.call(["java","-cp",self.args['jar_file'],mod, "--input_json", self.args['stitching_json']])

if __name__ == "__main__":
    mod = ATMontage(input_data=example_input)
    mod.run()
