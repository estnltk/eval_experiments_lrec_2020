#
# Finds diffs of v1.6 morph_analysis against v1.4 morph_analysis.
# Loads already annotated documents from the disk.
#
# The script runs without arguments, provided that required 
# input folders are available.
#

import os, os.path, json, codecs
from collections import defaultdict

from enc2017_extra_utils import create_enc_filename_stub
from enc2017_extra_utils import EstnltkJsonDocIterator
from enc2017_extra_utils import fetch_text_category

from morph_eval_utils import create_flat_v1_6_morph_analysis_layer
from morph_eval_utils import get_estnltk_morph_analysis_diff_annotations
from morph_eval_utils import get_estnltk_morph_analysis_annotation_alignments
from morph_eval_utils import get_concise_morph_diff_alignment_str
from morph_eval_utils import format_morph_diffs_string
from morph_eval_utils import write_formatted_diff_str_to_file
from morph_eval_utils import MorphDiffSummarizer

from estnltk import Text
from estnltk.converters import text_to_json, json_to_text
from estnltk.taggers import DiffTagger

remove_redundant_layers = True

use_progressbar = True

input_dir_1 = 'segmentation_annotated'
input_dir_2 = 'estnltk_morph_annotated'

assert os.path.exists(input_dir_1), '(!) Missing input dir {!r}'.format(input_dir_1)
assert os.path.exists(input_dir_2), '(!) Missing input dir {!r}'.format(input_dir_2)

output_dir = 'diffs_v1_4_morph'

if not os.path.exists(output_dir):
    os.mkdir(output_dir)

fpath = os.path.join(output_dir, '_morph_analysis_diff_gaps.txt')
if os.path.exists(fpath):
    os.unlink(fpath)


morph_diff_tagger = DiffTagger(layer_a='v1_4_morph_analysis',
                         layer_b='v1_6_morph_analysis_flat',
                         output_layer='morph_diff_layer',
                         output_attributes=('span_status', 'root', 'lemma', 'root_tokens', 'ending', 'clitic', 'partofspeech', 'form'),
                         span_status_attribute='span_status')

summarizer = MorphDiffSummarizer('v1_4', 'v1_6')

morph_diff_gap_counter = 0
broken_docs = []
assertion_fail_docs = []
skip_list = []
doc_count = 0
prefixes  = []
iterator = EstnltkJsonDocIterator(input_dir_2, skip_list=skip_list, prefixes=prefixes, partition=None,\
                                             use_progressbar=use_progressbar, verbose=True, take_only_first=-1)
for doc in iterator.iterate():
    doc_src = doc.meta['src'].lower() if 'src' in doc.meta else '--'
    # 1) Load text with v1_4 annotations
    fname_stub = create_enc_filename_stub( doc )
    fname = fname_stub+'.json'
    fpath = os.path.join(input_dir_1, fname)
    assert os.path.exists(fpath), '(!) Missing v1_4 annotations file {}'.format( fpath )
    doc_v1_4 = json_to_text(file=fpath)
    # Sanity check
    assert 'v1_4_words' in doc_v1_4.layers.keys(), "(!) Annotated doc {} misses 'v1_4_words'".format(fname_stub)
    assert 'v1_4_sentences' in doc_v1_4.layers.keys(), "(!) Annotated doc {} misses 'v1_4_sentences'".format(fname_stub)
    assert 'v1_4_morph_analysis' in doc_v1_4.layers.keys(), "(!) Annotated doc {} misses 'v1_4_morph_analysis'".format(fname_stub)
    assert 'morph_analysis' in doc.layers.keys(), "(!) Annotated doc {} misses 'morph_analysis'".format(fname_stub)
    if doc_v1_4.text != doc.text:
        print('(!) Textual content differs in v1_4 doc and v1_6 doc at {}. Skipping broken document.'.format(fname))
        broken_docs.append(fname_stub)
        continue
    # Create flat v1_6 analysis
    flat_morph = create_flat_v1_6_morph_analysis_layer( doc, 'morph_analysis', 'v1_6_morph_analysis_flat', add_layer=False )
    flat_morph.text_object = None
    doc_v1_4.add_layer( flat_morph )
    
    # 3) Find differences & alignments
    morph_diff_tagger.tag( doc_v1_4 )
    try:
        ann_diffs = get_estnltk_morph_analysis_diff_annotations( doc_v1_4, 'v1_4_morph_analysis', 'v1_6_morph_analysis_flat', 'morph_diff_layer')
        alignments = get_estnltk_morph_analysis_annotation_alignments( ann_diffs, ['v1_4_morph_analysis', \
                                                                                   'v1_6_morph_analysis_flat']  )
        
        # 4) Small sanity check:
        # unchanged_annotations + missing_annotations = number_of_annotations_in_old_layer
        # unchanged_annotations + extra_annotations   = number_of_annotations_in_new_layer
        normalized_extra_annotations   = 0
        normalized_missing_annotations = 0
        for diff_span in doc_v1_4['morph_diff_layer']:
            for status in diff_span.span_status:
                if status == 'missing':
                    normalized_missing_annotations += 1
                elif status == 'extra':
                    normalized_extra_annotations += 1
        unchanged_annotations = doc_v1_4['morph_diff_layer'].meta['unchanged_annotations']
        missing_annotations   = doc_v1_4['morph_diff_layer'].meta['missing_annotations'] - normalized_missing_annotations 
        extra_annotations     = doc_v1_4['morph_diff_layer'].meta['extra_annotations'] - normalized_extra_annotations
        missing_annotations_2 = 0
        extra_annotations_2   = 0
        for word_alignment in alignments:
            for annotation_alignment in word_alignment['alignments']:
                if annotation_alignment['__status'] == 'MODIFIED':
                    missing_annotations_2 += 1
                    extra_annotations_2   += 1
                elif annotation_alignment['__status'] == 'MISSING':
                    missing_annotations_2 += 1
                elif annotation_alignment['__status'] == 'EXTRA':
                    extra_annotations_2 += 1
        assert missing_annotations == missing_annotations_2
        assert extra_annotations == extra_annotations_2
    except:
        # Some assertion failed, probably
        assertion_fail_docs.append( fname_stub )
        print('(!) Assertion failed for {}'.format( fname ) )
        raise
    
    # 5) Visualize & output words with different annotations
    formatted, morph_diff_gap_counter = \
         format_morph_diffs_string( doc_v1_4, alignments, 'v1_4_morph_analysis', 'v1_6_morph_analysis_flat', gap_counter=morph_diff_gap_counter )
    if formatted is not None:
        fpath = os.path.join(output_dir, '_morph_analysis_diff_gaps.txt')
        write_formatted_diff_str_to_file( fpath, formatted )


    # Remove redundant layers (before saving)
    if remove_redundant_layers:
        if 'original_words' in doc_v1_4.layers.keys():
            del doc_v1_4.original_words
        if 'original_sentences' in doc_v1_4.layers.keys():
            del doc_v1_4.original_sentences
        if 'original_paragraphs' in doc_v1_4.layers.keys():
            del doc_v1_4.original_paragraphs
        if 'compound_tokens' in doc_v1_4.layers.keys():
            del doc_v1_4.compound_tokens
        if 'tokens' in doc_v1_4.layers.keys():
            del doc_v1_4.tokens
        if 'v1_4_words' in doc_v1_4.layers.keys():
            del doc_v1_4.v1_4_words
        if 'v1_4_sentences' in doc_v1_4.layers.keys():
            del doc_v1_4.v1_4_sentences
        if 'v1_6_sentences_qfx_flat' in doc_v1_4.layers.keys():
            del doc_v1_4.v1_6_sentences_qfx_flat
        if 'v1_6_words_flat' in doc_v1_4.layers.keys():
            del doc_v1_4.v1_6_words_flat
        if 'v1_6_sentences_flat' in doc_v1_4.layers.keys():
            del doc_v1_4.v1_6_sentences_flat

    # Record statistics
    text_cat = fetch_text_category(doc)
    summarizer.record_from_diff_layer( 'morph_analysis', doc_v1_4['morph_diff_layer'], text_cat )
    
    #print( doc_v1_4.layers.keys() )
    # output data 
    fpath = os.path.join(output_dir, fname)
    text_to_json(doc_v1_4, file=fpath)

    doc_count += 1
    #if doc_count > 1:
    #    break
if broken_docs:
    print()
    print(' Broken documents:', broken_docs)
print('')

print('TOTAL STATISTICS:')
print(summarizer.get_diffs_summary_output( show_doc_count=False ))
