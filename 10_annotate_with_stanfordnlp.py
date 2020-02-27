#
#  Annotates given json documents with standordnlp.
#  Saves the results as EstNLTK v1.6 JSON files.
#
#  The script runs without arguments, provided that required 
#  input and model folders are available.
#
#  In order to speed up the process, it is recommended to 
#  launch multiple instances of the process at the same time 
#  on different partitions of the corpus, e.g.
#       
#       python  10_annotate_with_stanfordnlp.py  (1,2)
#       python  10_annotate_with_stanfordnlp.py  (2,2)
#   

import os, os.path, re
from sys import argv

from enc2017_extra_utils import create_enc_filename_stub
from enc2017_extra_utils import EstnltkJsonDocIterator
from enc2017_extra_utils import get_partition_info_from_sys_argv
from enc2017_extra_utils import fetch_text_category

import stanfordnlp

from estnltk.layer.layer import Layer
from estnltk.converters import text_to_json

from segm_eval_utils import create_stanford_segmentation_layer

partition = get_partition_info_from_sys_argv( argv )

models_dir = '.'
assert os.path.exists(models_dir), '(!) Not found stanfordnlp\'s estonian models dir at: {!r}'.format(models_dir)
#stanfordnlp.download('et', models_dir)

# https://stanfordnlp.github.io/stanfordnlp/pipeline.html
# Initialize stanford pipeline for et tokenization
stanford_pipeline = stanfordnlp.Pipeline(lang="et", processors='tokenize,pos,lemma', models_dir=models_dir)

remove_redundant_layers = True

use_progressbar = True

# input dir 
input_dir = 'segmentation_annotated'
assert os.path.exists(input_dir), '(!) Input dir {!r} not available'.format(input_dir)

# output dir
output_dir = 'stanfordnlp_annotated'
if not os.path.exists(output_dir):
    os.mkdir(output_dir)


def get_stanford_segmentation_indices( text_str, stanford_doc, fname_stub ):
    ''' Fetches sentence and word positions from a document annotated by stanfordnlp. '''
    word_locs = []
    sent_locs = []
    last_location = 0
    for sent in stanford_doc.sentences:
        sent_start = -1
        sent_end   = -1
        for wid, wrd in enumerate( sent.words ):
            wrd_id   = wrd.index
            wrd_text = wrd.text
            word_start = text_str.find(wrd_text, last_location)
            if word_start > -1:
                word_loc = (word_start, word_start+len(wrd_text))
                word_locs.append( word_loc )
                last_location = word_start + len(wrd_text)
                if wid == 0:
                    sent_start = word_start
                sent_end = last_location
            else:
                raise Exception('(!) Unable to locate word {!r} in file {!r} in the text: {!r}'.format(wrd_text, fname_stub, text_str[last_location:]))
        assert sent_start != -1 and sent_end != -1, '(!) Unable to get sentence locations in file {!r}'.format(fname_stub)
        sent_locs.append( (sent_start, sent_end) )
    return word_locs, sent_locs


def get_stanford_morph_annotations( stanford_doc, fname_stub ):
    ''' Fetches UD morphological annotations from a document annotated by stanfordnlp. '''
    words = []
    for sid, sent in enumerate(stanford_doc.sentences):
        for wid, wrd in enumerate( sent.words ):
            word_dict = {}
            word_dict['output_text'] = wrd.text
            word_dict['index'] = wrd.index
            word_dict['lemma'] = wrd.lemma
            word_dict['upos'] = wrd.upos
            word_dict['xpos'] = wrd.xpos
            word_dict['feats'] = wrd.feats
            words.append(word_dict)
    return words


def create_stanford_morph_layer( text_obj, stanford_doc, words_layer, m_layer, output_layer, add_layer=True ):
    '''Creates a layer containing morph annotations from stanfordnlp. '''
    assert isinstance(stanford_doc, dict)
    assert m_layer in stanford_doc, '(!) Layer {!r} missing from: {!r}'.format(m_layer, stanford_doc.keys())
    assert words_layer in stanford_doc, '(!) Layer {!r} missing from: {!r}'.format(words_layer, stanford_doc.keys())
    layer = Layer(name=output_layer, \
                  attributes=('output_text', 'index', 'lemma', 'upos', 'xpos', 'feats'), \
                  text_object=text_obj,\
                  ambiguous=False)
    assert len(stanford_doc[words_layer]) == len(stanford_doc[m_layer])
    for wid, span in enumerate(stanford_doc[words_layer]):
        morph = stanford_doc[m_layer][wid]
        if 'text' in morph and 'output_text' not in morph:
            morph['output_text'] = morph['text']
            del morph['text']
        layer.add_annotation( (int(span[0]), int(span[1])), **morph )
    if add_layer:
        text_obj.add_layer( layer )
    return layer


skip_list = []
doc_count = 0
iterator = EstnltkJsonDocIterator(input_dir, skip_list=skip_list, prefixes=[], partition=partition,\
                                             use_progressbar=use_progressbar, verbose=True, take_only_first=-1)
for doc in iterator.iterate():
    doc_src = doc.meta['src'].lower() if 'src' in doc.meta else '--'
    # 1) Create stanfordnlp annotations
    stanford_doc_json = None
    fname_stub = create_enc_filename_stub( doc )
    doc_category = fetch_text_category( doc )
    if len(doc.text) > 0:  # Assure textual content, because calling stanford_pipeline() on empty string gives an AssertionError
        # Has textual content: annotate!
        stanford_doc = stanford_pipeline( doc.text )
        stanford_words, stanford_sents = get_stanford_segmentation_indices( doc.text, stanford_doc, fname_stub )
        stanford_words_annotated = get_stanford_morph_annotations( stanford_doc, fname_stub )
        assert len(stanford_words) == len(stanford_words_annotated), \
            '(!) Unexpected size differences in {!r}: {!r} vs {!r}'.format(fname_stub, str(stanford_words), str(stanford_words_annotated))
        stanford_doc_json = {'metadata': doc.meta, 'text':doc.text, 'words':stanford_words, \
                             'sentences':stanford_sents, 'annotations':stanford_words_annotated }
    else:
        # No textual content: create an empty stanford document
        stanford_doc_json = {'metadata': doc.meta, 'text':doc.text, 'words':[], \
                             'sentences':[], 'annotations':[] }
    
    # 2) Create EstNLTK's layers with stanfordnlp annotations
    assert stanford_doc_json is not None
    stanford_words = create_stanford_segmentation_layer( doc, stanford_doc_json, 'words', 'stanford_words', add_layer=True )
    stanford_sentences = create_stanford_segmentation_layer( doc, stanford_doc_json, 'sentences', 'stanford_sentences', add_layer=True )
    stanford_morph = create_stanford_morph_layer( doc, stanford_doc_json, 'words', 'annotations', 'stanford_morph', add_layer=True )
    # Remove redundant layers (before saving)
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
        # Note: do not delete 'words' and 'sentences'
        # Flat layers
        if 'v1_4_words' in doc.layers.keys():
            del doc.v1_4_words
        if 'v1_4_sentences' in doc.layers.keys():
            del doc.v1_4_sentences
        if 'v1_4_morph_analysis' in doc.layers.keys():
            del doc.v1_4_morph_analysis
        
    outfname = fname_stub+'.json'
    fpath = os.path.join(output_dir, outfname)
    text_to_json(doc, file = fpath)
    doc_count += 1

print()
print(' Docs annotated total:  ', doc_count)
