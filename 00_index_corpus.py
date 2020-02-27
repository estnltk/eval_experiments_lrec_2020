#
#  Skript for creating document index for the ENC_2017 corpus.
#  The index is a basis for making a random selection from 
#  the corpus, and later it is used as a guide in processing 
#  the corpus. 
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
#  As a result, the index file 'enc2017_index.txt' will be 
#  created;
# 

import re
import os, os.path

from estnltk import Text
from estnltk.corpus_processing.parse_enc2017 import parse_enc2017_file_iterator
from enc2017_extra_utils import load_ettenten_texttypes
from enc2017_extra_utils import enc2017fname_pat
from enc2017_extra_utils import ENC_INDEX_DELIMITER as delimiter 

use_progressbar = True

#================================================
#   Load etTenTen13 texttypes ( if possible )
#================================================

ettenten_texttypes_fname = 'etTenTen.doc_liigitus_en'
ettenten_info = {}
if os.path.exists(ettenten_texttypes_fname):
    ettenten_info = load_ettenten_texttypes( 'etTenTen.doc_liigitus_en' )
    print('Loaded info about {} etTenTen13 urls.'.format( len(ettenten_info.keys() ) ))
else:
    print('(!) Warning: Unable to load etTenTen13 texttypes from the file {!r}'.format(ettenten_texttypes_fname))
print()

# NB! 'etTenTen.doc_liigitus_en' is a big file and 
# not distributed in this repository.
# Please contact us if you need to obtain it.

#================================================
#   Extract information for the index
#================================================

def extract_indexable_info( text ):
    assert isinstance( text, Text )
    # Meta info
    doc_id    = text.meta.get('id', '_')
    subdoc_id = text.meta.get('subdoc_id', '_')
    src       = text.meta.get('src', '_')
    filename_or_url = text.meta.get('filename', '_')
    if filename_or_url == '_':
        filename_or_url = text.meta.get('url', '_')
    is_balanced = text.meta.get('balanced', '_')
    is_balanced = 'balanced' if is_balanced == 'yes' else '_'
    texttype = text.meta.get('texttype', '_')
    # Text counts
    chars = len(text.text)
    words = len(text.original_words)
    sentences = len(text.original_sentences)
    return [src, doc_id, subdoc_id, texttype, is_balanced, filename_or_url, words, chars, sentences]


#================================================
#   Process whole corpus and create index
#================================================

# Create anew index file
enc_index_file = 'enc2017_index.txt'
with open(enc_index_file, 'w', encoding='utf-8') as out_f:
    header = ['file', 'src', 'doc_id', 'subdoc_id', 'texttype', 'balanced', 'src_file_or_url', 'words', 'chars', 'sentences']
    out_f.write( delimiter.join(header) )
    out_f.write('\n')

text_count = 0
enc_index = []
enc_file_count = 0
for fname in sorted(os.listdir('.')):
    if enc2017fname_pat.match(fname):
        print('Processing ',fname,'...')
        enc_file_count += 1
        # iterate over corpus and extract Text objects one-by-one
        for text in parse_enc2017_file_iterator( fname, 
                                                 line_progressbar='ascii' if use_progressbar else None, 
                                                 tokenization='preserve_partially' ):
            # Fix web13 texttype
            if text.meta.get('src', '') == 'web13' and text.meta.get('url', '') in ettenten_info:
                text.meta['texttype'] = ettenten_info[ text.meta.get('url', '') ][1]
            index_entry = extract_indexable_info( text )
            index_entry = [fname] + index_entry
            enc_index.append( index_entry )
            # Flush the buffer
            if len(enc_index) > 2500:
                # Write entries into file
                with open(enc_index_file, 'a', encoding='utf-8') as out_f:
                    for items in enc_index:
                        out_f.write( delimiter.join( [str(i) for i in items] ) )
                        out_f.write('\n')
                enc_index = []
            text_count += 1
            #if text_count > 5:
            #    break
        # Flush the buffer
        if len(enc_index) > 0:
            # Write entries into file
            with open(enc_index_file, 'a', encoding='utf-8') as out_f:
                for items in enc_index:
                    out_f.write(delimiter.join( [str(i) for i in items] ) )
                    out_f.write('\n')
            enc_index = []

print()
print('Files processed: ', enc_file_count)
print('Docs processed:  ', text_count)

