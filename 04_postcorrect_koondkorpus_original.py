#
#   At this point, koondkorpus texts obtained from the JSON 
#  corpus contain double newlines at places of paragraph endings,
#  and single newlines at places of sentence endings.
#   However, the information about sentence endings is not gold 
#  standard, but based on some very old sentence tokenization 
#  algorithm and may be misleading. So, we need to remove it.
#
#   This script post-processes the plain texts corpus, and 
#  and replaces every single newline with a regular whitespace
#  character. Double newlines will remain as they are.
#
#  The script runs without arguments, provided that required 
#  input folder is available.
#

import os, os.path, json, re
from sys import argv
from collections import defaultdict

from tqdm import tqdm

from estnltk import Text
from estnltk.converters import text_to_json, json_to_text

from enc2017_extra_utils import fetch_text_category

# input directory containing original koondkorpus texts:
raw_koond_json_dir = '_plain_texts_json'

# output directory
output_dir = '_plain_texts_json'
if not os.path.exists(output_dir):
    os.mkdir(output_dir)

broken_files = []
c = 0
# filter the corpus: only koondkorpus' files need correcting
filtered_files_list = [f for f in os.listdir(raw_koond_json_dir) if f.endswith('.json') and f.startswith('nc_')]
for fname in tqdm(filtered_files_list, ascii=True):
    if fname.endswith('.json'):
        fpath = os.path.join( raw_koond_json_dir, fname )
        try:
            original_text = json_to_text(file=fpath)
            doc_category = fetch_text_category( original_text )
            # Keep double newlines, but replace regular newlines with spaces
            mod_text = original_text.text
            mod_text = mod_text.replace('\n\n', '<|*|[NNN]|*|>')
            mod_text = mod_text.replace('\n', ' ')
            mod_text = mod_text.replace('<|*|[NNN]|*|>', '\n\n')
            new_original_text = Text( mod_text )
            # Carry over metadata
            for key in original_text.meta.keys():
                new_original_text.meta[key] = original_text.meta[key]
            fpath = os.path.join(output_dir, fname)
            text_to_json(new_original_text, file=fpath)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            print('Broken file:', fname)
            broken_files.append( fname )
            original_text = None
        c += 1
print('Total broken files: ',len(broken_files),'/',c)
print()
