from rendermodules.module.render_module import (
    RenderModule, RenderModuleException
    )
import argschema
from test_data import render_params
import pytest


def test_render_modules():
    d = {'render': render_params}
    mod = RenderModule(input_data=d, args=[])
    assert(mod.args['render'] == render_params)


class NotARenderSchema(argschema.ArgSchema):
    pass


def test_render_modules_fail():
    with pytest.raises(RenderModuleException):
        mod = RenderModule(
            input_data={}, schema_type=NotARenderSchema, args=[])
