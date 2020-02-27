# ===================================================
# ===================================================
#  Utilities for finding & recording morph_analysis
#  differences
# ===================================================
# ===================================================

import os, os.path, re
from operator import eq
from collections import defaultdict
from collections import OrderedDict

from estnltk.text import Text
from estnltk.layer.layer import Layer
from estnltk.layer_operations import flatten
from estnltk.layer.annotation import Annotation
from estnltk.taggers import DiffTagger
from estnltk.taggers.standard_taggers.diff_tagger import iterate_diff_conflicts
from estnltk.taggers.standard_taggers.diff_tagger import iterate_modified

from enc2017_extra_utils import create_enc_filename_stub
from enc2017_extra_utils import fetch_text_category

# =================================================
# =================================================
#    Creating flat layers
# =================================================
# =================================================

def create_flat_v1_6_morph_analysis_layer( text_obj, morph_layer, output_layer, add_layer=True ):
    '''Creates copy of estnltk v1.6 morph_analysis layer that is a flat layer containing only segmentation. '''
    assert isinstance(text_obj, Text)
    assert morph_layer in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(morph_layer, text_obj.layers.keys())
    flat_morph = flatten(text_obj[ morph_layer ], output_layer )
    if add_layer:
        text_obj.add_layer( flat_morph )
    return flat_morph


# =================================================
# =================================================
#    Add annotation_id attribute to a layer
# =================================================
# =================================================

def add_annotation_ids( text_obj, morph_layer, attrib_name, attrib_prefix='' ):
    ''' Add annotation_id attributes to all annotations of a layer.
        This is useful for distinguishing annotations of the diff_layer 
        that are otherwise indistinguishable if they do not have common 
        attributes.
    '''
    assert isinstance(text_obj, Text)
    assert morph_layer in text_obj.layers.keys(), \
           '(!) Layer {!r} missing from: {!r}'.format(morph_layer, text_obj.layers.keys())
    assert attrib_name not in text_obj[ morph_layer ].attributes, \
           '(!) Layer {!r} already has attribute {!r}'.format(morph_layer, attrib_name)
    text_obj[ morph_layer ].attributes += (attrib_name, )
    separator = '' if len(attrib_prefix) == 0 else '_'
    for span in text_obj[ morph_layer ]:
        for aid, ann in enumerate(span.annotations):
            ann[attrib_name] = attrib_prefix+separator+str(aid)


# =================================================
# =================================================
#    Get morph analysis diff
#    ( Vabamorf's annotations )
# =================================================
# =================================================

def get_estnltk_morph_analysis_diff_annotations( text_obj, layer_a, layer_b, diff_layer ):
    ''' Collects differing sets of annotations from EstNLTK's morph_analysis diff_layer. '''
    STATUS_ATTR = '__status'
    assert isinstance(text_obj, Text)
    assert layer_a in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(layer_a, text_obj.layers.keys())
    assert layer_b in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(layer_b, text_obj.layers.keys())
    assert diff_layer in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(diff_layer, text_obj.layers.keys())
    layer_a_spans = text_obj[layer_a]
    layer_b_spans = text_obj[layer_b]
    common_attribs = set(text_obj[layer_a].attributes).intersection( set(text_obj[layer_b].attributes) )
    assert len(common_attribs) > 0, '(!) Layers {!r} and {!r} have no common attributes!'.format(layer_a, layer_b)
    assert STATUS_ATTR not in common_attribs, "(!) Unexpected attribute {!r} in {!r}.".format(STATUS_ATTR, common_attribs)
    assert layer_a not in ['start', 'end']
    assert layer_b not in ['start', 'end']
    collected_diffs = []
    missing_annotations = 0
    extra_annotations   = 0
    a_id = 0
    b_id = 0
    for diff_span in iterate_modified( text_obj[diff_layer], 'span_status' ):
        ds_start = diff_span.start
        ds_end =   diff_span.end
        # Find corresponding span in both layer
        a_span = None
        b_span = None
        while a_id < len(layer_a_spans):
            cur_a_span = layer_a_spans[a_id]
            if cur_a_span.start == ds_start and cur_a_span.end == ds_end:
                a_span = cur_a_span
                break
            a_id += 1
        while b_id < len(layer_b_spans):
            cur_b_span = layer_b_spans[b_id]
            if cur_b_span.start == ds_start and cur_b_span.end == ds_end:
                b_span = cur_b_span
                break
            b_id += 1
        if a_span == None:
            raise Exception('(!) {!r} not found from layer {!r}'.format(diff_span, layer_a))
        if b_span == None:
            raise Exception('(!) {!r} not found from layer {!r}'.format(diff_span, layer_b))
        a_annotations = []
        for a_anno in a_span.annotations:
            a_dict = a_anno.__dict__.copy()
            a_dict = {a:a_dict[a] for a in a_dict.keys() if a in common_attribs}
            a_dict[STATUS_ATTR] = None
            a_annotations.append( a_dict )
        b_annotations = []
        for b_anno in b_span.annotations:
            b_dict = b_anno.__dict__.copy()
            b_dict = {b:b_dict[b] for b in b_dict.keys() if b in common_attribs}
            b_dict[STATUS_ATTR] = None
            b_annotations.append( b_dict )
        for a_anno in a_annotations:
            match_found = False
            for b_anno in b_annotations:
                if a_anno == b_anno:
                    a_anno[STATUS_ATTR] = 'COMMON'
                    b_anno[STATUS_ATTR] = 'COMMON'
                    match_found = True
                    break
            if not match_found:
                missing_annotations += 1
                a_anno[STATUS_ATTR] = 'MISSING'
        for b_anno in b_annotations:
            if b_anno not in a_annotations:
                extra_annotations += 1
                b_anno[STATUS_ATTR] = 'EXTRA'
        collected_diffs.append( {'text':diff_span.text, layer_a: a_annotations, layer_b: b_annotations, 'start':diff_span.start, 'end':diff_span.end} )
    # Sanity check: missing vs extra annotations:
    # Note: text_obj[diff_layer].meta contains more *_annotations items, because it also 
    #       counts annotations in missing spans and extra spans; Unfortunately, merely
    #       subtracting:
    #                       missing_annotations - missing_spans
    #                       extra_annotations - extra_spans
    #       does not work either, because one missing or extra span may contain more 
    #       than one annotation. So, we have to re-count extra and missing annotations ...
    normalized_extra_annotations   = 0
    normalized_missing_annotations = 0
    for span in text_obj[diff_layer]:
        for status in span.span_status:
            if status == 'missing':
                normalized_missing_annotations += 1
            elif status == 'extra':
                normalized_extra_annotations += 1
    assert missing_annotations == text_obj[diff_layer].meta['missing_annotations'] - normalized_missing_annotations
    assert extra_annotations == text_obj[diff_layer].meta['extra_annotations'] - normalized_extra_annotations
    return collected_diffs


def get_estnltk_morph_analysis_annotation_alignments( collected_diffs, layer_names, focus_attributes=['root','partofspeech', 'form'], remove_status=True ):
    ''' Calculates annotation alignments between annotations in collected_diffs. '''
    assert isinstance(layer_names, list) and len(layer_names) == 2
    STATUS_ATTR = '__status'
    MATCHING_ATTR    = '__matching'
    MISMATCHING_ATTR = '__mismatching'
    alignments  = []
    annotations_by_layer = defaultdict(int)
    if len(collected_diffs) > 0:
        first_diff = collected_diffs[0]
        all_attributes = []
        for key in first_diff.keys():
            if key not in ['text', 'start', 'end']:
                all_attributes = [k for k in first_diff[key][0].keys() if k != STATUS_ATTR]
                assert key in layer_names
        assert len( all_attributes ) > 0
        assert len([a for a in focus_attributes if a in all_attributes]) == len(focus_attributes)
        for word_diff in collected_diffs:
            alignment = word_diff.copy()
            a_anns = word_diff[layer_names[0]]
            b_anns = word_diff[layer_names[1]]
            annotations_by_layer[layer_names[0]] += len(a_anns)
            annotations_by_layer[layer_names[1]] += len(b_anns)
            alignment['alignments'] = []
            del alignment[layer_names[0]]
            del alignment[layer_names[1]]
            a_used = set()
            b_used = set()
            for a_id, a in enumerate(a_anns):
                # Find fully matching annotation
                for b_id, b in enumerate(b_anns):
                    if a == b:
                        al = {STATUS_ATTR:'COMMON', layer_names[0]:a, layer_names[1]:b }
                        al[MISMATCHING_ATTR] = []
                        al[MATCHING_ATTR] = all_attributes.copy()
                        alignment['alignments'].append( al )
                        a_used.add(a_id)
                        b_used.add(b_id)
                        break
                if a_id in a_used:
                    continue
                # Find partially matching annotation
                closest_b = None
                closest_b_id = None
                closest_common   = []
                closest_uncommon = []
                for b_id, b in enumerate(b_anns):
                    if a_id in a_used or b_id in b_used:
                        continue
                    if b[STATUS_ATTR] == 'COMMON':
                        # Skip b that has been previously found as being common
                        continue
                    if a != b:
                        #count common attribs
                        matching_attribs = []
                        mismatching = []
                        for attr in all_attributes:
                            if a[attr] == b[attr]:
                                matching_attribs.append(attr)
                            else:
                                mismatching.append(attr)
                        if len(matching_attribs) > len(closest_common):
                            focus_1 = []
                            focus_2 = []
                            if closest_b != None:
                                focus_1 = [a for a in focus_attributes if a in matching_attribs]
                                focus_2 = [a for a in focus_attributes if a in closest_common]
                            # in case of a tie, prefer matches with more focus attributes
                            if len(focus_1) == len(focus_2) or len(focus_1) > len(focus_2):
                                closest_common   = matching_attribs
                                closest_uncommon = mismatching
                                closest_b_id = b_id
                                closest_b = b
                if closest_b != None:
                    al = {STATUS_ATTR:'MODIFIED', layer_names[0]:a, layer_names[1]:closest_b }
                    al[MISMATCHING_ATTR] = closest_uncommon
                    al[MATCHING_ATTR] = closest_common
                    alignment['alignments'].append( al )
                    a_used.add(a_id)
                    b_used.add(closest_b_id)
                else:
                    al = {STATUS_ATTR:'MISSING', layer_names[0]:a, layer_names[1]:{} }
                    al[MISMATCHING_ATTR] = all_attributes.copy()
                    al[MATCHING_ATTR] = []
                    alignment['alignments'].append( al )
                    a_used.add(a_id)
            for b_id, b in enumerate(b_anns):
                if b_id not in b_used:
                    al = {STATUS_ATTR:'EXTRA', layer_names[0]:{}, layer_names[1]:b }
                    al[MISMATCHING_ATTR] = all_attributes.copy()
                    al[MATCHING_ATTR] = []
                    alignment['alignments'].append( al )
            alignments.append( alignment )
    # Sanity check: check that we haven't lost any annotations during the careful alignment
    annotations_by_layer_2 = defaultdict(int)
    for word_diff in alignments:
        for al in word_diff['alignments']:
            for layer in layer_names:
                if len(al[layer].keys()) > 0:
                    annotations_by_layer_2[layer] += 1
    for layer in layer_names:
        if annotations_by_layer[layer] != annotations_by_layer_2[layer]:
           # Output information about the context of the failure
            from pprint import pprint
            print('='*50)
            print(layer,'  ',annotations_by_layer[layer], '  ', annotations_by_layer_2[layer])
            print('='*50)
            pprint(collected_diffs)
            print('='*50)
            pprint(alignments)
            print('='*50)
        assert annotations_by_layer[layer] == annotations_by_layer_2[layer], '(!) Failure in annotation conversion.'
    # Remove STATUS_ATTR's from annotations dict's (if required)
    if remove_status:
        for word_diff in alignments:
            for al in word_diff['alignments']:
                for layer in layer_names:
                    if STATUS_ATTR in al[layer].keys():
                        del al[layer][STATUS_ATTR]
    return alignments


def get_concise_morph_diff_alignment_str( alignments, layer_a, layer_b, focus_attributes=['root','partofspeech','form'], return_list=False ):
    ''' Formats differences of morph analysis annotations as a string (or a list of strings).'''
    STATUS_ATTR = '__status'
    MATCHING_ATTR    = '__matching'
    MISMATCHING_ATTR = '__mismatching'
    out_str = []
    max_len = max(len(layer_a), len(layer_b))
    max_label_len = max( [len(a) for a in ['MODIFIED', 'MISSING', 'EXTRA', 'COMMON']])
    for alignment in alignments:
        assert STATUS_ATTR      in alignment.keys()
        assert MATCHING_ATTR    in alignment.keys()
        assert MISMATCHING_ATTR in alignment.keys()
        assert layer_a in alignment.keys()
        assert layer_b in alignment.keys()
        if alignment[STATUS_ATTR] == 'MODIFIED':
            focus_is_matching = len([fa for fa in focus_attributes if fa in alignment[MATCHING_ATTR]]) == len(focus_attributes)
            if not focus_is_matching:
                a = [alignment[layer_a][fa] for fa in focus_attributes]
                b = [alignment[layer_b][fa] for fa in focus_attributes]
                out_str.append( (' --- {:'+str(max_label_len)+'} {} ').format(alignment[STATUS_ATTR], '-'*50) )
                out_str.append((' {:'+str(max_len)+'}   ').format(layer_a) + ' '+str(a))
                out_str.append((' {:'+str(max_len)+'}   ').format(layer_b) + ' '+str(b))
            else:
                a = [alignment[layer_a][fa] for fa in focus_attributes+alignment[MISMATCHING_ATTR]]
                b = [alignment[layer_b][fa] for fa in focus_attributes+alignment[MISMATCHING_ATTR]]
                out_str.append( (' --- {:'+str(max_label_len)+'} {} ').format(alignment[STATUS_ATTR], '-'*50) )
                out_str.append((' {:'+str(max_len)+'}   ').format(layer_a) + ' '+str(a))
                out_str.append((' {:'+str(max_len)+'}   ').format(layer_b) + ' '+str(b))
        elif alignment[STATUS_ATTR] == 'COMMON':
            a = [alignment[layer_a][fa] for fa in focus_attributes]
            b = [alignment[layer_b][fa] for fa in focus_attributes]
            out_str.append( (' --- {:'+str(max_label_len)+'} {} ').format(alignment[STATUS_ATTR], '-'*50) )
            out_str.append((' {:'+str(max_len)+'}   ').format(layer_a) + ' '+str(a))
            out_str.append((' {:'+str(max_len)+'}   ').format(layer_b) + ' '+str(b))
        elif alignment[STATUS_ATTR] in ['EXTRA', 'MISSING']:
            a = [alignment[layer_a][fa] for fa in focus_attributes] if len(alignment[layer_a].keys()) > 0 else []
            b = [alignment[layer_b][fa] for fa in focus_attributes] if len(alignment[layer_b].keys()) > 0 else []
            out_str.append( (' --- {:'+str(max_label_len)+'} {} ').format(alignment[STATUS_ATTR], '-'*50) )
            if a:
                out_str.append((' {:'+str(max_len)+'}   ').format(layer_a) + ' '+str(a))
            if b:
                out_str.append((' {:'+str(max_len)+'}   ').format(layer_b) + ' '+str(b))
        else:
            raise Exception( '(!) unexpected __status: {!r}'.format(alignment[STATUS_ATTR]) )
    return '\n'.join( out_str ) if not return_list else out_str


def _text_snippet( text_obj, start, end ):
    '''Takes a snippet out of the text, assuring that text boundaries are not exceeded.'''
    start = 0 if start < 0 else start
    start = len(text_obj.text) if start > len(text_obj.text) else start
    end   = len(text_obj.text) if end > len(text_obj.text)   else end
    end   = 0 if end < 0 else end
    snippet = text_obj.text[start:end]
    snippet = snippet.replace('\n', '\\n')
    return snippet


def format_morph_diffs_string( text_obj, diff_word_alignments, layer_a, layer_b, gap_counter=0 ):
    '''Formats aligned differences as human-readable text snippets.'''
    assert layer_a in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(layer_a, text_obj.layers.keys())
    assert layer_b in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(layer_b, text_obj.layers.keys())
    N = 60
    text_cat   = fetch_text_category(text_obj)
    fname_stub = create_enc_filename_stub(text_obj)
    output_lines = []
    for word_alignments in diff_word_alignments:
        w_start = word_alignments['start']
        w_end   = word_alignments['end']
        before = '...'+_text_snippet( text_obj, w_start - N, w_start )
        after  = _text_snippet( text_obj, w_end, w_end + N )+'...'
        output_lines.append('='*85)
        output_lines.append('')
        output_lines.append('  '+text_cat+'::'+fname_stub+'::'+str(gap_counter))
        output_lines.append('')
        output_lines.append( before+' {'+word_alignments['text']+'} '+after  )
        sub_strs = get_concise_morph_diff_alignment_str(word_alignments['alignments'], layer_a, layer_b, return_list=True )
        output_lines.extend( sub_strs )
        output_lines.append('')
        gap_counter += 1
    if len(output_lines)>0:
        output_lines.append('')
    return '\n'.join(output_lines) if len(output_lines)>0 else None, gap_counter


def write_formatted_diff_str_to_file( out_fname, output_lines ):
    '''Writes/appends formatted differences to the given file.'''
    if not os.path.exists(out_fname):
        with open(out_fname, 'w', encoding='utf-8') as f:
            pass
    with open(out_fname, 'a', encoding='utf-8') as f:
        ## write content
        f.write(output_lines)
        if not output_lines.endswith('\n'):
            f.write('\n')


class MorphDiffSummarizer:
    '''Aggregates and summarizes morph_analysis annotations difference statistics based on information from diff layers.'''

    def __init__(self, first_model, second_model):
        self.diffs_counter = {}
        self.first_model    = first_model
        self.second_model   = second_model
    
    def record_from_diff_layer( self, layer_name, layer, text_category ):
        assert isinstance(text_category, str)
        assert len(text_category) > 0
        if layer_name not in self.diffs_counter:
            self.diffs_counter[layer_name] = {}
        if 'total' not in self.diffs_counter[layer_name]:
            self.diffs_counter[layer_name]['total'] = defaultdict(int)
        for key in layer.meta:
            self.diffs_counter[layer_name]['total'][key] += layer.meta[key]
        self.diffs_counter[layer_name]['total']['_docs'] += 1
        if text_category not in self.diffs_counter[layer_name]:
            self.diffs_counter[layer_name][text_category] = defaultdict(int)
        for key in layer.meta:
            self.diffs_counter[layer_name][text_category][key] += layer.meta[key]
        self.diffs_counter[layer_name][text_category]['_docs'] += 1

    def get_diffs_summary_output( self, show_doc_count=True ):
        output = []
        for layer in sorted( self.diffs_counter.keys() ):
            output.append( layer )
            output.append( '\n' )
            diff_categories = [k for k in sorted(self.diffs_counter[layer].keys()) if k != 'total']
            assert 'total' in self.diffs_counter[layer]
            diff_categories.append('total')
            longest_cat_name = max( [len(k) for k in diff_categories] )
            for category in diff_categories:
                src = self.diffs_counter[layer][category]
                if category == 'total':
                    category = 'TOTAL'
                output.append( (' {:'+str(longest_cat_name+1)+'}').format(category) )
                if show_doc_count:
                    output.append('|')
                    output.append(' #docs: {} '.format(src['_docs']) )
                # unchanged_spans + modified_spans + missing_spans = length_of_old_layer
                # unchanged_spans + modified_spans + extra_spans = length_of_new_layer
                # unchanged_annotations + missing_annotations = number_of_annotations_in_old_layer
                # unchanged_annotations + extra_annotations   = number_of_annotations_in_new_layer
                
                first_layer_len  = src['unchanged_annotations'] + src['missing_annotations']
                second_layer_len = src['unchanged_annotations'] + src['extra_annotations']
                total_spans = first_layer_len + second_layer_len
                output.append('|')
                common_spans = src['unchanged_spans'] + src['modified_spans']
                ratio = src['modified_spans'] / common_spans
                output.append(' modified spans: {} / {} ({:.4f}) '.format(src['modified_spans'], common_spans, ratio ))
                output.append('|')
                # Ratio: https://docs.python.org/3.6/library/difflib.html#difflib.SequenceMatcher.ratio
                ratio = (src['unchanged_annotations']*2.0) / total_spans
                output.append(' annotations ratio: {} / {} ({:.4f}) '.format(src['unchanged_annotations']*2, total_spans, ratio ))
                missing_percent = (src['missing_annotations']/total_spans)*100.0
                output.append('|')
                output.append(' only in {}: {} ({:.4f}%) '.format(self.first_model, src['missing_annotations'], missing_percent ))
                extra_percent = (src['extra_annotations']/total_spans)*100.0
                output.append('|')
                output.append(' only in {}: {} ({:.4f}%) '.format(self.second_model, src['extra_annotations'], extra_percent ))
                output.append('\n')
            output.append('\n')
        return ''.join(output)

# =================================================
# =================================================
#    Stanfordnlp vs Vabamorf's annotations
#    comparison: A redux approach
#    Converts both Vabamorf's and Stanfordnlp's 
#    annotations to a reduced morphological 
#    format so that they become comparable
# =================================================
# =================================================

# ================
#  Redux Vabamorf
# ================

def create_redux_v1_6_morph_analysis_layer( text_obj, morph_layer, output_layer, add_layer=True, add_lemma=True ):
    '''Creates a reduced version of estnltk v1.6 morph_analysis layer. 
       The reduced morph layer contains only attributes 'lemma', 'pos' and 'form',
       and it does simplify morphological to an extent, e.g. information about 
       clitics and endings is stripped, and '=' symbols deleted from the root.
       Optionally, if add_lemma=False, then the reduced morph layer contains only
       attributes 'pos' and 'form'.
       The reduced morph layer is required for comparing Vabamorf's annotations 
       against UD annotations (e.g. stanfordnlp) via DiffTagger (because DiffTagger
       assumes that comparable layers have common attributes).
    '''
    assert isinstance(text_obj, Text)
    assert morph_layer in text_obj.layers.keys(), \
           '(!) Layer {!r} missing from: {!r}'.format(morph_layer, text_obj.layers.keys())
    output_attributes = ('lemma', 'pos', 'form')
    if not add_lemma:
        output_attributes = ('pos', 'form')
    redux_layer = Layer(name=output_layer, \
                        attributes=output_attributes, \
                        text_object=text_obj,\
                        ambiguous=True)
    for morph_word in text_obj[ morph_layer ]:
        for ann in morph_word.annotations:
            root   = ann['root']
            lemma  = ann['lemma']
            postag = ann['partofspeech']
            form   = ann['form']
            # Simplify annotations
            if form in ['?', '??']:
                form = ''
            attribs = { 'lemma':root, 'pos':postag, 'form':form }
            if postag == 'V' and lemma.endswith('ma'):
                attribs['lemma'] += 'ma'
            # Remove '=' symbols between letters:
            attribs['lemma'] = _clean_lemma( attribs['lemma'] )
            # Remove lemma ( for comparison against neuromorph which 
            # does not have lemmas ) 
            if not add_lemma:
                del attribs['lemma']
            redux_layer.add_annotation( morph_word.base_span, **attribs )
    if add_layer:
        text_obj.add_layer( redux_layer )
    return redux_layer

# ===================
#  Redux StanfordNLP
# ===================

def create_redux_stanfordnlp_morph_layer( text_obj, morph_layer, output_layer, add_layer=True ):
    '''Creates a reduced version of stanfordnlp morph_analysis layer. 
       The reduced morph layer contains only attributes 'lemma', 'pos' and 'form',
       and it uses Vabamorf's morphological categories.
       The reduced morph layer is required for comparing Vabamorf's annotations 
       against UD annotations (e.g. stanfordnlp) via DiffTagger (because DiffTagger
       assumes that comparable layers have common attributes).
    '''
    assert isinstance(text_obj, Text)
    assert morph_layer in text_obj.layers.keys(), \
           '(!) Layer {!r} missing from: {!r}'.format(morph_layer, text_obj.layers.keys())
    redux_layer = Layer(name=output_layer, \
                  attributes=('lemma', 'pos', 'form'), \
                  text_object=text_obj,\
                  ambiguous=True)
    for morph_word in text_obj[ morph_layer ]:
        for ann in morph_word.annotations:
            attribs = parse_stanfordnlp_morph_redux_attribs( ann )
            redux_layer.add_annotation( morph_word.base_span, **attribs )
            pass
    if add_layer:
        text_obj.add_layer( redux_layer )
    return redux_layer


def _split_feats( morph_form_feats ):
    '''Creates a dictionary based on stanfordnlp's "feats" attribute.'''
    if morph_form_feats is None or len(morph_form_feats) == 0:
        return {}
    feat_chunks = morph_form_feats.split('|')
    feat_chunks_split = [chunk.split('=') for chunk in feat_chunks]
    feats = {kv[0]:kv[1] for kv in feat_chunks_split if len(kv) == 2}
    return feats


def _clean_lemma( lemma ):
    ''' Removes '=' symbols from lemma if they appear between letters.'''
    new_lemma = []
    for i in range(len(lemma)):
        last_c = lemma[i-1] if i-1>-1 else ''
        c = lemma[i]
        next_c = lemma[i+1] if i+1<len(lemma) else ''
        if c == '=':
            if not(last_c.isalpha() and next_c.isalpha()):
                new_lemma.append( c )
        else:
            new_lemma.append( c )
    return ''.join(new_lemma)


ud_to_vm_case_mapping = {
    'Nom':'n', 
    'Gen':'g',
    'Par':'p',
    'Ill':'ill',
    'Ine':'in',
    'Ela':'el',
    'All':'all',
    'Ade':'ad',
    'Abl':'abl',
    'Tra':'tr',
    'Ter':'ter',
    'Ess':'es',
    'Abe':'ab',
    'Com':'kom',
    # aditiiv
    'Add':'adt'
}


def parse_stanfordnlp_morph_redux_attribs( stanfordnlp_annotation ):
    '''Creates and returns a reduced version stanfordnlp's morphological annotation.
       The reduced version contains only attributes 'lemma', 'pos' and 'form', and 
       uses Vabamorf's morphological categories.
       
       See also:
        https://github.com/EstSyntax/EstUD/blob/master/cgmorf2conllu/cgmorf2conllu.py
    '''
    attribs = { 'lemma':'', 'pos':'', 'form':'' }
    # Stanfordnlp attributes:
    ud_lemma = stanfordnlp_annotation['lemma']
    ud_xpos  = stanfordnlp_annotation['xpos'] # the old postag
    ud_upos  = stanfordnlp_annotation['upos'] # the new (UD) postag
    ud_feats = _split_feats( stanfordnlp_annotation['feats'] )
    # ==============================================================
    #   1) Parse lemma
    # ==============================================================
    attribs['lemma'] = ud_lemma
    if attribs['lemma'] is None:
        attribs['lemma'] = ''
    # Remove '=' symbols between letters:
    attribs['lemma'] = _clean_lemma( attribs['lemma'] )
    # ==============================================================
    #   2) Parse postag
    # ==============================================================
    attribs['pos']   = ud_xpos
    # Make corrections to the xpos
    if ud_upos == 'PROPN' and ud_xpos == 'S':
        attribs['pos'] = 'H'
    ud_degree = ud_feats.get('Degree', None)
    if ud_degree == 'Cmp':
        attribs['pos'] = 'C'
    if ud_degree == 'Sup':
        attribs['pos'] = 'U'
    if ud_upos == 'NUM':
        ud_numtype = ud_feats.get('NumType', None)
        if ud_numtype == 'Card':
            attribs['pos'] = 'N'
        if ud_numtype == 'Ord':
            attribs['pos'] = 'O'
    elif ud_upos == 'ADJ':
        # Reduce adjectives to numbers iff required
        ud_numtype = ud_feats.get('NumType', None)
        if ud_numtype == 'Card':
            attribs['pos'] = 'N'
        if ud_numtype == 'Ord':
            attribs['pos'] = 'O'
    # Interjection:  B == I (actually: I is subtype of B) (specific to EWTB corpus)
    if ud_xpos == 'B':
        attribs['pos'] = 'I'
    # Emoticons:  E == Z (specific to EWTB corpus)
    if ud_xpos == 'E':
        attribs['pos'] = 'Z'
    # Symbols following a quantitative phrase
    if ud_xpos == 'nominal' and ud_upos=='SYM':
        attribs['pos'] = 'Z'
    # ==============================================================
    #   3) Parse form
    # ==============================================================
    #  Nominal: ud has both case and number
    if 'Number' in ud_feats and 'Case' in ud_feats:
        ud_number = ud_feats['Number']
        vm_number = 'pl' if ud_number == 'Plur' else ud_number
        vm_number = 'sg' if vm_number == 'Sing' else vm_number
        ud_case = ud_feats['Case']
        assert ud_case in ud_to_vm_case_mapping, \
               '(!) Unexpected case {!r} in: {!r}'.format(ud_case, stanfordnlp_annotation)
        vm_case = ud_to_vm_case_mapping[ud_case]
        attribs['form'] = (vm_number+' '+vm_case) if vm_case != 'adt' else vm_case
        #
        # Special case -- long illative -- leads to an ambiguity:
        #  ud_case == 'Ill' --> 'sg ill' or 'adt'
        #  ud_case == 'Add' --> 'sg ill' or 'adt'
        # TODO: do we need to generate several variants here?
        # 
    # ... All the dance with the verbs ...
    if ud_xpos == 'V':
        # Get UD's category values
        ud_verb_form   = ud_feats.get('VerbForm', None)     # Fin, Inf, Part, Sup, Conv
        ud_voice       = ud_feats.get('Voice',    None)     # Act, Pass
        ud_mood        = ud_feats.get('Mood',     None)     # Ind, Imp, Cnd, Qou
        ud_case        = ud_feats.get('Case',     None)     # Ill, Ine, Ela, Tra, Abe
        ud_number      = ud_feats.get('Number',   None)     # Plur, Sing
        ud_person      = ud_feats.get('Person',   None)     # 1, 2, 3
        ud_tense       = ud_feats.get('Tense',    None)     # Past, Pres
        ud_polarity    = ud_feats.get('Polarity', None)     # Neg
        ud_connegative = ud_feats.get('Connegative', None)  # Yes
        assert not (ud_xpos == 'V' and ud_case != None and ud_number != None), \
               '(!) There should be no such verb: {!r}!'.format( stanfordnlp_annotation )
        #
        #  For an overview of Vabamorf's verb categories, 
        #  see: http://www.filosoft.ee/html_morf_et/morfoutinfo.html#4
        #
        # V1) Infinite forms
        # pure infinite
        if ud_verb_form == 'Inf':
            attribs['form'] = 'da'
        # supine personal
        if ud_verb_form == 'Sup' and ud_voice == 'Act':
            if ud_case == 'Ill':
                attribs['form'] = 'ma'
            if ud_case == 'Ine':
                attribs['form'] = 'mas'
            if ud_case == 'Ela':
                attribs['form'] = 'mast'
            if ud_case == 'Tra':
                attribs['form'] = 'maks'
            if ud_case == 'Abe':
                attribs['form'] = 'mata'
        # supine impersonal
        if ud_verb_form == 'Sup' and ud_voice == 'Pass':
            attribs['form'] = 'tama'
        # nud/tud
        if ud_verb_form == 'Part' and ud_tense == 'Past':
            if ud_voice == 'Act':
                attribs['form'] = 'nud'
            if ud_voice == 'Pass':
                attribs['form'] = 'tud'
        # ger
        if ud_verb_form == 'Conv':
            attribs['form'] = 'des'
        # V2) Negatives:
        if ud_polarity == 'Neg' or ud_connegative == 'Yes':
           # neg auxiliary
           if ud_upos == 'AUX' and ud_lemma in ['ära', 'ei']:
                attribs['form'] = 'neg'
           # neg personal 
           if ud_voice == 'Act':
               # # Ind, Imp, Cnd, Qou
               if ud_mood == 'Ind' and ud_tense == 'Pres':
                    # (!) Ambiguity:  vm_form in ['o', 'neg o']
                    attribs['form'] = 'neg o'
               if ud_mood == 'Imp' and ud_tense == 'Pres' and ud_person == '2' and ud_number == 'Sing':
                    attribs['form'] = 'o'
               if ud_mood == 'Imp' and ud_tense == 'Pres' and ud_person == '2' and ud_number == 'Plur':
                    attribs['form'] = 'neg ge'
               if ud_mood == 'Imp' and ud_tense == 'Pres' and ud_person == '3' and ud_number == 'Plur':
                    attribs['form'] = 'neg gu'
               if ud_mood == 'Ind' and ud_tense == 'Past':
                    # (!) Ambiguity:  vm_form in ['nud', 'neg nud']
                    attribs['form'] = 'neg nud'
               if ud_mood == 'Cnd' and ud_tense == 'Pres':
                    # (!) Ambiguity:  vm_form in ['ks', 'neg ks']
                    attribs['form'] = 'neg ks'
           # neg impersonal 
           if ud_voice == 'Pass':
               if ud_mood == 'Ind' and ud_tense == 'Pres':
                    attribs['form'] = 'ta'
        ud_affirmative = (not ud_polarity == 'Neg') and (not ud_connegative == 'Yes')
        # V3) Indicative, affirmative
        if ud_affirmative and ud_mood == 'Ind':
            # Present tense
            if ud_number == 'Sing'   and ud_tense == 'Pres' and ud_person == '1':
                attribs['form'] = 'n'
            if ud_number == 'Plur'   and ud_tense == 'Pres' and ud_person == '1':
                attribs['form'] = 'me'
            if ud_number == 'Sing'   and ud_tense == 'Pres' and ud_person == '2':
                attribs['form'] = 'd'
            if ud_number == 'Plur'   and ud_tense == 'Pres' and ud_person == '2':
                attribs['form'] = 'te'
            if ud_number == 'Sing'   and ud_tense == 'Pres' and ud_person == '3':
                attribs['form'] = 'b'
            if ud_number == 'Plur'   and ud_tense == 'Pres' and ud_person == '3':
                attribs['form'] = 'vad'
            if ud_voice == 'Pass' and ud_tense == 'Pres' and ud_person == None:
                # Passive voice
                attribs['form'] = 'takse'
            # Past tense
            if ud_number == 'Sing'  and ud_tense == 'Past' and ud_person == '1':
                attribs['form'] = 'sin'
            if ud_number == 'Plur'  and ud_tense == 'Past' and ud_person == '1':
                attribs['form'] = 'sime'
            if ud_number == 'Sing'  and ud_tense == 'Past' and ud_person == '2':
                attribs['form'] = 'sid'
            if ud_number == 'Plur'  and ud_tense == 'Past' and ud_person == '2':
                attribs['form'] = 'site'
            if ud_number == 'Sing'  and ud_tense == 'Past' and ud_person == '3':
                attribs['form'] = 's'
            if ud_number == 'Plur'  and ud_tense == 'Past' and ud_person == '3':
                attribs['form'] = 'sid'
            if ud_voice == 'Pass' and ud_tense == 'Past' and ud_person == None:
                # Passive voice
                attribs['form'] = 'ti'
        # V4) Imperative, affirmative
        if ud_affirmative and ud_mood == 'Imp':
            if ud_number == 'Sing'  and ud_tense == 'Pres' and ud_person == None and ud_voice == 'Act':
                attribs['form'] = 'gu'
            if ud_number == 'Sing'  and ud_tense == 'Pres' and ud_person == '2' and ud_voice == 'Act':
                attribs['form'] = 'o'
            if ud_number == 'Sing'  and ud_tense == 'Pres' and ud_person == '3' and ud_voice == 'Act':
                attribs['form'] = 'gu'
            if ud_number == 'Plur'  and ud_tense == 'Pres' and ud_person == '1' and ud_voice == 'Act':
                attribs['form'] = 'gem'
            if ud_number == 'Plur'  and ud_tense == 'Pres' and ud_person == '2' and ud_voice == 'Act':
                attribs['form'] = 'ge'
            if ud_number == 'Plur'  and ud_tense == 'Pres' and ud_person == '3' and ud_voice == 'Act':
                attribs['form'] = 'gu'
        # V5) Quotative, affirmative
        if ud_affirmative and ud_mood == 'Qot':
            if ud_tense == 'Pres' and ud_voice == 'Act':
                attribs['form'] = 'vat'
            if ud_tense == 'Pres' and ud_voice == 'Pass':
                attribs['form'] = 'tavat'
        # V6) Conditional, affirmative
        if ud_affirmative and ud_mood == 'Cnd':
            # Present tense
            if ud_tense == 'Pres' and ud_voice == 'Act' and ud_number == 'Sing' and ud_person == '1':
                # (!) Ambiguity:  vm_form in ['ksin', 'ks']
                attribs['form'] = 'ksin'
            if ud_tense == 'Pres' and ud_voice == 'Act' and ud_number == 'Sing' and ud_person == '2':
                # (!) Ambiguity:  vm_form in ['ksid', 'ks']
                attribs['form'] = 'ksid'
            if ud_tense == 'Pres' and ud_voice == 'Act' and ud_number == 'Sing' and ud_person == '3':
                attribs['form'] = 'ks'
            if ud_tense == 'Pres' and ud_voice == 'Act' and ud_number == 'Plur' and ud_person == '1':
                # (!) Ambiguity:  vm_form in ['ksime', 'ks']
                attribs['form'] = 'ksime'
            if ud_tense == 'Pres' and ud_voice == 'Act' and ud_number == 'Plur' and ud_person == '2':
                # (!) Ambiguity:  vm_form in ['ksite', 'ks']
                attribs['form'] = 'ksite'
            if ud_tense == 'Pres' and ud_voice == 'Act' and ud_number == 'Plur' and ud_person == '3':
                # (!) Ambiguity:  vm_form in ['ksid', 'ks']
                attribs['form'] = 'ksid'
            if ud_voice == 'Act'  and ud_tense == 'Pres' and ud_person == None:
                attribs['form'] = 'ks'
            # Past tense
            if ud_tense == 'Past' and ud_voice == 'Act' and ud_number == 'Sing' and ud_person == '1':
                # (!) Ambiguity:  vm_form in ['nuksin', 'nuks']
                attribs['form'] = 'nuksin'
            if ud_tense == 'Past' and ud_voice == 'Act' and ud_number == 'Sing' and ud_person == '2':
                # (!) Ambiguity:  vm_form in ['nuksid', 'nuks']
                attribs['form'] = 'nuksid'
            if ud_tense == 'Past' and ud_voice == 'Act' and ud_number == 'Sing' and ud_person == '3':
                attribs['form'] = 'nuks'
            if ud_tense == 'Past' and ud_voice == 'Act' and ud_number == 'Plur' and ud_person == '1':
                # (!) Ambiguity:  vm_form in ['nuksime', 'nuks']
                attribs['form'] = 'nuksime'
            if ud_tense == 'Past' and ud_voice == 'Act' and ud_number == 'Plur' and ud_person == '2':
                # (!) Ambiguity:  vm_form in ['nuksite', 'nuks']
                attribs['form'] = 'nuksite'
            if ud_tense == 'Past' and ud_voice == 'Act' and ud_number == 'Plur' and ud_person == '3':
                # (!) Ambiguity:  vm_form in ['nuksid', 'nuks']
                attribs['form'] = 'nuksid'
        if ud_mood == 'Cnd'  and ud_tense == 'Pres' and ud_voice == 'Pass' and ud_number == None  and ud_person == None:
            # Conditional impersonal
            attribs['form'] = 'taks'
    return attribs


# ==========================
#  Redux NeuroMorph(Disamb)
# ==========================

def create_redux_neuro_morph_layer( text_obj, neuro_morph_layer, output_layer, add_layer=True ):
    '''Creates a reduced version of neuromorph's morph_analysis layer. 
       The reduced morph layer contains only attributes 'pos' and 'form',
       and it uses Vabamorf's morphological categories.
       The reduced morph layer is required for comparing Vabamorf's annotations 
       against UD annotations (e.g. neuromorph's) via DiffTagger (because DiffTagger
       assumes that comparable layers have common attributes).
    '''
    assert isinstance(text_obj, Text)
    assert neuro_morph_layer in text_obj.layers.keys(), \
           '(!) Layer {!r} missing from: {!r}'.format(neuro_morph_layer, text_obj.layers.keys())
    redux_layer = Layer(name=output_layer, \
                        attributes=('pos', 'form'), \
                        text_object=text_obj,\
                        ambiguous=True)
    for morph_word in text_obj[ neuro_morph_layer ]:
        for ann in morph_word.annotations:
            assert 'morphtag' in ann.keys(), '(!) Attribute {!r} missing from: {!r}'.format('morphtag', ann)
            assert 'pos' in ann.keys(), '(!) Attribute {!r} missing from: {!r}'.format('pos', ann)
            assert 'form' in ann.keys(), '(!) Attribute {!r} missing from: {!r}'.format('form', ann)
            neural_output = ann['morphtag']
            postag = ann['pos']
            form = ann['form']
            # Fix some errors made by the neuromorph --> vabamorf converter
            if 'NOUN_TYPE=prop' in neural_output and postag == 'S':
                postag = 'H'
            if form == 'sg adt':
                form = 'adt'
            redux_layer.add_annotation( morph_word.base_span, **{'pos':  postag,\
                                                                 'form': form } )
    if add_layer:
        text_obj.add_layer( redux_layer )
    return redux_layer


# ===================
#   Get alignments   
# ===================

def get_features_from_original_annotation( origin_annotation ):
    ''' Fetches the most distinctive features from the origin_annotation and returns as a string.
        The type of original annotation can be either Vabamorf's morph, StanfordNLP morph or 
        Neuromorph's morph.
    '''
    features_str = ''
    origin = origin_annotation
    if 'upos' in origin.keys() and 'feats' in origin.keys():
        # Stanford annotation 
        features_str = '||'.join( [str(origin[a]) for a in ['lemma', 'upos', 'xpos', 'feats']] )
    elif 'partofspeech' in origin.keys() and 'root' in origin.keys():
        # VM annotation 
        features_str = '||'.join( [str(origin[a]) for a in ['root', 'ending', 'partofspeech', 'form']] )
    elif 'morphtag' in origin.keys() and 'pos' in origin.keys() and 'form' in origin.keys():
        # Neural disamb annotation 
        features_str = '||'.join( [str(origin[a]) for a in ['morphtag', 'pos', 'form']] )
    return features_str


from estnltk.taggers.standard_taggers.diff_tagger import iterate_modified

def get_morph_analysis_redux_diff_alignments( text_obj, layer_a, layer_b, \
                                              diff_layer, layer_a_origin=None, layer_b_origin=None ):
    ''' Collects and returns all alignments of annotation differences from layers a and b.
        A function that does a lot of things.
    '''
    STATUS_ATTR = '__status'
    ORIGIN_ATTR = '__origin'
    MATCHING_ATTR    = '__matching'
    MISMATCHING_ATTR = '__mismatching'
    assert isinstance(text_obj, Text)
    assert layer_a in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(layer_a, text_obj.layers.keys())
    assert layer_b in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(layer_b, text_obj.layers.keys())
    assert layer_a_origin is None or layer_a_origin in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(layer_a_origin, text_obj.layers.keys())
    assert layer_b_origin is None or layer_b_origin in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(layer_b_origin, text_obj.layers.keys())
    assert diff_layer in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(diff_layer, text_obj.layers.keys())
    layer_a_spans = text_obj[layer_a]
    layer_b_spans = text_obj[layer_b]
    layer_a_origin_spans = text_obj[layer_a_origin] if layer_a_origin is not None else []
    layer_b_origin_spans = text_obj[layer_b_origin] if layer_b_origin is not None else []
    common_attribs = set(text_obj[layer_a].attributes).intersection( set(text_obj[layer_b].attributes) )
    assert len(common_attribs) > 0, '(!) Layers {!r} and {!r} have no common attributes!'.format(layer_a, layer_b)
    assert STATUS_ATTR not in common_attribs, "(!) Unexpected attribute {!r} in {!r}.".format(STATUS_ATTR, common_attribs)
    assert ORIGIN_ATTR not in common_attribs, "(!) Unexpected attribute {!r} in {!r}.".format(ORIGIN_ATTR, common_attribs)
    assert MATCHING_ATTR not in common_attribs, "(!) Unexpected attribute {!r} in {!r}.".format(MATCHING_ATTR, common_attribs)
    assert MISMATCHING_ATTR not in common_attribs, "(!) Unexpected attribute {!r} in {!r}.".format(MISMATCHING_ATTR, common_attribs)
    assert layer_a not in ['start', 'end']
    assert layer_b not in ['start', 'end']
    assert layer_a_origin not in ['start', 'end']
    assert layer_b_origin not in ['start', 'end']
    # 
    #   Iterate over all modified spans and:
    #     + collect all annotation modifications
    #     + add matching annotations
    #     + add original (origin) annotations, if available
    #     + collect alignments
    # 
    a_id = 0
    b_id = 0
    alignments = []
    missing_annotations = 0
    extra_annotations   = 0
    for diff_span in iterate_modified( text_obj[diff_layer], 'span_status' ):
        ds_start = diff_span.start
        ds_end =   diff_span.end
        #
        # Find corresponding span on both layers
        #
        a_span = None
        b_span = None
        a_span_origin = None
        b_span_origin = None
        while a_id < len(layer_a_spans):
            cur_a_span = layer_a_spans[a_id]
            cur_a_origin_span = None
            if layer_a_origin is not None:
                cur_a_origin_span = layer_a_origin_spans[a_id]
            if cur_a_span.start == ds_start and cur_a_span.end == ds_end:
                a_span = cur_a_span
                a_span_origin = cur_a_origin_span
                break
            a_id += 1
        while b_id < len(layer_b_spans):
            cur_b_span = layer_b_spans[b_id]
            cur_b_origin_span = None
            if layer_b_origin is not None:
                cur_b_origin_span = layer_b_origin_spans[b_id]
            if cur_b_span.start == ds_start and cur_b_span.end == ds_end:
                b_span = cur_b_span
                b_span_origin = cur_b_origin_span
                break
            b_id += 1
        if a_span == None:
            raise Exception('(!) {!r} not found from layer {!r}'.format(diff_span, layer_a))
        if b_span == None:
            raise Exception('(!) {!r} not found from layer {!r}'.format(diff_span, layer_b))
        #
        # Find matching annotations
        #
        a_annotations = []
        for a_anno in a_span.annotations:
            a_dict = a_anno.__dict__.copy()
            a_dict = {a:a_dict[a] for a in a_dict.keys() if a in common_attribs}
            a_dict[ORIGIN_ATTR] = None
            a_annotations.append( a_dict )
        b_annotations = []
        for b_anno in b_span.annotations:
            b_dict = b_anno.__dict__.copy()
            b_dict = {b:b_dict[b] for b in b_dict.keys() if b in common_attribs}
            b_dict[ORIGIN_ATTR] = None
            b_annotations.append( b_dict )
        a_to_b_matches = dict()
        b_to_a_matches = dict()
        for aid, a_anno in enumerate(a_annotations):
            for bid, b_anno in enumerate(b_annotations):
                if a_anno == b_anno:
                    a_to_b_matches[aid] = bid
                    b_to_a_matches[bid] = aid
                    break # Break: no more than one match
        #
        # Count missing and extra annotations
        # Assign features from annotation origins
        #
        for aid, a_anno in enumerate(a_annotations):
            if aid not in a_to_b_matches:
                missing_annotations += 1
            origin = a_span_origin.annotations[aid] if a_span_origin is not None else None
            if origin:
                origin_features_str = get_features_from_original_annotation( origin )
                a_anno[ORIGIN_ATTR] = origin_features_str
        for bid, b_anno in enumerate(b_annotations):
            if bid not in b_to_a_matches:
                extra_annotations += 1
            origin = b_span_origin.annotations[bid] if b_span_origin is not None else None
            if origin:
                origin_features_str = get_features_from_original_annotation( origin )
                b_anno[ORIGIN_ATTR] = origin_features_str
        #
        # Finally, make maximally aligned pairs of annotations
        #  -- fully matching annotations
        #  -- partially matching annotations
        #  -- missing & extra annotations
        #
        word_alignments = { 'start': ds_start, 'end': ds_end, 'text': diff_span.text, 'alignments': [] }
        bid_used = set()
        for aid, a_anno in enumerate(a_annotations):
            alignment = {}
            if aid in a_to_b_matches:
                b_anno = b_annotations[a_to_b_matches[aid]]
                alignment[STATUS_ATTR] = 'COMMON'
                alignment[layer_a] = a_anno
                alignment[layer_b] = b_anno
                alignment[MATCHING_ATTR] = list(common_attribs)
                alignment[MISMATCHING_ATTR] = []
                word_alignments['alignments'].append( alignment )
            else:
                #  Find partially matching annotation (the closest match)
                closest_b   = None
                closest_bid = None
                closest_common   = []
                closest_uncommon = []
                for bid, b_anno in enumerate(b_annotations):
                    # Skip previously matched annotations
                    if bid in bid_used or bid in b_to_a_matches:
                        continue
                    #count attribs with matching values
                    matching_attribs = []
                    mismatching = []
                    for attr in common_attribs:
                        if a_anno[attr] == b_anno[attr]:
                            matching_attribs.append(attr)
                        else:
                            mismatching.append(attr)
                    if len(matching_attribs) > len(closest_common):
                        closest_common   = matching_attribs
                        closest_uncommon = mismatching
                        closest_bid = bid
                        closest_b = b_anno
                if closest_b != None:
                    bid_used.add( closest_bid )
                    alignment[STATUS_ATTR] = 'MODIFIED'
                    alignment[layer_a] = a_anno
                    alignment[layer_b] = closest_b
                    alignment[MATCHING_ATTR] = closest_common
                    alignment[MISMATCHING_ATTR] = closest_uncommon
                    word_alignments['alignments'].append( alignment )
                else:
                    alignment[STATUS_ATTR] = 'MISSING'
                    alignment[layer_a] = a_anno
                    alignment[layer_b] = {}
                    alignment[MATCHING_ATTR] = []
                    alignment[MISMATCHING_ATTR] = list(common_attribs)
                    word_alignments['alignments'].append( alignment )
        for bid, b_anno in enumerate(b_annotations):
            if bid not in b_to_a_matches and bid not in bid_used:
                alignment = {}
                alignment[STATUS_ATTR] = 'EXTRA'
                alignment[layer_a] = {}
                alignment[layer_b] = b_anno
                alignment[MATCHING_ATTR] = []
                alignment[MISMATCHING_ATTR] = list(common_attribs)
                word_alignments['alignments'].append( alignment )
        assert len(word_alignments['alignments']) > 0
        alignments.append( word_alignments )

    #
    # Sanity check 1: missing vs extra annotations in a_annotations & b_annotations
    # Note: text_obj[diff_layer].meta contains more *_annotations items, because it also 
    #       counts annotations in missing spans and extra spans; Unfortunately, merely
    #       subtracting:
    #                       missing_annotations - missing_spans
    #                       extra_annotations - extra_spans
    #       does not work either, because one missing or extra span may contain more 
    #       than one annotation. So, we have to manually re-count extra and missing 
    #       annotations ...
    #
    normalized_extra_annotations   = 0
    normalized_missing_annotations = 0
    for span in text_obj[diff_layer]:
        for status in span.span_status:
            if status == 'missing':
                normalized_missing_annotations += 1
            elif status == 'extra':
                normalized_extra_annotations += 1
    assert missing_annotations == text_obj[diff_layer].meta['missing_annotations'] - normalized_missing_annotations
    assert extra_annotations == text_obj[diff_layer].meta['extra_annotations'] - normalized_extra_annotations
    #
    # Sanity check 2: missing vs extra annotations in alignments
    #
    extra_annotations_2   = 0
    missing_annotations_2 = 0
    for word_annotations_alignment in alignments:
        for alignment in word_annotations_alignment['alignments']:
            if alignment[STATUS_ATTR] == 'MODIFIED':
                missing_annotations_2 += 1
                extra_annotations_2 += 1
            elif alignment[STATUS_ATTR] == 'MISSING':
                missing_annotations_2 += 1
            elif alignment[STATUS_ATTR] == 'EXTRA':
                extra_annotations_2 += 1
    assert missing_annotations_2 == text_obj[diff_layer].meta['missing_annotations'] - normalized_missing_annotations
    assert extra_annotations_2 == text_obj[diff_layer].meta['extra_annotations'] - normalized_extra_annotations
    return alignments



def format_annotation_diff_alignments( text_obj, diff_annotation_alignments, layer_a, layer_b, gap_counter=0 ):
    ''' Adds textual context to the alignments of annotations diffs and returns as a diff string.
    '''
    STATUS_ATTR = '__status'
    ORIGIN_ATTR = '__origin'
    MATCHING_ATTR    = '__matching'
    MISMATCHING_ATTR = '__mismatching'
    assert layer_a in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(layer_a, text_obj.layers.keys())
    assert layer_b in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(layer_b, text_obj.layers.keys())
    common_attribs = set(text_obj[layer_a].attributes).intersection( set(text_obj[layer_b].attributes) )
    assert len(common_attribs) > 0, '(!) Layers {!r} and {!r} have no common attributes!'.format(layer_a, layer_b)
    focus_attributes = [a for a in ['lemma', 'pos', 'form'] if a in common_attribs]
    max_layern_len = max(len(layer_a), len(layer_b))
    max_labeln_len = max( [len(a) for a in ['MODIFIED', 'MISSING', 'EXTRA', 'COMMON']])
    N = 60
    text_cat   = fetch_text_category(text_obj)
    fname_stub = create_enc_filename_stub(text_obj)
    output_lines = []
    for word_annotations_alignment in diff_annotation_alignments:
        w_start = word_annotations_alignment['start']
        w_end   = word_annotations_alignment['end']
        before = '...'+_text_snippet( text_obj, w_start - N, w_start )
        after  = _text_snippet( text_obj, w_end, w_end + N )+'...'
        output_lines.append('='*85)
        output_lines.append('')
        output_lines.append('  '+text_cat+'::'+fname_stub+'::'+str(gap_counter))
        output_lines.append('')
        output_lines.append( before+' {'+word_annotations_alignment['text']+'} '+after  )
        sub_strs = []
        prev_status = None
        for anno_alignment in word_annotations_alignment['alignments']:
            assert STATUS_ATTR      in anno_alignment.keys()
            assert MATCHING_ATTR    in anno_alignment.keys()
            assert MISMATCHING_ATTR in anno_alignment.keys()
            assert layer_a in anno_alignment.keys()
            assert layer_b in anno_alignment.keys()
            if anno_alignment[STATUS_ATTR] == 'MODIFIED':
                a = [anno_alignment[layer_a][fa] for fa in focus_attributes]
                b = [anno_alignment[layer_b][fa] for fa in focus_attributes]
                mismatching_attr_str = ''
                if anno_alignment[MISMATCHING_ATTR]:
                    mismatching_attr_str = str( anno_alignment[MISMATCHING_ATTR] )
                mismatching_attr_str_len = len(mismatching_attr_str)
                sub_strs.append( (' --- {:'+str(max_labeln_len)+'} {} {} ').format(anno_alignment[STATUS_ATTR], \
                                                                                  mismatching_attr_str, \
                                                                                 '-'*(50-mismatching_attr_str_len-1)) )
                origin_a = '' if not anno_alignment[layer_a][ORIGIN_ATTR] else '  ('+anno_alignment[layer_a][ORIGIN_ATTR]+')'
                origin_b = '' if not anno_alignment[layer_b][ORIGIN_ATTR] else '  ('+anno_alignment[layer_b][ORIGIN_ATTR]+')'
                sub_strs.append((' {:'+str(max_layern_len)+'}   ').format(layer_a) + ' '+str(a) + origin_a)
                sub_strs.append((' {:'+str(max_layern_len)+'}   ').format(layer_b) + ' '+str(b) + origin_b)
            elif anno_alignment[STATUS_ATTR] == 'COMMON':
                a = [anno_alignment[layer_a][fa] for fa in focus_attributes]
                b = [anno_alignment[layer_b][fa] for fa in focus_attributes]
                sub_strs.append( (' --- {:'+str(max_labeln_len)+'} {} ').format(anno_alignment[STATUS_ATTR], '-'*50) )
                origin_a = '' if not anno_alignment[layer_a][ORIGIN_ATTR] else '  ('+anno_alignment[layer_a][ORIGIN_ATTR]+')'
                origin_b = '' if not anno_alignment[layer_b][ORIGIN_ATTR] else '  ('+anno_alignment[layer_b][ORIGIN_ATTR]+')'
                sub_strs.append((' {:'+str(max_layern_len)+'}   ').format(layer_a) + ' '+str(a) + origin_a)
                sub_strs.append((' {:'+str(max_layern_len)+'}   ').format(layer_b) + ' '+str(b) + origin_b)
            elif anno_alignment[STATUS_ATTR] in ['EXTRA', 'MISSING']:
                a = [anno_alignment[layer_a][fa] for fa in focus_attributes] if len(anno_alignment[layer_a].keys()) > 0 else []
                b = [anno_alignment[layer_b][fa] for fa in focus_attributes] if len(anno_alignment[layer_b].keys()) > 0 else []
                if prev_status != anno_alignment[STATUS_ATTR]:  # avoid repetition
                    sub_strs.append( (' --- {:'+str(max_labeln_len)+'} {} ').format(anno_alignment[STATUS_ATTR], '-'*50) )
                if a:
                    origin_a = '' if not anno_alignment[layer_a][ORIGIN_ATTR] else '  ('+anno_alignment[layer_a][ORIGIN_ATTR]+')'
                    sub_strs.append((' {:'+str(max_layern_len)+'}   ').format(layer_a) + ' '+str(a) + origin_a)
                if b:
                    origin_b = '' if not anno_alignment[layer_b][ORIGIN_ATTR] else '  ('+anno_alignment[layer_b][ORIGIN_ATTR]+')'
                    sub_strs.append((' {:'+str(max_layern_len)+'}   ').format(layer_b) + ' '+str(b) + origin_b)
            else:
                raise Exception( '(!) unexpected __status: {!r}'.format(anno_alignment[STATUS_ATTR]) )
            prev_status = anno_alignment[STATUS_ATTR]
        if len(sub_strs) > 0:
            output_lines.extend( sub_strs )
        output_lines.append('')
        gap_counter += 1
    if len(output_lines)>0:
        output_lines.append('')
    return '\n'.join(output_lines) if len(output_lines)>0 else None, gap_counter



def create_annotation_diff_alignments_layer( text_obj, diff_annotation_alignments, layer_a, layer_b, output_layer ):
    ''' Creates a layer containing all alignments of annotation differences.'''
    STATUS_ATTR = '__status'
    ORIGIN_ATTR = '__origin'
    MATCHING_ATTR    = '__matching'
    MISMATCHING_ATTR = '__mismatching'
    assert layer_a in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(layer_a, text_obj.layers.keys())
    assert layer_b in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(layer_b, text_obj.layers.keys())
    # Construct the output layer
    # Get attribute names
    a_attributes = text_obj[layer_a].attributes
    b_attributes = text_obj[layer_b].attributes
    output_attributes = ('status', )
    output_attributes += ('layer', )
    a_unique_attrs = set()
    b_unique_attrs = set()
    for a_attr in a_attributes:
        if a_attr not in b_attributes:
            output_attributes += ('a_'+a_attr, )
            a_unique_attrs.add( a_attr )
        else:
            output_attributes += (a_attr, )
    for b_attr in b_attributes:
        if b_attr not in a_attributes:
            output_attributes += ('b_'+b_attr, )
            b_unique_attrs.add( b_attr )
    output_attributes += ('origin', )
    output_attributes += ('mismatching', )
    alignments_layer = Layer(name=output_layer, \
                             attributes=output_attributes, \
                             text_object=text_obj,\
                             ambiguous=True)
    for word_annotations_alignment in diff_annotation_alignments:
        w_start = word_annotations_alignment['start']
        w_end   = word_annotations_alignment['end']
        span = (w_start, w_end)
        for anno_alignment in word_annotations_alignment['alignments']:
            assert STATUS_ATTR      in anno_alignment.keys()
            assert MISMATCHING_ATTR in anno_alignment.keys()
            assert layer_a in anno_alignment.keys()
            assert layer_b in anno_alignment.keys()
            if len(anno_alignment[layer_a].keys()) > 0:
                result_dict = { a: None for a in output_attributes }
                result_dict['mismatching'] = anno_alignment[MISMATCHING_ATTR]
                result_dict['status']      = anno_alignment[STATUS_ATTR]
                result_dict['layer'] = layer_a
                for a_attr in a_attributes:
                    if a_attr not in a_unique_attrs:
                        result_dict[a_attr] = anno_alignment[layer_a][a_attr]
                    else:
                        result_dict['a_'+a_attr] = anno_alignment[layer_a][a_attr]
                if anno_alignment[layer_a][ORIGIN_ATTR]:
                    result_dict['origin'] = anno_alignment[layer_a][ORIGIN_ATTR]
                alignments_layer.add_annotation( span, **result_dict )
            if len(anno_alignment[layer_b].keys()) > 0:
                result_dict = { a: None for a in output_attributes }
                result_dict['mismatching'] = anno_alignment[MISMATCHING_ATTR]
                result_dict['status']      = anno_alignment[STATUS_ATTR]
                result_dict['layer'] = layer_b
                for b_attr in b_attributes:
                    if b_attr not in b_unique_attrs:
                        result_dict[b_attr] = anno_alignment[layer_b][b_attr]
                    else:
                        result_dict['b_'+b_attr] = anno_alignment[layer_b][b_attr]
                if anno_alignment[layer_b][ORIGIN_ATTR]:
                    result_dict['origin'] = anno_alignment[layer_b][ORIGIN_ATTR]
                alignments_layer.add_annotation( span, **result_dict )
    return alignments_layer

