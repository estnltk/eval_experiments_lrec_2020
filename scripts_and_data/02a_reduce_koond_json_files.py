#
#  (Optional step)
#
#  If you want to speed up the step 02b, then you can run this step
#  beforehand. It converts the original koondkorpus JSON files from 
#  the  legacy JSON format  to  the v1.6.4 JSON format, removes old 
#  annotations and saves as JSON files that only contain the raw 
#  textual content and metadata.
#
#  The scirpt runs without arguments, and it expects that the 
#  JSON files from the "Estonian Reference Corpus analysed with 
#  EstNLTK ver.1.6_b" are unpacked into the directory:
#      
#      koond_raw_json
#
#  You can obtain the original koondkorpus JSON files from:
#       https://doi.org/10.15155/1-00-0000-0000-0000-00156L
#


import os, os.path, json, re
from sys import argv

from tqdm import tqdm

from estnltk import Text
from estnltk.converters import from_json_file, to_json_file, dict_to_text, text_to_dict

use_progressbar = True

# input directory containing raw koondkorpus texts
raw_koond_json_dir = 'koond_raw_json'

# output directory
output_dir = 'koond_raw_json'
if not os.path.exists(output_dir):
    os.mkdir(output_dir)

# get list of all file names from raw koondkorpus dir
assert os.path.exists(raw_koond_json_dir)
all_koond_original_files = os.listdir( raw_koond_json_dir )
print()
print(' Total ',len(all_koond_original_files),' original koondkorpus json files to be processed.')
print()

doc_count = 0
# Iterate koondkorpus json files
for fname in tqdm(all_koond_original_files, ascii=True):
    # Load file
    fpath = os.path.join(raw_koond_json_dir, fname)
    legacy_dict = from_json_file(fpath)
    text_dict = text_to_dict(dict_to_text(legacy_dict))
    # Remove all annotation layers
    assert "layers" in text_dict.keys()
    del text_dict["layers"]
    text_dict["layers"] = []
    # Save dict to json file
    output_file = os.path.join(output_dir, fname)
    to_json_file(text_dict, output_file)
    doc_count += 1
print()
print(' Total koondkorpus documents processed: ',doc_count)
print('')
