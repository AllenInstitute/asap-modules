from rendermodules.module.render_module import RenderModule, RenderModuleException
from rendermodules.module.schemas import RenderParameters
import argschema
from test_data import render_params
import pytest

pytestmark = pytest.mark.skip()


def test_render_modules():
    d = {'render':render_params}
    mod = RenderModule(input_data = d,args=[])
    assert(mod.args['render']==render_params)

class NotARenderSchema(argschema.ArgSchema):
    pass

def test_render_modules_fail():
    with pytest.raises(RenderModuleException):
        mod = RenderModule(input_data = {}, schema_type=NotARenderSchema, args=[])
