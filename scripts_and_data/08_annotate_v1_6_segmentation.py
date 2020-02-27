#
#  Annotates given documents for v1_6 segmentation and saves the 
#  results as JSON format documents. 
#  By default, overwrites existing documents.
#
#  The script runs without arguments, provided that required 
#  input folder is available.
#
#  In order to speed up the process, it is recommended to launch 
#  multiple instances of the process at the same time on different 
#  partitions of the corpus, e.g.
#       
#       python  08_annotate_v1_6_segmentation.py  (1,2)
#       python  08_annotate_v1_6_segmentation.py  (2,2)
#       

import os, os.path, json, codecs, re
from collections import defaultdict
from sys import argv

from enc2017_extra_utils import create_enc_filename_stub
from enc2017_extra_utils import EstnltkJsonDocIterator
from enc2017_extra_utils import get_partition_info_from_sys_argv

from segm_eval_utils import create_flat_estnltk_segmentation_layer

from estnltk import Text
from estnltk.converters import text_to_json
from estnltk.taggers import SentenceTokenizer
sentence_tokenizer_w_quot_fix = SentenceTokenizer( output_layer='sentences_quot_fix', \
                                                   fix_double_quotes_based_on_counts=True )

partition = get_partition_info_from_sys_argv( argv )

remove_redundant_layers = True

use_progressbar = True

# input dir (should already contain v1_4 annotations)
input_dir = 'segmentation_annotated'

# output dir
output_dir = 'segmentation_annotated'

if not os.path.exists(output_dir):
    os.mkdir(output_dir)

skip_list = []
doc_count = 0
prefixes  = []
iterator = EstnltkJsonDocIterator(input_dir, skip_list=skip_list, prefixes=prefixes, partition=partition,\
                                             use_progressbar=use_progressbar, verbose=True, take_only_first=-1)
for doc in iterator.iterate():
    doc_src = doc.meta['src'].lower() if 'src' in doc.meta else '--'
    fname_stub = create_enc_filename_stub( doc )
    # Add regular tokenization
    doc.tag_layer(['words', 'sentences'])
    # Add sentences with quotation fixes
    sentence_tokenizer_w_quot_fix.tag( doc )
    
    # Sanity check
    assert 'sentences' in doc.layers.keys()
    assert 'words' in doc.layers.keys()
    assert 'sentences_quot_fix' in doc.layers.keys()
    
    # Remove redundant non-flat layers (to reduce space)
    if remove_redundant_layers:
        if 'original_words' in doc.layers.keys():
            del doc.original_words
        if 'original_sentences' in doc.layers.keys():
            del doc.original_sentences
        if 'original_paragraphs' in doc.layers.keys():
            del doc.original_paragraphs

    # Output document
    fpath = os.path.join(output_dir, fname_stub + '.json')
    text_to_json( doc, fpath )
    doc_count += 1

print('Docs annotated total:  ', doc_count)
