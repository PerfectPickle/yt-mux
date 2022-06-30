"""
For use on Linux only. Wrapper for yt-dlp and ffmpeg which downloads and muxes the actual best streams available for a given YT URL, generally favouring VP9 and av01. Situationally avc will be chosen depending on bit rate differential. Downloads first to CWD then moves file to output location if specified.
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
    parser = argparse.ArgumentParser(description=__doc__, epilog="Dependencies: ffmpeg, yt-dlp, mediainfo")

    parser.add_argument("url", help="youtube URL to be processed", default=False)
    parser.add_argument("output", help="target output directory or file. If not specified, defaults to CWD", nargs='?', default=False)
    parser.add_argument("-r", action='store_true', help="make additional remux to Davinci Resolve friendly .mov file")
    parser.add_argument("-b", action='store_true', help="in case of a competing av01 stream, download both it AND the best VP9/AVC stream")
    parser.add_argument("-m", action='store_true', help="make separate mp3 file (cbr) transcode of downloaded m4a audio")
    parser.add_argument("-w", action='store_true', help="if video is downloaded to vp9.mkv, transcode audio to WAV (pcm_s16le) and mux into vp9 video (useful for DaVinci Resolve)")
    return parser


# parse and return args
def get_args():
    parser = create_parser()

    return parser.parse_args()

# return output as pathlib Path object if valid, else exit
def check_get_output_arg():
    if args.output:
        output = pathlib.Path(args.output)

        #if output is dir, or if directory to specified output file exists
        if output.is_dir() or pathlib.Path(os.path.split(str(args.output))[0]).is_dir():
            return output
        else:
            print("Invalid output.")
            ("-------------------------")
            exit()
    else:
        return False

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
        elif "avc" in line:
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

def determine_best_video_codec(vp9: video_stream_info, avc: video_stream_info):
    # to roughly equalize vp9 and avc quality-to-bitrate ratio. 
    # avc is considered higher quality if its bitrate is more than double a vp9
    avc_tbr_multiplier = 2.0

    if vp9.fps >= avc.fps and vp9.res >= avc.res and vp9.tbr * avc_tbr_multiplier >= avc.tbr:
        return vp9
    elif avc.fps >= vp9.fps and avc.res >= vp9.res and avc.tbr >= vp9.tbr * avc_tbr_multiplier:
        return avc
    else:
        print("---")
        print("Could not clearly determine if vp9 or avc stream is higher quality.")
        print("-------------------------")
        exit()

def download_streams(url, best_vid, vp9_best, avc_best, opus_best, m4a_best, av1_best):

    subprocess.call(["yt-dlp", "-o", "%(title)s [%(id)s]_%(vcodec)s.%(ext)s", "-f", str(best_vid.stream_id), url], shell=False)
    
    # download best muxable audio, AND m4a if option selected and m4a not muxable. or av1 is set to download
    if (vp9_best is best_vid and args.m) or (vp9_best is best_vid and av1_best and args.b):
        # download opus_best
        subprocess.call(["yt-dlp", "-o", "%(title)s [%(id)s]_%(acodec)s.%(ext)s", "-f", str(opus_best.stream_id), url], shell=False)
        # download m4a_best
        subprocess.call(["yt-dlp", "-o", "%(title)s [%(id)s]_%(acodec)s.%(ext)s", "-f", str(m4a_best.stream_id), url], shell=False)
    elif vp9_best is best_vid:
        subprocess.call(["yt-dlp", "-o", "%(title)s [%(id)s]_%(acodec)s.%(ext)s", "-f", str(opus_best.stream_id), url], shell=False)
    elif avc_best is best_vid:
        subprocess.call(["yt-dlp", "-o", "%(title)s [%(id)s]_%(acodec)s.%(ext)s", "-f", str(m4a_best.stream_id), url], shell=False)
    else:
        print("This shouldn't happen, ever.")

    # download best av01 stream if exists and args.b
    if av1_best and args.b:
        subprocess.call(["yt-dlp", "-o", "%(title)s [%(id)s]_%(acodec)s.%(ext)s", "-f", str(av1_best.stream_id), url], shell=False)

    # if str(args.output) != os.getcwd():
    #     subprocess.call(["mv", ])

# mux video file and audio file together
def mux(vid_to_mux, vp9_best, avc_best, av1_best, output):
    # get files
    cwd_files = os.scandir()

    if "youtu.be/" in str(args.url):
        video_ID = str(args.url).split(".be/")[1].split('/')[0]
    else:
        video_ID = str(args.url).split("/watch?v=")[1].split('/')[0]

    print(video_ID)

    video_file = False
    audio_file = False
    vcodec = "vp9"
    acodec = "opus"
    suffix = ".mkv"

    if avc_best is vid_to_mux:
        vcodec = "avc"
        acodec = "m4a"
        suffix = ".mp4"
    elif av1_best and av1_best is vid_to_mux:
        vcodec = "av01"
        acodec = "m4a"
        suffix = ".mp4"

    for file in cwd_files:
        if vcodec in file.name and video_ID in file.name and file.is_file():
            video_file = pathlib.Path(file.path)
        elif acodec in file.name and video_ID in file.name and file.is_file():
            audio_file = pathlib.Path(file.path)

    if video_file and audio_file:
        #muxed_file_name = str(video_file.with_suffix(".mkv").name).replace(vcodec, "muxed")
        muxed_file_name = str(video_file.name).split("[" + video_ID + "]")[0] + "[" + video_ID + "]_" + vcodec + "_muxed" + suffix
        muxed_file_name = muxed_file_name.replace(" ", "_")
        if not output:
            final_output_path = muxed_file_name
        elif output.is_dir():
            final_output_path = output.joinpath(muxed_file_name)
        elif args.output and output.parent.is_dir():
            final_output_path = str(output)

        subprocess.call(["toolbox", "run", "-c", "fedora_36", "ffmpeg", "-i", video_file.name, "-i", audio_file.name, "-c:v", "copy", "-c:a", "copy", final_output_path], shell=False)
        
        output_file = pathlib.Path(final_output_path)

    # rm pre-mux video and audio file
    # if bytes are more than 5 secs worth of video according to tbr (sec × tbr × 125) and mediainfo detected a video codec. 125 is kilobit to byte conversion rate so tbr * 125 = bytes/s
        if output_file.is_file() and os.path.getsize(final_output_path) >= (5 * int(vid_to_mux.tbr) * 125) and len(get_video_codec(final_output_path)) >= 3:
            os.remove(str(video_file.resolve()))
            os.remove(str(audio_file.resolve()))
        print(get_video_codec(final_output_path))

            
# returns 3+ letter video codec acronymn (uppercase) if video codec detected in file, else returns an empty string
def get_video_codec(file_path):
    try:
        src_codec = str(subprocess.check_output(["toolbox", "run", "-c", "fedora_36", 'mediainfo', "--output=Video;%Format%", file_path]))
    except:
        src_codec = "f"
            
    # clean subprocess output, to either isolate video codec, or reduce to empty string
    src_codec = src_codec.replace("b'", "")
    src_codec = src_codec.replace("\\n'", "")
    src_codec = src_codec.replace("\\r", "")

    return src_codec.upper() 
        

def remux_to_vp9mov():
    pass

def transcode_to_wav():
    pass

# does yt-dlp -F and returns a dict containing the ID code, resolution, fps, and bitrate of the highest quality video stream
def get_best_video_info(video_streams):
    # [10:19] is resolution, [21:24] is fps, [38:43] is bit rate 
    best_resolution = 0
    best_fps = 0
    highest_bitrate = 0
    best_code = 0
    for stream in video_streams:
        res = int(str(stream[9:19].replace("x", "").strip()))
        fps = int(stream[21:24].strip())
        tbr = int(stream[37:43].split("k")[0].strip())

        print(stream)
        print(res)
        print(fps)
        print(tbr)

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
    # [37:43] is bit rate 

    highest_bitrate = 0
    best_code = 0

    for stream in audio_streams:
        tbr = int(stream[37:43].split("k")[0].strip())

        if tbr >= highest_bitrate:
            highest_bitrate = tbr
            best_code = int(stream[0:3])
    
    best_audio_info = audio_stream_info(best_code, highest_bitrate)

    return best_audio_info


args = get_args()
output = check_get_output_arg()

# get best stream objects
vp9_best, avc_best, opus_best, m4a_best, av1_best = get_best_streams(str(args.url))
best_vid = determine_best_video_codec(vp9_best, avc_best)

download_streams(str(args.url), best_vid, vp9_best, avc_best, opus_best, m4a_best, av1_best)

mux(best_vid, vp9_best, avc_best, av1_best, output)
if av1_best and args.b:
    mux(av1_best, vp9_best, avc_best, av1_best, output)

print(args)