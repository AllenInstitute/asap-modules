#!/usr/bin/env python

from marshmallow import post_load

import argschema
from argschema.fields import (Str, OutputDir, Int, Boolean, Float,
                              List, InputDir, InputFile, Dict, Nested)
from rendermodules.module.schemas import RenderClientParameters


class MaterializedBoxParameters(argschema.schemas.DefaultSchema):
    stack = Str(required=True, description=(""))
    rootDirectory = OutputDir(required=True, description=(""))
    width = Int(required=True, description="")
    height = Int(required=True, description="")
    maxLevel = Int(required=False, default=0, description="")
    fmt = Str(required=False)  # TODO validate to allow PNG, TIF(F?), JPG
    maxOverviewWidthAndHeight = Int(required=False, description=(""))
    skipInterpolation = Boolean(required=False, description=(""))
    binaryMask = Boolean(required=False, description=(""))
    label = Boolean(required=False, description=(""))
    createIGrid = Boolean(required=False, description=(""))
    forceGeneration = Boolean(required=False, description=(""))
    renderGroup = Int(required=False, description=(""))
    numberOfRenderGroups = Int(required=False, description=(""))


class ZRangeParameters(argschema.schemas.DefaultSchema):
    minZ = Int(required=False)
    maxZ = Int(required=False)


class RenderWebServiceParameters(argschema.schemas.DefaultSchema):
    baseDataUrl = Str(required=False)
    owner = Str(required=False)
    project = Str(required=False)


class RenderParametersRenderWebServiceParameters(RenderWebServiceParameters):
    render = Nested(
        RenderClientParameters, only=['owner', 'project', 'host', 'port'],
        required=False)

    @post_load
    def validate_options(self, data):
        # fill in with render parameters if they are defined
        if data.get('owner') is None:
            data['owner'] = data['render']['owner']
        if data.get('project') is None:
            data['project'] = data['render']['project']
        if data.get('baseDataUrl') is None:
            data['baseDataUrl'] = '{host}{port}/render-ws/v1'.format(
                host=(data['render']['host']
                      if data['render']['host'].startswith(
                      'http') else 'http://{}'.format(data['render']['host'])),
                port=('' if data['render']['port'] is None else ':{}'.format(
                      data['render']['port'])))


class SparkParameters(argschema.schemas.DefaultSchema):
    masterUrl = Str(required=True, description=(""))
    jarfile = Str(required=True, description=(""))
    className = Str(required=True, description=(""))
    driverMemory = Str(required=False, default='6g', description=(""))
    # memory = Str(required=False, defaut='6g', description=(""))
    sparkhome = InputDir(required=True, description=(""))
    spark_files = List(InputFile, required=False, description=(""))
    spark_conf = Dict(required=False, description=(""))


class MaterializeSectionsParameters(
        argschema.ArgSchema, MaterializedBoxParameters,
        ZRangeParameters, RenderParametersRenderWebServiceParameters,
        SparkParameters):
    cleanUpPriorRun = Boolean(required=False)
    explainPlan = Boolean(required=False)
    maxImageCacheGb = Float(required=False, default=2.0)  # TODO see Eric's
    zValues = List(Int, required=False)


class MaterializeSectionsOutput(argschema.schemas.DefaultSchema):
    zValues = List(Int, required=True)
    rootDirectory = InputDir(required=True)
    materializedDirectory = InputDir(required=True)
