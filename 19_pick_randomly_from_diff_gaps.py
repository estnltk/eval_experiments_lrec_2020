#
#   Script for making random selections from *__diff_gaps.txt files.
#   Random selections are for manual evaluation.
#  

import re, sys
import os, os.path
from collections import defaultdict

from random import randint

class MorphDiffCounter():
    '''Records information about morph_analysis diff gaps. Prints summarizing statistics after processing the file.'''
    
    def __init__( self ):
        self.morph_diff_pattern_1 = re.compile('^\s*---\s*([A-Z]+)\s+---+\s*$')
        self.morph_diff_pattern_2 = re.compile('^\s*---\s*(MODIFIED)\s+(\[[^\[\]]+\])\s*---+\s*$')
        self.morph_line_pattern   = re.compile('^\s*([a-z0-9_]+)\s+(\[[^\[\]]+?\]).*$')
        self.last_morph_diff_type    = None
        self.last_morph_diff_subtype = None
        self.last_morph_diff_count = 0
        self.separator = '=================='
        self.diff_counter = defaultdict(int)

    def finalize_last_item( self ):
        if self.last_morph_diff_type != None:
            assert self.last_morph_diff_count > 0 or self.last_morph_diff_type == 'MODIFIED'
            if self.last_morph_diff_type == 'MODIFIED' and self.last_morph_diff_count == 0:
                self.last_morph_diff_count = 1
            key = self.last_morph_diff_type
            if self.last_morph_diff_subtype is not None:
                key += ' '+self.last_morph_diff_subtype
            self.diff_counter[ key ] += self.last_morph_diff_count
            self.last_morph_diff_type    = None
            self.last_morph_diff_subtype = None
            self.last_morph_diff_count = 0

    def process_line( self, line ):
        # Collect morph annotation markings:
        morph_diff_match1 = self.morph_diff_pattern_1.match(line)
        morph_diff_match2 = self.morph_diff_pattern_2.match(line)
        if morph_diff_match1:
            self.finalize_last_item()
            self.last_morph_diff_type    = morph_diff_match1.group(1)
            self.last_morph_diff_subtype = None
        if morph_diff_match2:
            self.finalize_last_item()
            self.last_morph_diff_type    = morph_diff_match2.group(1)
            self.last_morph_diff_subtype = morph_diff_match2.group(2)
        if not morph_diff_match1 and not morph_diff_match2:
            morph_line_match = self.morph_line_pattern.match(line)
            if morph_line_match:
                if self.last_morph_diff_type in ['COMMON', 'MODIFIED']:
                    if self.last_morph_diff_count == 0:
                        self.last_morph_diff_count = 1
                else:
                    assert self.last_morph_diff_type in ['EXTRA', 'MISSING']
                    self.last_morph_diff_count += 1
            else:
                self.finalize_last_item()
        if self.separator in line:
            self.finalize_last_item()

    def has_items( self ):
        return len(self.diff_counter.keys()) > 0

    def print_stats( self ):
        print('Differences by annotation match type:')
        total = sum([ self.diff_counter[k] for k in self.diff_counter.keys() ])
        print(' ',total, ' ({:.2f}%) '.format(100.0), ' TOTAL')
        print()
        for indx in sorted(self.diff_counter.keys(), key=self.diff_counter.get, reverse=True ):
            per = (self.diff_counter[indx] / total)*100.0
            print(' ',self.diff_counter[indx], ' ({:.2f}%) '.format(per), ' ',indx)
        print()


# Number of random items to be picked per subcorpus
rand_pick_per_subcorpus = 20

if len(sys.argv) > 1:
    diff_file = sys.argv[1]
    assert os.path.exists( diff_file ), '(!) Input file {} not found!'.format( diff_file )
    is_morph_analysis_diff = 'morph_analysis' in diff_file
    # Collect all diff gaps
    #   nc_periodicals::nc_255_27990::2
    pattern_diff_index = re.compile('^\s*([^: ]+)::([^: ]+)::(\d+)\s*$')
    morph_diff_counter = MorphDiffCounter()
    diff_gaps = defaultdict(list)
    print('Collecting indexes ...')
    with open(diff_file, 'r', encoding='utf-8') as in_f:
        for line in in_f:
            line = line.strip()
            diff_ind_match = pattern_diff_index.match( line )
            if diff_ind_match:
                corpus_ind = diff_ind_match.group(1)
                diff_gaps[corpus_ind].append( line )
            if is_morph_analysis_diff:
                morph_diff_counter.process_line( line )
    if is_morph_analysis_diff:
        morph_diff_counter.finalize_last_item()
    
    # Summary statistics
    print('Differences by subcorpus:')
    total = sum([ len(diff_gaps[k]) for k in diff_gaps.keys() ])
    print(' ',total, ' ({:.2f}%) '.format(100.0), ' TOTAL')
    print()
    for corpus_ind in sorted(diff_gaps.keys(), key=lambda x: len(diff_gaps[x]), reverse=True ):
        per = (len(diff_gaps[corpus_ind]) / total)*100.0
        print(' ',len(diff_gaps[corpus_ind]), ' ({:.2f}%) '.format(per), ' ',corpus_ind)
    print()
    if morph_diff_counter.has_items():
        # Detailed statistics about morph annotations
        morph_diff_counter.print_stats()
    print('Picking randomly {} from each subcorpus'.format(rand_pick_per_subcorpus))
    diff_gap_picks = defaultdict(set)
    for corpus_ind in sorted(diff_gaps.keys(), key=lambda x: len(diff_gaps[x]), reverse=True ):
        corpus_total = len(diff_gaps[corpus_ind])
        failed_attempts = 0
        while len( diff_gap_picks[corpus_ind] ) < rand_pick_per_subcorpus:
            i = randint(0, corpus_total - 1)
            gap_ind = diff_gaps[corpus_ind][i]
            if gap_ind not in diff_gap_picks[corpus_ind]:
                diff_gap_picks[corpus_ind].add(gap_ind)
                failed_attempts = 0
            else:
                failed_attempts += 1
                if failed_attempts >= 20:
                    print('(!) 20 unsuccessful random picks in a row: terminating ...')
                    break
    pattern_separator = ('='*85)
    print('Collecting randomly picked examples ...')
    lines_of_rand_picked_examples = []
    collected_for_corp_id = defaultdict(int)
    with open(diff_file, 'r', encoding='utf-8') as in_f:
        collected_lines = []
        pickable_line = False
        last_corpus_ind = None
        for line in in_f:
            line = line.strip()
            diff_ind_match = pattern_diff_index.match( line )
            if diff_ind_match:
                corpus_ind = diff_ind_match.group(1)
                for gap_id in diff_gap_picks[corpus_ind]:
                    if gap_id in line:
                        pickable_line = True
                        last_corpus_ind = corpus_ind
                        break
            collected_lines.append(line)
            if pattern_separator in line:
                if pickable_line:
                    lines_of_rand_picked_examples.extend( collected_lines )
                    collected_for_corp_id[last_corpus_ind] += 1
                collected_lines = []
                pickable_line = False
    for k in collected_for_corp_id.keys():
        print(' ',collected_for_corp_id[k], ' ',k)
    in_f_head, in_f_tail = os.path.split(diff_file)
    in_f_root, in_f_ext = os.path.splitext(in_f_tail)
    assert in_f_ext == '' or in_f_ext.startswith('.')
    c = 1
    out_fname = '{}x{}{}'.format(in_f_root, rand_pick_per_subcorpus, in_f_ext)
    while os.path.exists( out_fname ):
        out_fname = '{}x{}_{}{}'.format(in_f_root, rand_pick_per_subcorpus, c, in_f_ext)
        c += 1
    print( ' Saving into {} ...'.format(out_fname) )
    with open(out_fname, 'w', encoding='utf-8') as out_f:
        for line in lines_of_rand_picked_examples:
            out_f.write(line.rstrip())
            out_f.write('\n')
    print( 'Done.')
else:
    print('(!) Please give diff gaps file as an input.')

