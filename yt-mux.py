"""
For use on Linux only. Wrapper for yt-dlp and ffmpeg which downloads and muxes the actual best streams available, generally favouring VP9 and av01. Situationally avc will be chosen depending on bit rate differential
"""
# the above docstring is accessible within the variable: __doc__

import argparse
import os
import subprocess
import pathlib

class video_stream_info:
    def __init__(self, stream_id, res, fps, tbr):
        self.stream_id=stream_id
        self.res=res
        self.fps=fps
        self.tbr=tbr

class audio_stream_info:
    def __init__(self, stream_id, tbr):
        self.stream_id=stream_id
        self.tbr=tbr


# create parser, add arguments, return parser
def create_parser():
    parser = argparse.ArgumentParser(description=__doc__, epilog="Dependencies: ffmpeg, yt-dlp")

    parser.add_argument("url", help="youtube URL to be processed", default=False)
    parser.add_argument("output", help="target output directory or file. If not specified, defaults to CWD", nargs='?', default=os.getcwd())
    parser.add_argument("-r", action='store_true', help="make additional remux to Davinci Resolve friendly .mov file")
    parser.add_argument("-b", action='store_true', help="in case of a competing av01 stream, download both it AND the best VP9/AVC stream")
    parser.add_argument("-m", action='store_true', help="download separate m4a audio and make separate WAV file (pcm_s16le) transcode of downloaded m4a audio (useful for DaVinci Resolve)")
    return parser


# parse and return args
def get_args():
    parser = create_parser()

    return parser.parse_args()


def check_args():
    output = pathlib.Path(args.output)

    #if output is dir, or if directory to specified output file exists
    if output.is_dir() or pathlib.Path(os.path.split(str(args.output))[0]).is_dir():
        pass
    else:
        print("Invalid output.")
        ("-------------------------")
        exit()


def get_best_streams(url):
    output = subprocess.check_output(["yt-dlp", "-F", url], shell=False)
    data = output.decode("utf-8")

    stream_info = data.split('\n')
    #data = os.system(str("yt-dlp -F " + url))
    vp9_streams = []
    avc_streams = []
    opus_streams = []
    m4a_streams = []
    av1_streams = []

    for line in stream_info:
        if "vp9" in line:
            vp9_streams.append(line)
        elif "avc" in line and "video only" in line:
            avc_streams.append(line)
        elif "opus" in line:
            opus_streams.append(line)
        elif "m4a" in line and "audio only" in line:
            m4a_streams.append(line)
        elif "av01" in line or "av1" in line:
            av1_streams.append(line)

    vp9_info = get_best_video_info(vp9_streams)
    avc_info = get_best_video_info(avc_streams)

    opus_info = get_best_audio_info(opus_streams)
    m4a_info = get_best_audio_info(m4a_streams)

    if args.b and len(av1_streams > 0):
        av1_info = get_best_video_info(av1_streams)
    else:
        av1_info = False
    
    return vp9_info, avc_info, opus_info, m4a_info, av1_info


def get_best_video_code(vp9: video_stream_info, avc: video_stream_info):
    # to roughly equalize vp9 and avc quality-to-bitrate ratio. 
    # avc is considered higher quality if its bitrate is more than double a vp9
    avc_tbr_multiplier = 2.0

    if vp9.fps >= avc.fps and vp9.res >= avc.res and vp9.tbr * avc_tbr_multiplier >= avc.tbr:
        return vp9.stream_id
    elif avc.fps >= vp9.fps and avc.res >= vp9.res and avc.tbr >= vp9.tbr * avc_tbr_multiplier:
        return avc.stream_id
    else:
        print("---")
        print("Could not clearly determine if vp9 or avc stream is higher quality.")
        print("-------------------------")
        exit()



def download_streams(url):
    vp9_best, avc_best, opus_best, m4a_best, av1_best = get_best_streams(url)

    best_vid_id = get_best_video_code(vp9_best, avc_best)
    subprocess.call(["yt-dlp", "-o", "%(title)s [%(id)s]_%(vcodec)s.%(ext)s", "-f", str(best_vid_id), url], shell=False)
    
    # if str(args.output) != os.getcwd():
    #     subprocess.call(["mv", ])



# mux video file and audio file together
def mux():
    pass


def remux_to_vp9mov():
    pass


def transcode_to_wav():
    pass


# does yt-dlp -F and returns a dict containing the ID code, resolution, fps, and bitrate of the highest quality video stream
def get_best_video_info(video_streams):
    # [10:19] is resolution, [22:24] is fps, [38:43] is bit rate 
    best_resolution = 0
    best_fps = 0
    highest_bitrate = 0
    best_code = 0
    for stream in video_streams:
        res = int(str(stream[10:19].replace("x", "")))
        fps = int(stream[22:24])
        tbr = int(stream[38:43].replace("k", ""))

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
                print("The best video stream could not be be clearly determined.")
                exit()

    print("----")
    print("best - for unique vcodec")
    print("code: " + str(best_code))
    print("res: " + str(best_resolution))
    print("fps: " + str(best_fps))
    print("tbr: " + str(highest_bitrate))

    best_video_info = video_stream_info(best_code, best_resolution, best_fps, highest_bitrate)

    return best_video_info


def get_best_audio_info(audio_streams):
    # [38:43] is bit rate 

    highest_bitrate = 0
    best_code = 0

    for stream in audio_streams:
        tbr = int(stream[38:43].replace("k", ""))

        if tbr >= highest_bitrate:
            highest_bitrate = tbr
            best_code = int(stream[0:3])
    
    best_audio_info = audio_stream_info(best_code, highest_bitrate)

    return best_audio_info


args = get_args()
#print(str(args.url))
download_streams(str(args.url))
print(args)