#
# Finds diffs of v1.6 segmentation against v1.4 segmentations.
# Loads already annotated documents from the disk.
#
# The script runs without arguments, provided that required 
# input folder is available.
#

import os, os.path, json, codecs
from collections import defaultdict

from enc2017_extra_utils import create_enc_filename_stub
from enc2017_extra_utils import EstnltkJsonDocIterator
from enc2017_extra_utils import fetch_text_category

from segm_eval_utils import create_flat_estnltk_segmentation_layer
from segm_eval_utils import SegmentDiffSummarizer
from segm_eval_utils import group_continuous_diff_spans
from segm_eval_utils import format_diffs_string
from segm_eval_utils import write_formatted_diff_str_to_file


from estnltk import Text
from estnltk.converters import text_to_json, json_to_text
from estnltk.taggers import DiffTagger

remove_redundant_layers = True

use_progressbar = True

# Use quotation mark fixed sentences from estnltk
use_quot_fix = False

# Input dir (texts must have v1_6 and v1_4 segmentation annotations)
input_dir = 'segmentation_annotated'
assert os.path.exists(input_dir), '(!) Missing input dir {!r}'.format(input_dir)

# Output dir
output_dir = 'diffs_v1_4_segment'+('_estnltk_quot_fix' if use_quot_fix else '')
if not os.path.exists(output_dir):
    os.mkdir(output_dir)

words_diff_tagger = DiffTagger(layer_a='v1_4_words',
                         layer_b='v1_6_words_flat',
                         output_layer='words_diff_layer',
                         output_attributes=('span_status', ),
                         span_status_attribute='span_status')
sentences_diff_tagger = DiffTagger(layer_a='v1_4_sentences',
                         layer_b='v1_6_sentences_qfx_flat' if use_quot_fix else 'v1_6_sentences_flat',
                         output_layer='sentences_diff_layer',
                         output_attributes=('span_status', ),
                         span_status_attribute='span_status')

summarizer = SegmentDiffSummarizer('v1_4', 'v1_6')

words_gap_counter     = 0
sentences_gap_counter = 0
broken_docs = []
skip_list = []
doc_count = 0
prefixes  = []
iterator = EstnltkJsonDocIterator(input_dir, skip_list=skip_list, prefixes=prefixes, partition=None,\
                                             use_progressbar=use_progressbar, verbose=True, take_only_first=-1)
for doc in iterator.iterate():
    doc_src = doc.meta['src'].lower() if 'src' in doc.meta else '--'
    # 1) Load annotated text
    fname_stub = create_enc_filename_stub( doc )
    outfname = fname_stub+'.json'
    
    # 2) Create flat v1.6 segmentation layers
    assert 'sentences' in doc.layers.keys(), "(!) Annotated doc {} misses 'sentences'".format(fname_stub)
    assert 'words' in doc.layers.keys(), "(!) Annotated doc {} misses 'words'".format(fname_stub)
    assert 'sentences_quot_fix' in doc.layers.keys(), "(!) Annotated doc {} misses 'sentences_quot_fix'".format(fname_stub)
    
    create_flat_estnltk_segmentation_layer( doc, 'words', 'v1_6_words_flat', add_layer=True )
    create_flat_estnltk_segmentation_layer( doc, 'sentences', 'v1_6_sentences_flat', add_layer=True )
    create_flat_estnltk_segmentation_layer( doc, 'sentences_quot_fix' , 'v1_6_sentences_qfx_flat', add_layer=True )
    
    # Sanity check
    assert 'v1_4_words' in doc.layers.keys(), "(!) Annotated doc {} misses 'v1_4_words'".format(fname_stub)
    assert 'v1_4_sentences' in doc.layers.keys(), "(!) Annotated doc {} misses 'v1_4_sentences'".format(fname_stub)
    assert 'v1_4_morph_analysis' in doc.layers.keys(), "(!) Annotated doc {} misses 'v1_4_morph_analysis'".format(fname_stub)
    assert 'v1_6_words_flat' in doc.layers.keys(), "(!) Annotated doc {} misses 'v1_6_words_flat'".format(fname_stub)
    assert 'v1_6_sentences_flat' in doc.layers.keys(), "(!) Annotated doc {} misses 'v1_6_sentences_flat'".format(fname_stub)
    assert 'v1_6_sentences_qfx_flat' in doc.layers.keys(), "(!) Annotated doc {} misses 'v1_6_sentences_qfx_flat'".format(fname_stub)

    # 2) Find differences
    words_diff_tagger.tag( doc )
    sentences_diff_tagger.tag( doc )
    
    # Record statistics
    text_cat = fetch_text_category(doc)
    summarizer.record_from_diff_layer( 'words', doc['words_diff_layer'], text_cat )
    summarizer.record_from_diff_layer( 'sentences', doc['sentences_diff_layer'], text_cat )
    grouped_words = group_continuous_diff_spans( doc['words_diff_layer'] )
    grouped_sentences = group_continuous_diff_spans( doc['sentences_diff_layer'] )
    
    # Take out gaps in diffs:
    # a) words
    diff_str, words_gap_counter = format_diffs_string(doc, grouped_words, gap_counter=words_gap_counter, format='vertical')
    fpath = os.path.join(output_dir, '_word_diff_gaps.txt')
    write_formatted_diff_str_to_file( fpath, diff_str )

    # b) sentences
    diff_str, sentences_gap_counter = format_diffs_string(doc, grouped_sentences, gap_counter=sentences_gap_counter, format='horizontal')
    fpath = os.path.join(output_dir, '_sentences_diff_gaps.txt')
    write_formatted_diff_str_to_file( fpath, diff_str )

    # Remove redundant layers (before saving)
    if remove_redundant_layers:
        if 'original_words' in doc.layers.keys():
            del doc.original_words
        if 'original_sentences' in doc.layers.keys():
            del doc.original_sentences
        if 'original_paragraphs' in doc.layers.keys():
            del doc.original_paragraphs
        if 'v1_4_morph_analysis' in doc.layers.keys():
            del doc.v1_4_morph_analysis
        # Regular layers
        if 'compound_tokens' in doc.layers.keys():
            del doc.compound_tokens
        if 'tokens' in doc.layers.keys():
            del doc.tokens
        if 'sentences_quot_fix' in doc.layers.keys():
            del doc.sentences_quot_fix
        if 'sentences' in doc.layers.keys():
            del doc.sentences
        if 'words' in doc.layers.keys():
            del doc.words
        # We could also remove layers used for diffs
        # Because diffs are based on spans only

    # output data 
    fpath = os.path.join(output_dir, outfname)
    text_to_json(doc, file=fpath)

    doc_count += 1
    #if doc_count > 1:
    #    break
print()
print()
if broken_docs:
    print(' Broken documents:', broken_docs)
print('')
print('TOTAL STATISTICS:')
print('use_estnltk_quotation_fixes={}'.format(use_quot_fix))
print(summarizer.get_diffs_summary_output( show_doc_count=False ))
