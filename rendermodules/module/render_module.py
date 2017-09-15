import os
import subprocess
import argschema
import renderapi

class RenderModuleException(Exception):
    """Base Exception class for render module"""
    pass

class RenderClientParameters(argschema.schemas.DefaultSchema):
    host = argschema.fields.Str(
        required=True, description='render host')
    port = argschema.fields.Int(
        required=True, description='render post integer')
    owner = argschema.fields.Str(
        required=True, description='render default owner')
    project = argschema.fields.Str(
        required=True, description='render default project')
    client_scripts = argschema.fields.Str(
        required=True, description='path to render client scripts')
    memGB = argschema.fields.Str(
        required=False, default='5G',
        description='string describing java heap memory (default 5G)')


class RenderParameters(argschema.ArgSchema):
    render = argschema.fields.Nested(RenderClientParameters)

class ArgSchemaModule(argschema.ArgSchemaParser):
    default_schema = None
    default_output_schema = None


class RenderModule(ArgSchemaModule):
    default_schema = RenderParameters

    def __init__(self, schema_type=None, *args, **kwargs):
        if (schema_type is not None and not
            issubclass(schema_type, RenderParameters)):
            raise RenderModuleException(
                'schema {} is not of type RenderParameters')

        # TODO do we want output schema passed?
        super(RenderModule, self).__init__(
            schema_type=schema_type, *args, **kwargs)
        self.render = renderapi.render.connect(**self.args['render'])

if __name__ == '__main__':
    example_input = {
        "render": {
            "host": "ibs-forrestc-ux1",
            "port": 8080,
            "owner": "NewOwner",
            "project": "H1706003_z150",
            "client_scripts": "/pipeline/render/render-ws-java-client/src/main/scripts"
        }
    }
    module = RenderModule(input_data=example_input)

    bad_input = {
        "render": {
            "host": "ibs-forrestc-ux1",
            "port": '8080',
            "owner": "Forrest",
            "project": "H1706003_z150",
            "client_scripts": "/pipeline/render/render-ws-java-client/src/main/scripts"
        }
    }
    module = RenderModule(input_data=bad_input)
