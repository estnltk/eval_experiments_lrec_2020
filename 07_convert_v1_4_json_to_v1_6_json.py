#
#  Converts annotations in EstNLTK v1.4 json files to annotations 
#  of EstNLTK v1.6. Saves documents as EstNLTK v1.6 json files.
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
assert estnltk_version is not None and estnltk_version.startswith('1.6'), \
    '(!) Wrong estnltk version! Use estnltk version 1.6.* for running this code.'

from enc2017_extra_utils import create_enc_filename_stub
from enc2017_extra_utils import EstnltkJsonDocIterator
from enc2017_extra_utils import get_partition_info_from_sys_argv
from enc2017_extra_utils import fetch_text_category

from estnltk.layer.layer import Layer
from estnltk.converters import text_to_json, json_to_text
from estnltk.taggers import VabamorfTagger
from estnltk.taggers.morph_analysis.morf_common import NORMALIZED_TEXT

from segm_eval_utils import create_flat_estnltk_segmentation_layer
from segm_eval_utils import create_flat_estnltk_v1_4_segmentation_layer

remove_redundant_layers = True

use_progressbar = True

# input dir containing v1_6 format files
input_dir_v1_6 = '_plain_texts_json'

# input dir containing v1_4 annotations
input_dir_v1_4 = 'v1_4_selected_annotated'

# output dir
output_dir = 'segmentation_annotated'

if not os.path.exists(output_dir):
    os.mkdir(output_dir)

def create_flat_v1_4_morph_layer( text_obj, v1_4_dict, words_layer, output_layer, add_layer=True ):
    '''Creates a layer containing morph annotations from estnltk 1.4. '''
    assert isinstance(v1_4_dict, dict)
    assert words_layer in v1_4_dict, '(!) Layer {!r} missing from: {!r}'.format(words_layer, v1_4_dict.keys())
    layer = Layer(name=output_layer, \
                  attributes=VabamorfTagger.output_attributes, \
                  text_object=text_obj,\
                  ambiguous=True)
    for wid, span in enumerate(v1_4_dict[words_layer]):
        start = span['start']
        end = span['end']
        analysis = span['analysis']
        if len(analysis) > 0:
            for a in analysis:
                for attrib in VabamorfTagger.output_attributes:
                    if attrib == NORMALIZED_TEXT:
                        if attrib not in a:
                            a[attrib] = v1_4_dict['text'][start:end]
                layer.add_annotation( (start, end), **a )
        else:
            # add an empty annotation
            a = {}
            for attrib in VabamorfTagger.output_attributes:
                a[attrib] = None
            layer.add_annotation( (start, end), **a )
    if add_layer:
        text_obj.add_layer( layer )
    return layer


broken_docs = []
skip_list = []
doc_count = 0
prefixes  = []
iterator = EstnltkJsonDocIterator(input_dir_v1_6, skip_list=skip_list, prefixes=prefixes, partition=None,\
                                                  use_progressbar=use_progressbar, verbose=True, take_only_first=-1)
for doc in iterator.iterate():
    doc_src = doc.meta['src'].lower() if 'src' in doc.meta else '--'
    fname_stub = create_enc_filename_stub( doc )
    doc_category = fetch_text_category( doc )
    fname = fname_stub + '.json'
    # 1) Load v1_4 file
    fpath = os.path.join(input_dir_v1_4, fname)
    v1_4_dict = None
    with codecs.open(fpath, 'rb', 'ascii') as f:
        v1_4_dict = json.loads( f.read() )
    # 2) Sanity check: Assert that textual contents match
    if v1_4_dict['text'] != doc.text:
        print('(!) Mismatching textual contents of v1_4 and v1_6 in {!r}. Skipping file.'.format(fname))
        broken_docs.append( fname_stub )
        continue
    # assert that layers exist
    assert 'sentences' in v1_4_dict.keys()
    assert 'words' in v1_4_dict.keys()
    
    # 3) Create flat v1_4 layers ...
    create_flat_estnltk_v1_4_segmentation_layer( doc, v1_4_dict, 'words', 'v1_4_words', add_layer=True )
    create_flat_estnltk_v1_4_segmentation_layer( doc, v1_4_dict, 'sentences', 'v1_4_sentences', add_layer=True )
    create_flat_v1_4_morph_layer( doc, v1_4_dict, 'words', 'v1_4_morph_analysis', add_layer=True )
    
    # 4) Remove redundant layers (optional)
    if remove_redundant_layers:
        if 'original_words' in doc.layers.keys():
            del doc.original_words
        if 'original_sentences' in doc.layers.keys():
            del doc.original_sentences
        if 'original_paragraphs' in doc.layers.keys():
            del doc.original_paragraphs
    
    # 5) Output document
    fpath = os.path.join(output_dir, fname)
    text_to_json(doc, file=fpath)
    
    doc_count += 1


print()
if broken_docs:
    print( ' Broken documents({}): {}'.format( len(broken_docs)), broken_docs  )
print(' Docs converted total:  ', doc_count)
