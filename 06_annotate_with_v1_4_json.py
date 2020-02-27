#
#  Annotates json files in the input directory with EstNLTK v1.4
#
#  The script runs without arguments, provided that required 
#  input folder is available.
#

import os, os.path, json, codecs

import pkg_resources

estnltk_version = ''
try:
    estnltk_dist = pkg_resources.get_distribution("estnltk")
    estnltk_version = estnltk_dist.version
except:
    raise Exception('(!) Unable to load estnltk module ...')
assert estnltk_version is not None and estnltk_version.startswith('1.4.1'), \
    '(!) Wrong estnltk version! Use estnltk version 1.4.1 for running this code.'

# input dir
input_dir = '_plain_texts_json'

# output dir
output_dir = 'v1_4_selected_annotated'

if not os.path.exists(output_dir):
    os.mkdir(output_dir)

from datetime import datetime

from estnltk import Text
from estnltk.corpus import read_document, write_document

doc_count = 0
startTime = datetime.now()
for fname in os.listdir(input_dir):
    if fname.endswith('.json'):
        in_fpath = os.path.join( input_dir, fname )
        with open(in_fpath, 'r', encoding='utf-8') as in_f:
            text_dict = json.load(fp=in_f)
        assert 'text' in text_dict
        assert 'meta' in text_dict
        doc = Text(text_dict['text'])
        doc['meta'] = {}
        for k in text_dict['meta'].keys():
            doc['meta'][k] = text_dict['meta'][k]
        doc.tag_analysis()
        #print(list(doc.keys()))
        out_fpath = os.path.join( output_dir, fname )
        write_document( doc, out_fpath )
        doc_count += 1
        #if doc_count > 10:
        #    break
print()
print(' Docs annotated total:  ', doc_count)
print(' Total processing time: {}'.format( datetime.now()-startTime ) )
