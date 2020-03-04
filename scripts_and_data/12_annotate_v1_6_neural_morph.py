#
#  Annotates given documents for v1_6 morph_analysis with neural disambiguator 
#  and saves the results as JSON format files.
#
#  The script runs without arguments, provided that required input 
#  folder is available, and neural morpological disambiguator has 
#  been correctly configured.
#
#  How to set up & test neuromorph under Ubuntu?
#
#  0) download the model from the temporary location:
#      https://entu.keeleressursid.ee/api2/file-23989
#      ( you should get file softmax_emb_cat_sum.zip )
#
#  1) Find the location where estnltk is installed in your conda environment.
#     The full path could be something like that:
#       /home/my_user/conda_envs/py36/lib/python3.6/site-packages/estnltk-1.6.4b0-py3.6-linux-x86_64.egg/estnltk
#     
#     In estnltk's installation folder, there should be a subdirectory:
#       .../taggers/neural_morph/new_neural_morph/softmax_emb_cat_sum
#
#     Unpack the zip file and copy its contents (namely: folder 'output') to the 'softmax_emb_cat_sum';
#
#     Now, set the variable NEURAL_MORPH_TAGGER_CONFIG, e.g.
#      $ export NEURAL_MORPH_TAGGER_CONFIG=/home/my_user/conda_envs/py36/lib/python3.6/site-packages/estnltk-1.6.4b0-py3.6-linux-x86_64.egg/estnltk/taggers/neural_morph/new_neural_morph/softmax_emb_cat_sum
#      $ echo $NEURAL_MORPH_TAGGER_CONFIG
#
#  2) repair neuromorph and get it passing the tests:
#     2.1) apply fixes from the commit:
#          https://github.com/estnltk/estnltk/commit/952158b7b0f887348fd152bf5f4d4e1cc66654fd#diff-d6c68f9e1192f401c26453f5efe7e034
#          (to get the tests working)
#     2.2) apply the fixes from the commit:
#          https://github.com/estnltk/estnltk/commit/3aa24ac4eaf35e6e0a8e2be27cc43c55e5c5dfae
#          (to get correct postags for proper names and 'adt' forms)
#     2.3) run pytest and see if it succeeds:
#          $ pytest --pyargs estnltk.tests.test_taggers.test_new_neural_morph_tagger
#          ...
#          ==================================== 3 passed, 13 warnings in 53.56s ====================================
#
#  In order to speed up the process, it is recommended to launch 
#  multiple instances of the process at the same time on different 
#  partitions of the corpus, e.g.
#       
#       python  12_annotate_v1_6_neural_morph.py   1,2 
#       python  12_annotate_v1_6_neural_morph.py   2,2 
#       

import os, os.path, json, codecs, re
from collections import defaultdict
from sys import argv

from enc2017_extra_utils import create_enc_filename_stub
from enc2017_extra_utils import EstnltkJsonDocIterator
from enc2017_extra_utils import get_partition_info_from_sys_argv

from estnltk import Text
from estnltk.taggers.neural_morph.new_neural_morph.neural_morph_tagger import SoftmaxEmbCatSumTagger

from estnltk.converters import text_to_json, json_to_text

partition = get_partition_info_from_sys_argv( argv )

# use softmax emb_cat_sum model
neural_disamb = SoftmaxEmbCatSumTagger(output_layer='morph_softmax_emb_cat_sum')

remove_redundant_layers = True

use_progressbar = True

use_existing_morph = True

# inputs
input_dir_1 = 'estnltk_morph_annotated'
assert os.path.exists(input_dir_1), '(!) Morph analysis input dir {!r} not available'.format(input_dir_1)
input_dir_2 = 'segmentation_annotated'
assert os.path.exists(input_dir_2), '(!) Segmentation input dir {!r} not available'.format(input_dir_2)

# output
output_dir = 'v1_6_neural_disamb_annotated'
if not os.path.exists(output_dir):
    os.mkdir(output_dir)

doc_count = 0
broken_docs = []
iterator = EstnltkJsonDocIterator(input_dir_1, skip_list=[], prefixes=[], partition=partition,\
                                             use_progressbar=use_progressbar, verbose=True, take_only_first=-1)
for doc in iterator.iterate():
    doc_src = doc.meta['src'].lower() if 'src' in doc.meta else '--'
    fname_stub = create_enc_filename_stub( doc )
    # 1) Check morph input
    assert 'words' in doc.layers.keys(), "(!) Annotated doc {} misses 'words'".format(fname_stub)
    if use_existing_morph:
        assert 'morph_analysis' in doc.layers.keys(), "(!) Annotated doc {} misses 'morph_analysis'".format(fname_stub)

    # 2) Load and check segmentation input
    fpath = os.path.join(input_dir_2, fname_stub + '.json')
    assert os.path.exists(fpath), '(!) V1.6 segmentation file {} is missing!'.format( fpath )
    doc_with_segm = json_to_text(file=fpath)
    if doc_with_segm.text != doc.text:
        print ('(!) Mismatching texts for {} in {} and {}. Skipping broken document.'.format(fname_stub, input_dir_1, input_dir_2))
        broken_docs.append(fname_stub)
        continue
    assert 'sentences' in doc_with_segm.layers.keys(), "(!) Annotated doc_with_segm {} misses 'sentences'".format(fname_stub)
    assert 'compound_tokens' in doc_with_segm.layers.keys(), "(!) Annotated doc_with_segm {} misses 'compound_tokens'".format(fname_stub)
    # Extract sentences segmentation layer (perform some layer copying "black magic")
    sentences_copy = doc_with_segm['sentences'].copy()
    sentences_copy.text_object = None
    doc.add_layer( sentences_copy )
    
    # 3) Add the default morph_analysis (if required)
    if not use_existing_morph:
        doc.tag_layer( ['morph_analysis'] )
    
    # 4) Use neural morph disamb
    neural_disamb.tag( doc )
    
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

if broken_docs:
    print()
    print(' Broken documents:', broken_docs)
print('Docs annotated total:  ', doc_count)