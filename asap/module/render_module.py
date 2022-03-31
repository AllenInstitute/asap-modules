#!/usr/bin/env python
import subprocess
import os

import argschema
import renderapi
from asap.module.schemas import (
    RenderParameters, InputStackParameters, OutputStackParameters,
    SparkParameters)


class RenderModuleException(Exception):
    """Base Exception class for render module"""
    pass


class RenderModule(argschema.ArgSchemaParser):
    default_schema = RenderParameters

    def __init__(self, schema_type=None, *args, **kwargs):
        if (schema_type is not None and not issubclass(
                schema_type, RenderParameters)):
            raise RenderModuleException(
                'schema {} is not of type RenderParameters')

        # TODO do we want output schema passed?
        super(RenderModule, self).__init__(
            schema_type=schema_type, *args, **kwargs)
        self.render = renderapi.render.connect(**self.args['render'])


class StackInputModule(RenderModule):
    default_schema = InputStackParameters

    def __init__(self, default_schema=None, *args, **kwargs):
        super(StackInputModule, self).__init__(*args, **kwargs)
        self.input_stack = self.args['input_stack']
        self.zValues = self.args['zValues']

    def get_inputstack_zs(self, input_stack=None, render=None, **kwargs):
        input_stack = self.input_stack if input_stack is None else input_stack
        render = self.render if render is None else render

        return renderapi.stack.get_z_values_for_stack(
            input_stack, render=render)

    def get_overlapping_inputstack_zvalues(
            self, input_stack=None, zValues=None,
            render=None, **kwargs):
        input_stack = self.input_stack if input_stack is None else input_stack
        zValues = self.zValues if zValues is None else zValues
        render = self.render if render is None else render

        inputstack_zs = self.get_inputstack_zs(input_stack, render, **kwargs)
        return list(set(zValues).intersection(set(inputstack_zs)))


class StackOutputModule(RenderModule):
    default_schema = OutputStackParameters

    def __init__(self, default_schema=None, *args, **kwargs):
        super(StackOutputModule, self).__init__(*args, **kwargs)
        self.output_stack = self.args['output_stack']
        self.zValues = self.args['zValues']
        self.pool_size = self.args['pool_size']
        self.close_stack = self.args['close_stack']
        self.overwrite_zlayer = self.args['overwrite_zlayer']

    def delete_zValues(self, zValues=None, output_stack=None, render=None):
        zValues = self.zValues if zValues is None else zValues
        output_stack = (self.output_stack if output_stack is None
                        else output_stack)
        render = self.render if render is None else render

        for z in zValues:
            try:
                renderapi.stack.delete_section(
                    output_stack, z, render=render)
            except renderapi.errors.RenderError as e:
                self.logger.error(e)

    def output_tilespecs_to_stack(self, tilespecs, output_stack=None,
                                  sharedTransforms=None, close_stack=None,
                                  overwrite_zlayer=None, render=None,
                                  pool_size=None, **kwargs):
        # TODO decorator to handle kwarg/attribute overrides?
        output_stack = (self.output_stack if output_stack is None
                        else output_stack)
        render = self.render if render is None else render
        close_stack = self.close_stack if close_stack is None else close_stack
        pool_size = self.pool_size if pool_size is None else pool_size
        overwrite_zlayer = (self.overwrite_zlayer if overwrite_zlayer is None
                            else overwrite_zlayer)

        if output_stack not in render.run(
                renderapi.render.get_stacks_by_owner_project):
            # stack does not exist
            render.run(renderapi.stack.create_stack,
                       output_stack)

        render.run(renderapi.stack.set_stack_state,
                   output_stack, 'LOADING')

        if overwrite_zlayer:
            self.delete_zValues(output_stack=output_stack, render=render,
                                **kwargs)
        renderapi.client.import_tilespecs_parallel(
            output_stack, tilespecs, sharedTransforms=sharedTransforms,
            pool_size=pool_size, close_stack=close_stack, render=render)

    def validate_tilespecs(self, input_stack, output_stack, z, render=None):
        render = self.render if render is None else render

        input_rs = renderapi.resolvedtiles.get_resolved_tiles_from_z(
            input_stack, z, render=render)
        output_rs = renderapi.resolvedtiles.get_resolved_tiles_from_z(
            output_stack, z, render=render)
        in_ids = set([t.tileId for t in input_rs.tilespecs])
        out_ids = set([t.tileId for t in output_rs.tilespecs])
        if in_ids != out_ids:  # pragma: no cover
            return False
        else:
            return True


class StackTransitionModule(StackOutputModule, StackInputModule):
    def __init__(self, *args, **kwargs):
        super(StackTransitionModule, self).__init__(*args, **kwargs)


class SparkModuleError(RenderModuleException):
    """error thrown by asap spark modules"""


class SparkModule(argschema.ArgSchemaParser):
    default_schema = SparkParameters

    @staticmethod
    def sanitize_cmd(cmd):
        def jbool_str(c):
            return str(c) if type(c) is not bool else "true" if c else "false"
        if any([i is None for i in cmd]):
            raise SparkModuleError(
                'missing argument in command "{}"'.format(map(str, cmd)))
        return list(map(jbool_str, cmd))

    @staticmethod
    def get_cmd_opt(v, flag=None):
        return [] if v is None else [v] if flag is None else [flag, v]

    @staticmethod
    def get_flag_cmd(v, flag=None):
        # for arity 0
        return [flag] if v else []

    @classmethod
    def get_spark_call(cls, masterUrl=None, jarfile=None, className=None,
                       driverMemory=None, memory=None, sparkhome=None,
                       spark_files=None, spark_conf=None, **kwargs):
        get_cmd_opt = cls.get_cmd_opt
        sparksub = os.path.join(sparkhome, 'bin', 'spark-submit')

        sparkfileargs = []
        if spark_files is not None:
            for sparkfile in spark_files:
                sparkfileargs += ['--files', sparkfile]
        sparkconfargs = []
        if spark_conf is not None:
            for key, value in spark_conf.items():
                sparkconfargs += ['--conf', "{}='{}'".format(key, value)]

        cmd = ([sparksub, '--master', masterUrl] +
               get_cmd_opt(driverMemory, '--driver-memory') +
               get_cmd_opt(memory, '--executor-memory') +
               sparkfileargs +
               sparkconfargs +
               ['--class', className,
               jarfile])
        return cls.sanitize_cmd(cmd)

    @classmethod
    def get_args(cls, **kwargs):
        """override to append to spark call"""
        return cls.sanitize_cmd([])

    @classmethod
    def get_spark_command(cls, **kwargs):
        c = cls.get_spark_call(**kwargs) + cls.get_args(**kwargs)
        return c

    def run_spark_command(self, **kwargs):
        return subprocess.check_call(
            self.get_spark_command(**self.args), **kwargs)


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
