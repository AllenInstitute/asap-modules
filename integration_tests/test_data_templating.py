from jinja2 import Environment, FileSystemLoader
import os

env = Environment(loader=FileSystemLoader('test_files'))
calc_lens_template = env.get_template('calc_lens_correction_parameters.json')
test_data_root = os.environ.get('RENDER_TEST_DATA_ROOT','/allen/aibs/pipeline/image_processing/volume_assembly')
fiji_installation = 
calc_lens_parameters = test_data_root.render(test_data_root=test_data_root, 
output_from_parsed_template = template.render(foo='Hello World!')
print output_from_parsed_template