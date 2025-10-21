#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Airband Radio Demodulator
# Author: Kentaro1043
# GNU Radio version: 3.10.12.0

from gnuradio import blocks
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import osmosdr
import time
import threading




class airband_demodulator(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "Airband Radio Demodulator", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 2.4e6
        self.freq = freq = 128.8e6

        ##################################################
        # Blocks
        ##################################################

        self.rational_resampler_xxx_0 = filter.rational_resampler_ccc(
                interpolation=1,
                decimation=5,
                taps=[],
                fractional_bw=0)
        self.osmosdr_source_0 = osmosdr.source(
            args="numchan=" + str(1) + " " + "rtl=0"
        )
        self.osmosdr_source_0.set_time_unknown_pps(osmosdr.time_spec_t())
        self.osmosdr_source_0.set_sample_rate(samp_rate)
        self.osmosdr_source_0.set_center_freq(freq, 0)
        self.osmosdr_source_0.set_freq_corr(25, 0)
        self.osmosdr_source_0.set_dc_offset_mode(0, 0)
        self.osmosdr_source_0.set_iq_balance_mode(0, 0)
        self.osmosdr_source_0.set_gain_mode(True, 0)
        self.osmosdr_source_0.set_gain(40, 0)
        self.osmosdr_source_0.set_if_gain(20, 0)
        self.osmosdr_source_0.set_bb_gain(20, 0)
        self.osmosdr_source_0.set_antenna('', 0)
        self.osmosdr_source_0.set_bandwidth(0, 0)
        self.low_pass_filter_0_0 = filter.fir_filter_ccf(
            10,
            firdes.low_pass(
                1,
                samp_rate,
                10e3,
                5e3,
                window.WIN_HAMMING,
                6.76))
        self.blocks_multiply_const_vxx_0 = blocks.multiply_const_ff(32767.0)
        self.blocks_float_to_short_0 = blocks.float_to_short(1, 1)
        self.blocks_file_sink_0 = blocks.file_sink(gr.sizeof_short*1, './tmp/audio.pcm', True)
        self.blocks_file_sink_0.set_unbuffered(True)
        self.blocks_complex_to_mag_0 = blocks.complex_to_mag(1)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.blocks_complex_to_mag_0, 0), (self.blocks_multiply_const_vxx_0, 0))
        self.connect((self.blocks_float_to_short_0, 0), (self.blocks_file_sink_0, 0))
        self.connect((self.blocks_multiply_const_vxx_0, 0), (self.blocks_float_to_short_0, 0))
        self.connect((self.low_pass_filter_0_0, 0), (self.rational_resampler_xxx_0, 0))
        self.connect((self.osmosdr_source_0, 0), (self.low_pass_filter_0_0, 0))
        self.connect((self.rational_resampler_xxx_0, 0), (self.blocks_complex_to_mag_0, 0))


    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.low_pass_filter_0_0.set_taps(firdes.low_pass(1, self.samp_rate, 10e3, 5e3, window.WIN_HAMMING, 6.76))
        self.osmosdr_source_0.set_sample_rate(self.samp_rate)

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq
        self.osmosdr_source_0.set_center_freq(self.freq, 0)




def main(top_block_cls=airband_demodulator, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    tb.flowgraph_started.set()

    try:
        input('Press Enter to quit: ')
    except EOFError:
        pass
    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
