"""
For use on Linux only. Wrapper for yt-dlp and ffmpeg which downloads and muxes the actual best webm streams available.
"""
# the above docstring is accessible within the variable: __doc__

import argparse
import os
import subprocess
import pathlib

# create parser, add arguments, return parser
def create_parser():
    parser = argparse.ArgumentParser(description=__doc__, epilog="Dependencies: ffmpeg, yt-dlp")

    parser.add_argument("url", help="youtube URL to be processed", required=True)
    parser.add_argument("output", help="target output directory or file. If not specified, defaults to CWD", default=os.getcwd())
    parser.add_argument("-r", action='store_true', help="make additional remux to Davinci Resolve friendly .mov file")
    parser.add_argument("-m", action='store_true', help="download separate m4a audio and make separate WAV file (pcm_s16le) transcode of downloaded m4a audio (useful for DaVinci Resolve)")
    return parser