from rendermodules.module.template_module import TemplateModule
import pytest
import json

def test_template_module(tmpdir):
    tmpfile = tmpdir.join('output.json')
    d = {
        "example":"my example parameters",
        "output_json":str(tmpfile)
    }
    mod = TemplateModule(input_data = d)
    mod.run()

    with open(str(tmpfile),'r') as fp:
        output_d = json.load(fp)
    
    assert output_d['output_value']==(mod.args['example']+mod.args['default_val'])
    