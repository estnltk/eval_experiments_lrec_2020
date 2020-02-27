#
#   Documents from web13 and wiki17 subcorpora do not need 
#  corrections. However, in order to make the processing chain 
#  uniform, we convert these documents from .vert format to 
#  JSON format.
#
#  The scirpt runs without arguments, and it expects that the 
#  the current directory contains unpacked ENC 2017 files:
#
#      estonian_nc17.vert.01
#      estonian_nc17.vert.02
#      estonian_nc17.vert.03
#      ...
#      estonian_nc17.vert.08
#
#   You can obtain ENC 2017 files from:
#       https://doi.org/10.15155/3-00-0000-0000-0000-071E7L
#


import os, os.path, json, re
from sys import argv
from random import randint
import shutil

from tqdm import tqdm

from estnltk import Text
from estnltk.converters import text_to_json, json_to_text

from enc2017_extra_utils import create_enc_filename_stub
from enc2017_extra_utils import IndexBasedENC2017DocIterator
from enc2017_extra_utils import fetch_text_category
from enc2017_extra_utils import get_partition_info_from_sys_argv

use_progressbar = True

# selection index 
enc_index_file = 'enc2017_index_random_5x2000000.txt'

# Where to put plain text files
output_dir = '_plain_texts_json'
if not os.path.exists(output_dir):
    os.mkdir(output_dir)

# Skip koondkorpus' .vert files ( because we only want web13 and wiki17 )
vert_skip_list = ['estonian_nc17.vert.01', 'estonian_nc17.vert.02', 'estonian_nc17.vert.03']

partition = get_partition_info_from_sys_argv( argv )

# Iterate over vert files
iterator = IndexBasedENC2017DocIterator('.', enc_index_file, vert_skip_list=vert_skip_list, \
                                        partition=partition, no_tokenization=True, \
                                        use_progressbar=use_progressbar, verbose=True, take_only_first=-1)
copied_files = 0
for doc in iterator.iterate():
    fname_stub = create_enc_filename_stub( doc )
    if fname_stub.startswith(('web13', 'wiki17')):
        outfname = fname_stub+'.json'
        # Write out Text object
        fpath = os.path.join( output_dir, outfname )
        text_to_json( doc, file=fpath )
        copied_files += 1
print()
print(' Total {} files copied.'.format(copied_files) )
print()
