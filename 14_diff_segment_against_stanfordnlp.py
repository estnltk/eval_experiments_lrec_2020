#
# Finds diffs of v1.6 segmentation against stanfordNLP.
# Loads already annotated (stanfordNLP & estnltk) documents from the disk.
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

input_dir = 'stanfordnlp_annotated'
assert os.path.exists(input_dir), '(!) Missing input dir {}'.format(input_dir)

output_dir = 'diffs_stanfordnlp_segment'+('_estnltk_quot_fix' if use_quot_fix else '')

if not os.path.exists(output_dir):
    os.mkdir(output_dir)

words_diff_tagger = DiffTagger(layer_a='stanford_words',
                         layer_b='estnltk_words_flat',
                         output_layer='words_diff_layer',
                         output_attributes=('span_status', ),
                         span_status_attribute='span_status')
sentences_diff_tagger = DiffTagger(layer_a='stanford_sentences',
                         layer_b='estnltk_sentences_qfx_flat' if use_quot_fix else 'estnltk_sentences_flat',
                         output_layer='sentences_diff_layer',
                         output_attributes=('span_status', ),
                         span_status_attribute='span_status')

summarizer = SegmentDiffSummarizer('stanford', 'estnltk')

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
    # Sanity check
    assert 'stanford_words' in doc.layers.keys(), "(!) Annotated doc {} misses 'stanford_words'".format(fname_stub)
    assert 'stanford_sentences' in doc.layers.keys(), "(!) Annotated doc {} misses 'stanford_sentences'".format(fname_stub)
    assert 'stanford_morph' in doc.layers.keys(), "(!) Annotated doc {} misses 'stanford_morph'".format(fname_stub)
    assert 'words' in doc.layers.keys(), "(!) Annotated doc {} misses 'words'".format(fname_stub)
    assert 'sentences' in doc.layers.keys(), "(!) Annotated doc {} misses 'sentences'".format(fname_stub)
    # 2) Create flat layers
    create_flat_estnltk_segmentation_layer( doc, 'words', 'estnltk_words_flat', add_layer=True )
    create_flat_estnltk_segmentation_layer( doc, 'sentences_quot_fix' if use_quot_fix else 'sentences', \
                                                 'estnltk_sentences_qfx_flat' if use_quot_fix else 'estnltk_sentences_flat', \
                                                 add_layer=True )
    # 3) Find differences
    words_diff_tagger.tag( doc )
    sentences_diff_tagger.tag( doc )
    
    # Remove redundant layers (before saving)
    if remove_redundant_layers:
        if 'original_words' in doc.layers.keys():
            del doc.original_words
        if 'original_sentences' in doc.layers.keys():
            del doc.original_sentences
        if 'original_paragraphs' in doc.layers.keys():
            del doc.original_paragraphs
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
        if 'stanford_morph' in doc.layers.keys():
            del doc.stanford_morph
        # We might also remove layers used for diffs
        # Because diffs are based on spans only
        #if 'estnltk_sentences_flat' in doc.layers.keys():
        #    del doc.estnltk_sentences_flat
        #if 'stanford_sentences' in doc.layers.keys():
        #    del doc.stanford_sentences
        #if 'estnltk_words_flat' in doc.layers.keys():
        #    del doc.estnltk_words_flat
        #if 'stanford_words' in doc.layers.keys():
        #    del doc.stanford_words
    
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
