import renderapi
from rendermodules.module.render_module import RenderModule
from rendermodules.module.schemas import TemplateOutputParameters, TemplateParameters

example_json = {
    "render": {
        "host": "ibs-forrestc-ux1",
        "port": 8080,
        "owner": "NewOwner",
        "project": "H1706003_z150",
        "client_scripts": "/pipeline/render/render-ws-java-client/src/main/scripts"
    },
    "example": "my example parameters"
}


class TemplateModule(RenderModule):
    default_schema = TemplateParameters
    default_output_schema = TemplateOutputParameters

    def run(self):
        d = {
            "output_value": self.args['example'] + self.args['default_val']
        }
        self.output(d)
        self.logger.error('this module does nothing useful')


if __name__ == "__main__":
    mod = TemplateModule(input_data=example_json)
    mod.run()
