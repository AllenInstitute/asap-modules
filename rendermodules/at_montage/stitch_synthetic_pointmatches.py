import renderapi
import os
from pathos.multiprocessing import Pool
from functools import partial
from ..module.render_module import RenderModule
from rendermodules.at_montage.schemas import StitchSyntheticPointMatchesOutputParameters, StitchSyntheticPointMatchesParameters

example_json={
    "render":{
            "host": "ibs-forrestc-ux1",
            "port": 8080,
            "owner": "NewOwner",
            "project": "H1706003_z150",
            "client_scripts": "/pipeline/render/render-ws-java-client/src/main/scripts"
        },
        "example":"my example parameters"
}


class StitchSyntheticPointMatches(RenderModule):
    default_schema = StitchSyntheticPointMatchesParameters
    default_output_schema = StitchSyntheticPointMatchesOutputParameters
    def run(self):
        d = {
            "output_value":self.args['example']+self.args['default_val']
        }
        self.output(d)
        self.logger.error('this module does nothing useful')

if __name__ == "__main__":
    mod = StitchSyntheticPointMatches(input_data= example_json)
    mod.run()
