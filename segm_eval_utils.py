# =================================================
# =================================================
#  Utilities for finding & recording segmentation 
#  differences
# =================================================
# =================================================

import os, os.path, re
from collections import defaultdict

from estnltk.text import Text
from estnltk.layer.layer import Layer
from estnltk.taggers import DiffTagger
from estnltk.taggers.standard_taggers.diff_tagger import iterate_diff_conflicts
from estnltk.taggers.standard_taggers.diff_tagger import iterate_missing
from estnltk.taggers.standard_taggers.diff_tagger import iterate_extra

from enc2017_extra_utils import create_enc_filename_stub
from enc2017_extra_utils import fetch_text_category

# =================================================
#   Creating flat layers
#   (required for using DiffTagger)
# =================================================

def create_stanford_segmentation_layer( text_obj, stanford_doc, seg_layer, output_layer, add_layer=True ):
    '''Creates segmentation layer from stanford_doc saved by the script annotate_with_stanfordnlp.py. '''
    assert isinstance(stanford_doc, dict)
    assert seg_layer in stanford_doc, '(!) Layer {!r} missing from: {!r}'.format(seg_layer, stanford_doc.keys())
    layer = Layer(name=output_layer, \
                  attributes=(), \
                  text_object=text_obj,\
                  ambiguous=False)
    for span in stanford_doc[seg_layer]:
        layer.add_annotation( (int(span[0]), int(span[1])) )
    if add_layer:
        text_obj.add_layer( layer )
    return layer


def create_flat_estnltk_segmentation_layer( text_obj, seg_layer, output_layer, add_layer=True ):
    '''Creates copy of estnltk v1.6 segmentation layer that is a flat layer containing only segmentation. '''
    assert isinstance(text_obj, Text)
    assert seg_layer in text_obj.layers.keys(), '(!) Layer {!r} missing from: {!r}'.format(seg_layer, text_obj.layers.keys())
    layer = Layer(name=output_layer, \
                  attributes=(), \
                  text_object=text_obj,\
                  ambiguous=False)
    for span in text_obj[seg_layer]:
        layer.add_annotation( (span.start, span.end) )
    if add_layer:
        text_obj.add_layer( layer )
    return layer


def create_flat_estnltk_v1_4_segmentation_layer( text_obj, v1_4_dict, seg_layer, output_layer, add_layer=True ):
    '''Creates a segmentation layer from estnltk v1.4 annotations contained in a dictionary v1_4_dict. '''
    assert isinstance(v1_4_dict, dict)
    assert isinstance(text_obj, Text)
    assert seg_layer in v1_4_dict, '(!) Layer {!r} missing from: {!r}'.format(seg_layer, v1_4_dict.keys())
    layer = Layer(name=output_layer, \
                  attributes=(), \
                  text_object=text_obj,\
                  ambiguous=False)
    for span in v1_4_dict[seg_layer]:
        layer.add_annotation( (span['start'], span['end']) )
    if add_layer:
        text_obj.add_layer( layer )
    return layer

# =================================================
#   Gathering and summarizing statistics
# =================================================

class SegmentDiffSummarizer:
    '''Aggregates and summarizes segmentation difference statistics based on information from diff layers.'''

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
                first_layer_len  = src['unchanged_spans'] + src['modified_spans'] + src['missing_spans']
                second_layer_len = src['unchanged_spans'] + src['modified_spans'] + src['extra_spans']
                total_spans = first_layer_len + second_layer_len
                # Ratio: https://docs.python.org/3.6/library/difflib.html#difflib.SequenceMatcher.ratio
                ratio = (src['unchanged_spans']*2.0) / total_spans
                output.append('|')
                output.append(' ratio: {} / {}  ({:.4f}) '.format(src['unchanged_spans']*2, total_spans, ratio ))
                missing_percent = (src['missing_spans']/total_spans)*100.0
                output.append('|')
                output.append(' only in {}: {} ({:.4f}%) '.format(self.first_model, src['missing_spans'], missing_percent ))
                extra_percent = (src['extra_spans']/total_spans)*100.0
                output.append('|')
                output.append(' only in {}: {} ({:.4f}%) '.format(self.second_model, src['extra_spans'], extra_percent ))
                output.append('\n')
            output.append('\n')
        return ''.join(output)

# =======================================
#  Grouping and visualizing differences
# =======================================

def _can_be_added_to_group( span, group ):
    ''' A helper method for group_diff_spans(). 
        A new span can be added to the group iff:
        *) the group is empty, or
        *) the span is already in the group, or
        *) the span continues one span of the group;
    '''
    continues_group = False
    is_in_group = False
    (start, end) = span
    for (g_start, g_end) in group:
        if (g_start, g_end) == (start, end):
            is_in_group = True
        if g_end == start:
            continues_group = True
    return len(group)==0 or (len(group)>0 and (continues_group or is_in_group))


def group_continuous_diff_spans( diff_layer ):
    '''Makes groups out of continuous diff conflicts.'''
    last_a_group = []
    last_b_group = []
    grouped_overlaps = []
    for (a, b) in iterate_diff_conflicts( diff_layer, 'span_status' ):
         a_span = (a.start, a.end)
         b_span = (b.start, b.end)
         a_name = a.input_layer_name[0]
         b_name = b.input_layer_name[0]
         # verify if one of the spans can be used to extend 
         # the last group
         a_ok = _can_be_added_to_group( a_span, last_a_group )
         b_ok = _can_be_added_to_group( b_span, last_b_group )
         if a_ok or b_ok:
            if a_span not in last_a_group:  # avoid duplicates
                last_a_group.append(a_span)
            if b_span not in last_b_group:  # avoid duplicates
                last_b_group.append(b_span)
         else:
            grouped_overlaps.append( {a_name:last_a_group, b_name:last_b_group} )
            # Restart grouping
            last_a_group = [ a_span ]
            last_b_group = [ b_span ]
    assert len(last_a_group) == 0 or (len(last_a_group) > 0 and len(last_b_group) > 0)
    assert len(last_b_group) == 0 or (len(last_a_group) > 0 and len(last_b_group) > 0)
    if len(last_a_group) > 0 and len(last_b_group) > 0:
        grouped_overlaps.append( {a_name:last_a_group, b_name:last_b_group} )
    return grouped_overlaps


def _text_snippet( text_obj, start, end ):
    '''Takes a snippet out of the text, assuring that text boundaries are not exceeded.'''
    start = 0 if start < 0 else start
    start = len(text_obj.text) if start > len(text_obj.text) else start
    end   = len(text_obj.text) if end > len(text_obj.text)   else end
    end   = 0 if end < 0 else end
    snippet = text_obj.text[start:end]
    snippet = snippet.replace('\n', '\\n')
    return snippet


def format_diffs_string( text_obj, grouped_diffs, gap_counter=0, format='vertical' ):
    '''Formats grouped differences as human-readable text snippets.'''
    assert format in ['horizontal', 'vertical'], '(!) Unexpected format:'+str( format )
    if len( grouped_diffs ) > 0:
        layers = sorted( list(grouped_diffs[0].keys()) )
        assert len(layers) == 2
        layer_a = layers[0]
        layer_b = layers[1]
    else:
        return '', gap_counter
    text_cat   = fetch_text_category(text_obj)
    fname_stub = create_enc_filename_stub(text_obj)
    if format == 'vertical':
        N = 40
        output_lines = []
        max_len = max(len(layer_a), len(layer_b))
        for gid, group in enumerate( grouped_diffs ):
            output_a = [(' {:'+str(max_len)+'}   ').format(layer_a)]
            output_b = [(' {:'+str(max_len)+'}   ').format(layer_b)]
            a_spans = group[layer_a]
            b_spans = group[layer_b]
            before_a = '...'+_text_snippet( text_obj, a_spans[0][0]-N, a_spans[0][0] )
            before_b = '...'+_text_snippet( text_obj, b_spans[0][0]-N, b_spans[0][0] )
            output_a.append(before_a)
            output_b.append(before_b)
            last_span = None
            for (start,end) in a_spans:
                if last_span:
                    if last_span[1] != start:
                        output_a.append( _text_snippet( text_obj,last_span[1],start ) )
                output_a.append( '{'+_text_snippet( text_obj,start,end )+'}' )
                last_span = (start,end)
            last_span = None
            for (start,end) in b_spans:
                if last_span:
                    if last_span[1] != start:
                        output_b.append( _text_snippet( text_obj,last_span[1],start ) )
                output_b.append( '{'+_text_snippet( text_obj,start,end )+'}' )
                last_span = (start,end)
            after_a = _text_snippet( text_obj, a_spans[-1][1], a_spans[-1][1]+N )+'...'
            after_b = _text_snippet( text_obj, b_spans[-1][1], b_spans[-1][1]+N )+'...'
            output_a.append(after_a)
            output_b.append(after_b)
            output_lines.append('='*85)
            output_lines.append('')
            output_lines.append('  '+text_cat+'::'+fname_stub+'::'+str(gap_counter))
            output_lines.append('')
            output_lines.append( ''.join(output_a) )
            output_lines.append( ''.join(output_b) )
            output_lines.append('')
            gap_counter += 1
        return '\n'.join(output_lines), gap_counter
    elif format == 'horizontal':
        N = 70
        output_lines = []
        max_len = max(len(layer_a), len(layer_b))
        a_name = (' {:'+str(max_len)+'}   ').format(layer_a)
        b_name = (' {:'+str(max_len)+'}   ').format(layer_b)
        blank  = (' {:'+str(max_len)+'}   ').format(' ')
        for gid, group in enumerate( grouped_diffs ):
            a_spans = group[layer_a]
            b_spans = group[layer_b]
            output_lines.append('='*85)
            output_lines.append('')
            output_lines.append('  '+text_cat+'::'+fname_stub+'::'+str(gap_counter))
            output_lines.append('')
            # 1) Context before
            before_a = '...'+_text_snippet( text_obj, a_spans[0][0]-N, a_spans[0][0] )
            before_b = '...'+_text_snippet( text_obj, b_spans[0][0]-N, b_spans[0][0] )
            extra = '' if before_a == before_b else '*** '
            output_lines.append(blank+extra+before_a)
            # 2) Output difference
            output_lines.append('-'*25)
            last_span = None
            for (start,end) in a_spans:
                if last_span:
                    if last_span[1] != start:
                        in_between_str = _text_snippet( text_obj,last_span[1],start )
                        if not re.match('^\s*$', in_between_str):
                            output_lines.append( blank+in_between_str )
                output_lines.append( a_name+_text_snippet( text_obj,start,end ) )
                last_span = (start,end)
            output_lines.append('-'*25)
            last_span = None
            for (start,end) in b_spans:
                if last_span:
                    if last_span[1] != start:
                        in_between_str = _text_snippet( text_obj,last_span[1],start )
                        if not re.match('^\s*$', in_between_str):
                            output_lines.append( blank+in_between_str )
                output_lines.append( b_name+_text_snippet( text_obj,start,end ) )
                last_span = (start,end)
            output_lines.append('-'*25)
            # 3) Context after
            after_a = _text_snippet( text_obj, a_spans[-1][1], a_spans[-1][1]+N )+'...'
            after_b = _text_snippet( text_obj, b_spans[-1][1], b_spans[-1][1]+N )+'...'
            extra = '' if after_a == after_b else ' ***'
            output_lines.append(blank+after_a+extra)
            output_lines.append('')
            gap_counter += 1
        return '\n'.join(output_lines), gap_counter
    return None, gap_counter


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

