import renderapi
import os
from pathos.multiprocessing import Pool
from functools import partial
from ..module.render_module import RenderModule, RenderParameters
import argschema
import marshmallow as mm

example_json={
        "render":{
            "host":"ibs-forrestc-ux1",
            "port":8080,
            "owner":"Forrest",
            "project":"M247514_Rorb_1",
            "client_scripts":"/pipeline/render/render-ws-java-client/src/main/scripts"
        },
        "example":"my example parameters",
}

class TemplateParameters(RenderParameters):
    example = argschema.fields.Str(required=True,
        description='an example')
    default_val = argschema.fields.Str(required=False,default="a default value",
        description='an example with a default')


class Template(RenderModule):
    def __init__(self,schema_type=None,*args,**kwargs):
        if schema_type is None:
            schema_type = TemplateParameters
        super(Template,self).__init__(schema_type=schema_type,*args,**kwargs)
    def run(self):
        print self.args
        self.logger.error('WARNING NEEDS TO BE TESTED, TALK TO FORREST IF BROKEN')


if __name__ == "__main__":
    mod = Template(input_data= example_json)
    mod.run()
