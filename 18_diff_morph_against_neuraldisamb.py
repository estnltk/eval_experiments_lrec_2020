#
# Finds diffs of v1.6 morph against neural morphological disambiguation.
# Loads already annotated (neuromorph & estnltk) documents from the disk.
#
# The script runs without arguments, provided that required 
# input folders are available.
#
import os, os.path, json, codecs
from collections import OrderedDict

from enc2017_extra_utils import create_enc_filename_stub
from enc2017_extra_utils import EstnltkJsonDocIterator
from enc2017_extra_utils import fetch_text_category

from morph_eval_utils import create_redux_v1_6_morph_analysis_layer
from morph_eval_utils import create_redux_neuro_morph_layer
from morph_eval_utils import get_morph_analysis_redux_diff_alignments
from morph_eval_utils import format_annotation_diff_alignments
from morph_eval_utils import create_annotation_diff_alignments_layer
from morph_eval_utils import write_formatted_diff_str_to_file
from morph_eval_utils import MorphDiffSummarizer

from estnltk import Text
from estnltk.converters import text_to_json, json_to_text
from estnltk.taggers import DiffTagger

remove_redundant_layers = True

use_progressbar = True

input_dir_1 = 'estnltk_morph_annotated'
input_dir_2 = 'v1_6_neural_disamb_annotated'

assert os.path.exists(input_dir_1), '(!) Missing input dir {!r}'.format(input_dir_1)
assert os.path.exists(input_dir_2), '(!) Missing input dir {!r}'.format(input_dir_2)

output_dir = 'diffs_neural_morph_disamb'
if not os.path.exists(output_dir):
    os.mkdir(output_dir)

fpath = os.path.join(output_dir, '_morph_disamb_diff_gaps.txt')
if os.path.exists(fpath):
    os.unlink(fpath)

morph_diff_tagger = DiffTagger(layer_a = 'v1_6_morph_analysis_redux',
                               layer_b = 'neural_disamb_redux',
                               output_layer='morph_diff_layer',
                               output_attributes=('span_status','pos','form' ),
                               span_status_attribute='span_status')

summarizer = MorphDiffSummarizer('v1_6', 'neuromorph')

morph_diff_gap_counter = 0
broken_docs = []
skip_list = []
doc_count = 0
prefixes  = []
assertion_fail_docs = []
iterator = EstnltkJsonDocIterator(input_dir_1, skip_list=skip_list, prefixes=prefixes, partition=None,\
                                             use_progressbar=use_progressbar, verbose=True, take_only_first=-1)
for doc in iterator.iterate():
    doc_src = doc.meta['src'].lower() if 'src' in doc.meta else '--'
    # 1) Load neural disambiguated text
    fname_stub = create_enc_filename_stub( doc )
    fname = fname_stub+'.json'
    fpath = os.path.join(input_dir_2, fname)
    assert os.path.exists(fpath), '(!) Missing neuromorph annotations file {}'.format( fpath )
    doc_neuromorph = json_to_text(file=fpath)
    
    # Sanity checks
    assert "morph_softmax_emb_cat_sum" in doc_neuromorph.layers.keys(), "(!) Annotated doc_neuromorph {} misses 'morph_softmax_emb_cat_sum'".format(fname_stub)
    assert 'morph_analysis' in doc.layers.keys(), "(!) Annotated doc {} misses 'morph_analysis'".format(fname_stub)
    if doc_neuromorph.text != doc.text:
        print('(!) Textual content differs in neuromorph doc and v1_6 doc at {}. Skipping broken document.'.format(fname))
        broken_docs.append(fname_stub)
        continue
    
    # 2) Create reduced morph analysis layers 
    redux_vm_morph = create_redux_v1_6_morph_analysis_layer( doc, 'morph_analysis', 'v1_6_morph_analysis_redux', add_layer=False, add_lemma=False )
    redux_vm_morph.text_object = None
    doc_neuromorph.add_layer( redux_vm_morph )
    create_redux_neuro_morph_layer( doc_neuromorph, "morph_softmax_emb_cat_sum", 'neural_disamb_redux', add_layer=True )

    # 3) Find differences & alignments
    try:
        morph_diff_tagger.tag( doc_neuromorph )
        alignments = get_morph_analysis_redux_diff_alignments( doc_neuromorph, \
                                                               'v1_6_morph_analysis_redux', \
                                                               'neural_disamb_redux',\
                                                               'morph_diff_layer', \
                                                               layer_a_origin = None, \
                                                               layer_b_origin = "morph_softmax_emb_cat_sum" )
        annotations_diff = \
            create_annotation_diff_alignments_layer( doc_neuromorph, alignments, 
                                                     'v1_6_morph_analysis_redux', \
                                                     'neural_disamb_redux', 'morph_annotations_diff_layer' )
        doc_neuromorph.add_layer( annotations_diff )
    except AssertionError as error:
        # Some assertion failed
        print('(!) Assertion failed for {}'.format( fname ) )
        assertion_fail_docs.append( fname_stub )
        raise
    except:
        # Some other, unexpected error
        raise
    
    # 4) Visualize & output words with different annotations
    formatted, morph_diff_gap_counter = \
          format_annotation_diff_alignments( doc_neuromorph, alignments, \
                                             'v1_6_morph_analysis_redux', \
                                             'neural_disamb_redux',\
                                             gap_counter=morph_diff_gap_counter )
    if formatted is not None:
        fpath = os.path.join(output_dir, '_morph_analysis_diff_gaps.txt')
        write_formatted_diff_str_to_file( fpath, formatted )

    # Remove redundant layers (before saving)
    if remove_redundant_layers:
        if 'original_words' in doc_neuromorph.layers.keys():
            del doc_neuromorph.original_words
        if 'original_sentences' in doc_neuromorph.layers.keys():
            del doc_neuromorph.original_sentences
        if 'original_paragraphs' in doc_neuromorph.layers.keys():
            del doc_neuromorph.original_paragraphs
        if 'compound_tokens' in doc_neuromorph.layers.keys():
            del doc_neuromorph.compound_tokens
        if 'tokens' in doc_neuromorph.layers.keys():
            del doc_neuromorph.tokens
        if 'sentences_quot_fix' in doc_neuromorph.layers.keys():
            del doc_neuromorph.sentences_quot_fix
        if 'sentences' in doc_neuromorph.layers.keys():
            del doc_neuromorph.sentences
        if 'words' in doc_neuromorph.layers.keys():
            del doc_neuromorph.words
        if 'morph_analysis' in doc_neuromorph.layers.keys():
            del doc_neuromorph.morph_analysis
        if 'morph_softmax_emb_cat_sum' in doc_neuromorph.layers.keys():
            del doc_neuromorph.morph_softmax_emb_cat_sum
    
    # Record statistics
    text_cat = fetch_text_category(doc_neuromorph)
    summarizer.record_from_diff_layer( 'morph_analysis', doc_neuromorph['morph_diff_layer'], text_cat )
    
    # output data 
    fpath = os.path.join(output_dir, fname)
    text_to_json(doc_neuromorph, file=fpath)

    doc_count += 1
    #if doc_count > 1:
    #    break
print()
print()
if broken_docs:
    print(' Broken documents:', broken_docs)
print('')
print('TOTAL STATISTICS:')
print(summarizer.get_diffs_summary_output( show_doc_count=False ))
