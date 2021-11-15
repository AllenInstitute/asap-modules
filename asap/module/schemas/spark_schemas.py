import argschema
from argschema.fields import Str, InputDir, List, InputFile, Dict


class SparkOptions(argschema.schemas.DefaultSchema):
    jarfile = Str(required=True, description=(
        "spark jar to call java spark command"))
    className = Str(required=True, description=(
        "spark class to call"))
    driverMemory = Str(required=False, default='6g', description=(
        "spark driver memory (important for local spark)"))
    memory = Str(
        required=False,
        description="Memory required for spark job")
    sparkhome = InputDir(required=True, description=(
        "Spark home directory containing bin/spark_submit"))
    spark_files = List(InputFile, required=False, description=(
        "list of spark files to add to the spark submit command"))
    spark_conf = Dict(required=False, description=(
        "dictionary of key value pairs to add to spark_submit "
        "as --conf key=value"))


class SparkParameters(SparkOptions):
    masterUrl = Str(required=True, description=(
        "spark master url.  For local execution local[num_procs,num_retries]"))
