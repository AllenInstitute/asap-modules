import os
from jinja2 import Environment, FileSystemLoader
import json
import tempfile

pool_size = os.environ.get('RENDERMODULES_POOL_SIZE', 5)

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
    render_port = int(render_port)
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

TEST_DATA_ROOT = os.environ.get(
    'RENDER_TEST_DATA_ROOT',
    '/allen/aibs/pipeline/image_processing/volume_assembly')

log_dir = os.environ.get(
    'LOG_DIR',
    os.path.join(TEST_DATA_ROOT, 'logs'))

try:
    os.makedirs(log_dir)
except OSError as e:
    pass

example_dir = os.path.join(os.path.dirname(__file__), 'test_files')
example_env = Environment(loader=FileSystemLoader(example_dir))


FIJI_PATH = os.environ.get(
    'FIJI_PATH',
    os.path.join(TEST_DATA_ROOT, 'Fiji.app'))


# ROUGH_SOLVER_EXECUTABLE = os.environ.get(
#         'ROUGH_SOLVER_EXECUTABLE',
#         os.path.join(
#             TEST_DATA_ROOT,
#             'EM_aligner/matlab_compiled/do_rough_alignment'))


def render_json_template(env, template_file, **kwargs):
    template = env.get_template(template_file)
    d = json.loads(template.render(**kwargs))
    return d


# test data for dataimport testing
METADATA_FILE = os.path.join(example_dir, 'TEMCA_mdfile.json')

MIPMAP_TILESPECS_JSON = render_json_template(
        example_env,
        'mipmap_tilespecs_ref.json',
        test_data_root=TEST_DATA_ROOT)
MIPMAP_TRANSFORMS_JSON = render_json_template(
        example_env,
        'mipmap_ref_tforms.json',
        test_data_root=TEST_DATA_ROOT)

cons_ex_tilespec_json = render_json_template(
        example_env,
        'cycle1_step1_acquire_tiles.json',
        test_data_root=TEST_DATA_ROOT)

cons_ex_transform_json = render_json_template(
        example_env,
        'cycle1_step1_acquire_transforms.json',
        test_data_root=TEST_DATA_ROOT)

multiplicative_correction_example_dir = os.path.join(
    TEST_DATA_ROOT, 'intensitycorrection_test_data')

MULTIPLICATIVE_INPUT_JSON = render_json_template(
        example_env,
        'intensity_correction_template.json',
        test_data_root=TEST_DATA_ROOT)
# lc_example_dir = os.environ.get('RENDER_MODULES_LC_TEST_DATA',
#     'allen/aibs/pipeline/image_processing/volume_assembly/lc_test_data/')


calc_lens_parameters = render_json_template(
        example_env,
        'calc_lens_correction_parameters.json',
        test_data_root=TEST_DATA_ROOT,
        fiji_path=FIJI_PATH,
        test_output=tempfile.mkdtemp())

TILESPECS_NO_LC_JSON = render_json_template(
        example_env,
        'test_noLC.json',
        test_data_root=TEST_DATA_ROOT)
TILESPECS_LC_JSON = render_json_template(
        example_env,
        'test_LC.json',
        test_data_root=TEST_DATA_ROOT)

# materialization testing
MATERIALIZE_BOX_JSON = render_json_template(
    example_env, 'materialize_sections_test_data.json',
    test_data_root=TEST_DATA_ROOT)

# Swap Zs json files
swap_z_tspecs1 = render_json_template(example_env, 'swap_z_tspecs1.json')

swap_z_tspecs2 = render_json_template(example_env, 'swap_z_tspecs2.json')

swap_pt_matches1 = render_json_template(example_env, 'swap_pt_matches1.json')

swap_pt_matches2 = render_json_template(example_env, 'swap_pt_matches2.json')

RAW_STACK_INPUT_JSON = render_json_template(
        example_env,
        'raw_tile_specs_for_em_montage.json',
        test_data_root=TEST_DATA_ROOT)

MATLAB_SOLVER_PATH = os.environ.get(
        'MATLAB_SOLVER_PATH',
        os.path.join(TEST_DATA_ROOT, 'EMAligner/dev/allen_templates'))

MONTAGE_SOLVER_BIN = os.path.join(MATLAB_SOLVER_PATH, 'run_em_solver.sh')
RENDER_SPARK_JAR = os.environ['RENDER_SPARK_JAR']
SPARK_HOME = os.environ.get('SPARK_HOME', '/shared/spark')
montage_project = "em_montage_test"
montage_collection = "test_montage_collection"
montage_z = 1015
log4propertiesfile = os.environ.get(
        "SPARK_LOG_PROPERTIES",
        os.path.join(
            TEST_DATA_ROOT,
            'utils/spark/conf/log4j.properties.template'))
pbs_template = os.environ.get(
        "PBS_TEMPLATE",
        os.path.join(
            TEST_DATA_ROOT,
            'utils/code/spark_submit/spinup_spark.pbs'))

test_pointmatch_parameters = render_json_template(
        example_env,
        'point_match_parameters.json',
        render_host=render_host,
        render_port=render_port,
        render_project=montage_project,
        render_owner=render_test_owner,
        render_client_scripts=client_script_location,
        spark_log_dir=tempfile.mkdtemp(),
        render_spark_jar=RENDER_SPARK_JAR,
        spark_master_url=os.environ['SPARK_MASTER_URL'],
        spark_home=SPARK_HOME,
        point_match_collection=montage_collection,
        spark_logging_properties=log4propertiesfile)

test_pointmatch_parameters_qsub = render_json_template(
        example_env,
        'point_match_parameters_qsub.json',
        render_host=render_host,
        render_port=render_port,
        render_project=montage_project,
        render_owner=render_test_owner,
        render_client_scripts=client_script_location,
        spark_log_dir=tempfile.mkdtemp(),
        render_spark_jar=RENDER_SPARK_JAR,
        spark_home=SPARK_HOME,
        point_match_collection=montage_collection,
        spark_logging_properties=log4propertiesfile,
        pbs_template=pbs_template)

test_em_montage_parameters = render_json_template(
        example_env,
        'run_montage_job_for_section_template.json',
        render_host=render_host,
        render_port=render_port,
        render_project=montage_project,
        render_owner=render_test_owner,
        render_client_scripts=client_script_location,
        em_solver_bin=MONTAGE_SOLVER_BIN,
        scratch_dir=tempfile.mkdtemp(),
        point_match_collection=montage_collection,
        montage_z=montage_z)

# rough alignment parameters' data
ROUGH_MONTAGE_TILESPECS_JSON = render_json_template(
    example_env, 'rough_align_montage_tilespecs_ref.json',
    test_data_root=TEST_DATA_ROOT)
ROUGH_MONTAGE_TRANSFORM_JSON = render_json_template(
    example_env, 'rough_align_montage_ref_transforms.json',
    test_data_root=TEST_DATA_ROOT)

ROUGH_DS_TEST_TILESPECS_JSON = render_json_template(
        example_env,
        'rough_align_downsample_test_tilespecs.json',
        test_data_root=TEST_DATA_ROOT)

ROUGH_POINT_MATCH_COLLECTION = render_json_template(
        example_env, 'rough_align_point_matches.json')

ROUGH_MAPPED_PT_MATCH_COLLECTION = render_json_template(
        example_env, 'rough_align_mapped_point_matches.json')

rough_project = "rough_align_test"

ROUGH_MASK_DIR = os.path.join(
        TEST_DATA_ROOT,
        'em_modules_test_data/rough_align_test_data/masks')

test_rough_parameters = render_json_template(
        example_env,
        'run_rough_job_for_chunk_template.json',
        render_host=render_host,
        render_port=render_port,
        render_project=rough_project,
        render_owner=render_test_owner,
        render_client_scripts=client_script_location,
        em_solver_bin=MONTAGE_SOLVER_BIN,
        scratch_dir=tempfile.mkdtemp(),
        firstz=1020,
        lastz=1022)

rough_solver_example = render_json_template(
        example_env, 'solver_montage_test.json',
        render_project = rough_project,
        render_host=render_host,
        render_owner=render_test_owner,
        render_port=render_port,
        mongo_port=os.environ.get('MONGO_PORT', 27017),
        render_mongo_host=os.environ.get('RENDER_MONGO_HOST', 'localhost'),
        render_output_owner=render_test_owner,
        render_client_scripts=client_script_location,
        solver_output_dir=tempfile.mkdtemp())

test_rough_parameters_python = render_json_template(
        example_env,
        'rough_align_python_input.json',
        render_host=render_host,
        render_port=render_port,
        render_project=rough_project,
        render_owner=render_test_owner,
        render_client_scripts=client_script_location,
        firstz=1020,
        lastz=1022)

apply_rough_alignment_example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "Tests",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "montage_stack": "rough_test_montage_stack",
    "prealigned_stack": "rough_test_montage_stack",
    "lowres_stack": "rough_test_downsample_rough_stack",
    "output_stack": "rough_test_rough_stack",
    "tilespec_directory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch/rough/jsonFiles",
    "map_z": "False",
    "new_z": [251, 252, 253],
    "consolidate_transforms": "True",
    "old_z": [1020, 1021, 1022],
    "scale": 0.1,
    "apply_scale": "False",
    "pool_size": 20
}

# EM Montage QC data
PRESTITCHED_STACK_INPUT_JSON = render_json_template(
        example_env,
        'em_montage_qc_pre_tilespecs.json',
        test_data_root=TEST_DATA_ROOT)

POSTSTITCHED_STACK_INPUT_JSON = render_json_template(
        example_env,
        'em_montage_qc_post_tilespecs.json',
        test_data_root=TEST_DATA_ROOT)

MONTAGE_QC_POINT_MATCH_JSON = render_json_template(
        example_env,
        'em_montage_qc_point_matches.json')

montage_qc_project = "em_montage_qc_test"

# Point match optimization
PT_MATCH_STACK_TILESPECS = render_json_template(
        example_env,
        'pt_match_optimization_tilespecs.json',
        test_data_root=TEST_DATA_ROOT)


# Solver testing
solver_montage_parameters = render_json_template(
        example_env,
        'solver_montage_test.json',
        render_project="solver_montage_project",
        render_host=render_host,
        render_owner=render_test_owner,
        render_port=render_port,
        mongo_port=os.environ.get('MONGO_PORT', 27017),
        render_mongo_host=os.environ.get('RENDER_MONGO_HOST', 'localhost'),
        render_output_owner=render_test_owner,
        render_client_scripts=client_script_location,
        solver_output_dir=tempfile.mkdtemp())

FUSION_TILESPEC_JSON = render_json_template(
    example_env, 'fusion_test_tilespecs_ref.json',
    test_data_root=TEST_DATA_ROOT)

FUSION_TRANSFORM_JSON = render_json_template(
    example_env, 'fusion_test_tform_ref.json', test_data_root=TEST_DATA_ROOT)
