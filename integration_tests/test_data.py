import os
from jinja2 import Environment, FileSystemLoader
import json
import tempfile

render_host = os.environ.get(
    'RENDER_HOST', 'renderservice')
render_port = os.environ.get(
    'RENDER_PORT', 8080)
render_test_owner = os.environ.get(
    'RENDER_TEST_OWNER', 'test'
)
client_script_location = os.environ.get(
    'RENDER_CLIENT_SCRIPTS',
    ('/shared/render/render-ws-java-client/'
     'src/main/scripts/'))

# rendermodules test compares with integer
try:
    render_port=int(render_port)
except ValueError:
    pass


render_params = {
    "host": render_host,
    "port": render_port,
    "owner": render_test_owner,
    "project": "test_project",
    "client_scripts": client_script_location
}

scratch_dir = os.environ.get(
    'SCRATCH_DIR', '/var/www/render/scratch/')
try:
    os.makedirs(scratch_dir)
except OSError as e:
    pass

log_dir = os.environ.get(
    'LOG_DIR', '/allen/aibs/pipeline/image_processing/volume_assembly/logs/')

try:
    os.makedirs(log_dir)
except OSError as e:
    pass

example_dir = os.path.join(os.path.dirname(__file__), 'test_files')
example_env = Environment(loader=FileSystemLoader(example_dir))

TEST_DATA_ROOT = os.environ.get(
    'RENDER_TEST_DATA_ROOT', '/allen/aibs/pipeline/image_processing/volume_assembly')

FIJI_PATH = os.environ.get(
    'FIJI_PATH', '/allen/aibs/pipeline/image_processing/volume_assembly/Fiji.app')

#ROUGH_SOLVER_EXECUTABLE = os.environ.get(
#    'ROUGH_SOLVER_EXECUTABLE',
#    '/allen/aibs/pipeline/image_processing/volume_assembly/EM_aligner/matlab_compiled/do_rough_alignment')


def render_json_template(env, template_file, **kwargs):
    template = env.get_template(template_file)
    d = json.loads(template.render(**kwargs))
    return d


# test data for dataimport testing
METADATA_FILE = os.path.join(example_dir, 'TEMCA_mdfile.json')

MIPMAP_TILESPECS_JSON = render_json_template(example_env, 'mipmap_tilespecs.json',
                                             test_data_root=TEST_DATA_ROOT)

cons_ex_tilespec_json = render_json_template(example_env, 'cycle1_step1_acquire_tiles.json',
                                             test_data_root=TEST_DATA_ROOT)

cons_ex_transform_json = render_json_template(example_env,  'cycle1_step1_acquire_transforms.json',
                                              test_data_root=TEST_DATA_ROOT)

multiplicative_correction_example_dir = os.path.join(
    TEST_DATA_ROOT, 'intensitycorrection_test_data')

MULTIPLICATIVE_INPUT_JSON = render_json_template(example_env, 'intensity_correction_template.json',
                                                 test_data_root=TEST_DATA_ROOT)
# lc_example_dir = os.environ.get('RENDER_MODULES_LC_TEST_DATA',
#     'allen/aibs/pipeline/image_processing/volume_assembly/lc_test_data/')


calc_lens_parameters = render_json_template(example_env, 'calc_lens_correction_parameters.json',
                                            test_data_root=TEST_DATA_ROOT,
                                            fiji_path=FIJI_PATH,
                                            test_output=tempfile.mkdtemp())

TILESPECS_NO_LC_JSON = render_json_template(example_env, 'test_noLC.json',
                                            test_data_root=TEST_DATA_ROOT)
TILESPECS_LC_JSON = render_json_template(example_env, 'test_LC.json',
                                         test_data_root=TEST_DATA_ROOT)

# materialization testing
MATERIALIZE_BOX_JSON = render_json_template(
    example_env, 'materialize_sections_test_data.json',
    test_data_root=TEST_DATA_ROOT)


# rough alignment test data
rough_align_test_data_dir = os.path.join(TEST_DATA_ROOT,
                                        'rough_align_test_data')
RAW_STACK_INPUT_JSON = render_json_template(example_env, 'raw_tile_specs_for_em_montage.json',
                                            test_data_root=TEST_DATA_ROOT)

MATLAB_SOLVER_PATH = os.environ.get('MATLAB_SOLVER_PATH',
    '/allen/aibs/pipeline/image_processing/volume_assembly/EMAligner/dev/allen_templates')
#MATLAB_SOLVER_PATH='/allen/aibs/pipeline/image_processing/volume_assembly/EM_aligner/allen_templates/'
MONTAGE_SOLVER_BIN = os.path.join(MATLAB_SOLVER_PATH,'run_em_solver.sh')
RENDER_SPARK_JAR = os.environ['RENDER_SPARK_JAR']
SPARK_HOME = os.environ.get('SPARK_HOME','/shared/spark')
montage_project = "em_montage_test"
montage_collection = "test_montage_collection"
montage_z = 1015
log4propertiesfile = os.environ.get("SPARK_LOG_PROPERTIES",
    "/allen/aibs/pipeline/image_processing/volume_assembly/utils/spark/conf/log4j.properties.template")
pbs_template=os.environ.get("PBS_TEMPLATE",
    "/allen/aibs/pipeline/image_processing/volume_assembly/utils/code/spark_submit/spinup_spark.pbs")

test_pointmatch_parameters = render_json_template(example_env,
    'point_match_parameters.json',
    render_host = render_host,
    render_port = render_port,
    render_project = montage_project,
    render_owner = render_test_owner,
    render_client_scripts = client_script_location,
    spark_log_dir = tempfile.mkdtemp(),
    render_spark_jar = RENDER_SPARK_JAR,
    spark_master_url = os.environ['SPARK_MASTER_URL'],
    spark_home = SPARK_HOME,
    point_match_collection = montage_collection,
    spark_logging_properties = log4propertiesfile)

test_pointmatch_parameters_qsub = render_json_template(example_env,
    'point_match_parameters_qsub.json',
    render_host = render_host,
    render_port = render_port,
    render_project = montage_project,
    render_owner = render_test_owner,
    render_client_scripts = client_script_location,
    spark_log_dir = tempfile.mkdtemp(),
    render_spark_jar = RENDER_SPARK_JAR,
    spark_home = SPARK_HOME,
    point_match_collection = montage_collection,
    spark_logging_properties = log4propertiesfile,
    pbs_template=pbs_template)

test_em_montage_parameters = render_json_template(example_env,
    'run_montage_job_for_section_template.json',
    render_host = render_host,
    render_port = render_port,
    render_project = montage_project,
    render_owner = render_test_owner,
    render_client_scripts = client_script_location,
    em_solver_bin = MONTAGE_SOLVER_BIN,
    scratch_dir = tempfile.mkdtemp(),
    point_match_collection = montage_collection,
    montage_z = montage_z)

# EM Montage QC data
PRESTITCHED_STACK_INPUT_JSON = render_json_template(example_env, 'em_montage_qc_pre_tilespecs.json',
                                                    test_data_root=TEST_DATA_ROOT)

POSTSTITCHED_STACK_INPUT_JSON = render_json_template(example_env, 'em_montage_qc_post_tilespecs.json',
                                                    test_data_root=TEST_DATA_ROOT)

MONTAGE_QC_POINT_MATCH_JSON = render_json_template(example_env, 'em_montage_qc_point_matches.json')

montage_qc_project = "em_montage_qc_test"

# Point match optimization
PT_MATCH_STACK_TILESPECS = render_json_template(example_env, 'pt_match_optimization_tilespecs.json',
                                                test_data_root=TEST_DATA_ROOT)


