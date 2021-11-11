from rendermodules.module.template_module import TemplateModule
import json


def test_template_module(tmpdir):
    tmpfile = tmpdir.join('output.json')
    d = {
        "render": {
            "host": "ibs-forrestc-ux1",
            "port": 8080,
            "owner": "NewOwner",
            "project": "H1706003_z150",
            "client_scripts": "/pipeline/render/render-ws-java-client/src/main/scripts"
        },
        "example": "my example parameters",
        "output_json": str(tmpfile)
    }
    mod = TemplateModule(input_data=d, args=[])
    mod.run()

    with open(str(tmpfile), 'r') as fp:
        output_d = json.load(fp)

    assert output_d['output_value'] == (
        mod.args['example'] + mod.args['default_val'])
