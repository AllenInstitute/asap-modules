import renderapi
from rendermodules.stack.consolidate_transforms import ConsolidateTransforms
from test_data import render_host,render_port,client_script_location
import pytest

@pytest.fixture(scope='module')
def test_consolidate_transforms():
    