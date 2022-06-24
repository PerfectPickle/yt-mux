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

    parser.add_argument("url", help="youtube URL to be processed", default=False)
    parser.add_argument("output", help="target output directory or file. If not specified, defaults to CWD", nargs='?', default=os.getcwd())
    parser.add_argument("-r", action='store_true', help="make additional remux to Davinci Resolve friendly .mov file")
    parser.add_argument("-m", action='store_true', help="download separate m4a audio and make separate WAV file (pcm_s16le) transcode of downloaded m4a audio (useful for DaVinci Resolve)")
    return parser

# parse and return args
def get_args():
    parser = create_parser()

    return parser.parse_args()

def get_best_stream_codes(url):
    output = subprocess.check_output(["yt-dlp", "-F", url], shell=False)
    data = output.decode("utf-8")

    stream_info = data.split('\n')
    #data = os.system(str("yt-dlp -F " + url))
    vp9_streams = []
    opus_streams = []
    m4a_streams = []
    for line in stream_info:
        if "vp9" in line:
            vp9_streams.append(line)
        elif "opus" in line:
            opus_streams.append(line)
        elif "m4a" in line and "audio only" in line:
            m4a_streams.append(line)

    get_best_vp9_code(vp9_streams)
    # if line has equal/best fps, resolution, and file size, download.

# does yt-dlp -F and returns the ID code corresponding to the highest quality VP9 stream
def get_best_vp9_code(vp9_streams):
    # [10:19] is resolution, [22:24] is fps, [38:43] is bit rate 
    best_resolution = 0
    best_fps = 0
    highest_bitrate = 0
    best_code = 0
    for stream in vp9_streams:
        res = int(str(stream[10:19].replace("x", "")))
        fps = int(stream[22:24])
        tbr = int(stream[38:43])

        if res >= best_resolution and fps >= best_fps and tbr >= highest_bitrate:
            best_resolution = res
            best_fps = fps
            highest_bitrate = tbr
            best_code = int(stream[0:3])
        else:
            has_better = False
            if res >= best_resolution:
                print("resolution is better")
                has_better = True
            if fps >= best_fps:
                print("fps is better")
                has_better = True
            if tbr >= highest_bitrate:
                print("bitrate is higher")
                has_better = True

            if has_better:
                print("The best VP9 stream could not be be clearly determined.")
                exit()

    print("best ")
    print("code: " + best_code)
    print("res: " + best_resolution)
    print("fps: " + best_fps)
    print("tbr: " + highest_bitrate)

    return best_code


def get_best_opus_code():
    pass

def get_best_m4a_code():
    pass

args = get_args()
print(args)
print(str(args.url))
get_best_stream_codes(str(args.url))