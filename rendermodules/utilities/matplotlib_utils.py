# imports needed for rough_align_qc
import os
import matplotlib
if os.environ.get('DISPLAY', '') == '':
    matplotlib.use('Agg')

import matplotlib.pyplot as plt
import mpld3
import matplotlib as mpl
from matplotlib.backends.backend_pdf import PdfPages
