#
#  Annotates given documents for v1_6 morph_analysis and saves the 
#  results as JSON format files.
#
#  The script runs without arguments, provided that required 
#  input folder is available.
#
#  In order to speed up the process, it is recommended to launch 
#  multiple instances of the process at the same time on different 
#  partitions of the corpus, e.g.
#       
#       python  09_annotate_v1_6_morph.py   1,2 
#       python  09_annotate_v1_6_morph.py   2,2 
#       

import os, os.path, re
from sys import argv

from enc2017_extra_utils import create_enc_filename_stub
from enc2017_extra_utils import EstnltkJsonDocIterator
from enc2017_extra_utils import get_partition_info_from_sys_argv

from estnltk import Text
from estnltk.converters import text_to_json, json_to_text

partition = get_partition_info_from_sys_argv( argv )

remove_redundant_layers = True

use_progressbar = True

# input dir 
input_dir  = 'segmentation_annotated'
assert os.path.exists(input_dir), '(!) Input dir {!r} not available'.format(input_dir)

# output dir
output_dir = 'estnltk_morph_annotated'
if not os.path.exists(output_dir):
    os.mkdir(output_dir)

skip_list = []
doc_count = 0
iterator = EstnltkJsonDocIterator(input_dir, skip_list=skip_list, prefixes=[], partition=partition,\
                                             use_progressbar=use_progressbar, verbose=True, take_only_first=-1)
for doc in iterator.iterate():
    doc_src = doc.meta['src'].lower() if 'src' in doc.meta else '--'
    fname_stub = create_enc_filename_stub( doc )
    assert 'words' in doc.layers.keys(), "(!) Annotated doc {} misses 'words'".format(fname_stub)
    assert 'sentences' in doc.layers.keys(), "(!) Annotated doc {} misses 'sentences'".format(fname_stub)
    assert 'compound_tokens' in doc.layers.keys(), "(!) Annotated doc {} misses 'compound_tokens'".format(fname_stub)
    # Add default morph_analysis
    doc.tag_layer(['morph_analysis'])
    # Remove redundant segmentation layers (to reduce space)
    if remove_redundant_layers:
        if 'original_words' in doc.layers.keys():
            del doc.original_words
        if 'original_sentences' in doc.layers.keys():
            del doc.original_sentences
        if 'original_paragraphs' in doc.layers.keys():
            del doc.original_paragraphs
        # Regular layers
        if 'compound_tokens' in doc.layers.keys():
            del doc.compound_tokens
        if 'tokens' in doc.layers.keys():
            del doc.tokens
        if 'sentences_quot_fix' in doc.layers.keys():
            del doc.sentences_quot_fix
        if 'sentences' in doc.layers.keys():
            del doc.sentences
        # Flat layers
        if 'v1_4_words' in doc.layers.keys():
            del doc.v1_4_words
        if 'v1_4_sentences' in doc.layers.keys():
            del doc.v1_4_sentences
        if 'v1_4_morph_analysis' in doc.layers.keys():
            del doc.v1_4_morph_analysis
    fpath = os.path.join(output_dir, fname_stub + '.json')
    text_to_json( doc, fpath )
    doc_count += 1

print(' Docs annotated total:  ', doc_count)