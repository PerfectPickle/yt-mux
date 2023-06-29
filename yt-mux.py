"""
For use on Linux only. Wrapper for yt-dlp and ffmpeg which downloads and muxes the actual best streams available for a given YT URL, by deafult preferring avc. Downloads first to CWD then moves file to output location if specified. Looks for cookies.txt in ~/Downloads.
"""
# the above docstring is accessible within the variable: __doc__

import argparse
import os
import subprocess
import pathlib
import numpy
import time

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
    parser = argparse.ArgumentParser(description=__doc__, epilog="Dependencies: ffmpeg, yt-dlp, numpy")

    parser.add_argument("url", help="youtube URL to be processed", default=False)
    parser.add_argument("output", help="target output directory or file. If not specified, defaults to CWD", nargs='?', default=False)
    parser.add_argument("-a", action='store_true', help="all codecs - download & mux all codecs available for the highest resolution available.")
    parser.add_argument("-m", action='store_true', help="make separate mp3 ~245kbps transcode of audio")
    parser.add_argument("-k", action='store_true', help="keep premux audio files")
    parser.add_argument("-w", action='store_true', help="if video is downloaded to vp9.mkv, transcode audio to WAV (pcm_s16le) and mux into vp9 video (useful for DaVinci Resolve)")
    parser.add_argument("-v", action='store_true', help="only download av1 video")
    parser.add_argument("-p", action='store_true', help="only download vp9 video")
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
    cmd = ["yt-dlp", "-F", url]
    if cookies_dir_entry and cookies_dir_entry.is_file():
        cmd.append("--cookies")
        cmd.append(str(cookies_dir_entry.path))

    output = subprocess.check_output(cmd, shell=False)
    data = output.decode("utf-8")

    stream_info = data.split('\n')
    
    txt_offset = 0
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
        
        if "-dash" in line[0:8]:
            txt_offset = 5

    vp9_info = get_best_video_info(vp9_streams, txt_offset)
    avc_info = get_best_video_info(avc_streams, txt_offset)
    
    if len(av1_streams) > 0:
        av1_info = get_best_video_info(av1_streams, txt_offset)
    else:
        av1_info = False

    opus_info = get_best_audio_info(opus_streams, txt_offset)
    m4a_info = get_best_audio_info(m4a_streams, txt_offset)

    
    return vp9_info, avc_info, opus_info, m4a_info, av1_info

# returns cookies.txt path if found in ~/Downloads, else returns False
def get_cookies():
    entries = os.scandir(os.path.expanduser("~/Downloads"))
    for entry in entries:
        if entry.name == "cookies.txt":
            return entry
    return False

# returns a list of video_stream_info objects who meet the criteria of being at the maximum resolution available
def get_streams_of_highest_res(vp9, avc, av1):
    inputs = [vp9, avc]
    if av1:
        inputs.append(av1)

    highest_res = 0
    for stream in inputs:
        if int(stream.res) > highest_res:
            highest_res = int(stream.res)

    avail_in_highest_res = []
    for stream in inputs:
        if int(stream.res) == highest_res:
            avail_in_highest_res.append(stream)

    return avail_in_highest_res

def determine_best_video_codec(vp9: video_stream_info, avc: video_stream_info):
    # to roughly equalize vp9 and avc quality-to-bitrate ratio. 
    # avc is considered higher quality if its bitrate is more that of vp9_tbr * avc_tbr_multiplier
    avc_tbr_multiplier = 1.5
    
    if avc.fps >= vp9.fps and avc.res >= vp9.res: # and avc.tbr >= vp9.tbr * avc_tbr_multiplier:
        return avc
    elif vp9.fps >= avc.fps and vp9.res >= avc.res: # and vp9.tbr * avc_tbr_multiplier >= avc.tbr:
        return vp9
    else:
        print("---")
        print("Could not clearly determine if vp9 or avc stream is higher quality.")
        print("-------------------------")
        exit()

def try_download_stream(cmd):
    attempts = 0
    dl_completed = False
    while not dl_completed:
        returncode = subprocess.call(cmd, shell=False)
        if int(returncode) == 0:
            dl_completed = True
            attempts = 0
        else:
            attempts += 1
            if attempts >= 100:
                print("---")
                print("Download failed after 100 attempts. Exiting..")
                print("-------------------------")
                exit()
            else:
                print("---")
                print("Download attempt #" + str(attempts) + " failed. Trying again in 5 seconds.. ")
                print("---")
                time.sleep(5)

def download_streams(url, stream_to_dl, vp9_best, avc_best, opus_best, m4a_best, av1_best):

    vid_cmd = ["yt-dlp", "-o", "%(title)s [%(id)s]_%(vcodec)s.%(ext)s", "-f", str(stream_to_dl.stream_id), url]
    opus_cmd = ["yt-dlp", "-o", "%(title)s [%(id)s]_%(acodec)s.%(ext)s", "-f", str(opus_best.stream_id), url]
    m4a_cmd = ["yt-dlp", "-o", "%(title)s [%(id)s]_%(acodec)s.%(ext)s", "-f", str(m4a_best.stream_id), url]

    # add cookies to cmd
    if cookies_dir_entry and cookies_dir_entry.is_file():
        vid_cmd.append("--cookies")
        vid_cmd.append(str(cookies_dir_entry.path))
        opus_cmd.append("--cookies")
        opus_cmd.append(str(cookies_dir_entry.path))
        m4a_cmd.append("--cookies")
        m4a_cmd.append(str(cookies_dir_entry.path))

    try_download_stream(vid_cmd)

    # download best muxable audio, AND m4a if option selected and m4a not muxable. or av1 is set to download
    if vp9_best is stream_to_dl:
        try_download_stream(opus_cmd)
    elif avc_best is stream_to_dl or av1_best is stream_to_dl:
        try_download_stream(m4a_cmd)
    else:
        print("This shouldn't happen, ever.")

# mux video file and audio file together, returns list of premux files to remove as pathlib.Path() objects
def mux(vid_to_mux, vp9_best, avc_best, av1_best, output):
    # get files
    cwd_files = os.scandir()

    if "youtu.be/" in str(args.url):
        video_ID = str(args.url).split(".be/")[1].split('/')[0]
    elif "/shorts/" in str(args.url):
        video_ID = str(args.url).split("/shorts/")[1].split('/')[0]
    else:
        video_ID = str(args.url).split("/watch?v=")[1].split('/')[0]

    print(video_ID)

    files_to_rm = []
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

    if args.w and vcodec == "vp9":
        acodec = "m4a"

    for file in cwd_files:
        if vcodec in file.name and video_ID in file.name and file.is_file():
            video_file = pathlib.Path(file.path)
        elif acodec in file.name and video_ID in file.name and file.is_file():
            audio_file = pathlib.Path(file.path)

    if video_file and audio_file:
        #muxed_file_name = str(video_file.with_suffix(".mkv").name).replace(vcodec, "muxed")
        muxed_file_name = str(video_file.name).split("[" + video_ID + "]")[0] + "[" + video_ID + "]_" + vcodec + "_muxed" + suffix
        muxed_file_name = muxed_file_name.replace(" ", "_")
        muxed_file_name = muxed_file_name.replace("__", "")
        muxed_file_name = muxed_file_name.replace("___", "")

        if not output:
            final_output_path = muxed_file_name
        elif output.is_dir():
            final_output_path = output.joinpath(muxed_file_name)
        elif args.output and output.parent.is_dir():
            final_output_path = str(output)

        mux_cmd = ["toolbox", "run", "ffmpeg", "-i", video_file.name, "-i", audio_file.name, "-c:v", "copy", "-c:a", "copy", final_output_path]
        if args.w and vcodec == "vp9":
            mux_cmd[12] = "pcm_s16le"
        subprocess.call(mux_cmd, shell=False)
        
        output_file = pathlib.Path(final_output_path)

    # rm pre-mux video and audio file
    # if bytes are more than 5 secs worth of video according to tbr (sec × tbr × 125). 125 is kilobit to byte conversion rate so tbr * 125 = bytes/s
        if output_file.is_file() and os.path.getsize(final_output_path) >= (5 * int(vid_to_mux.tbr) * 125):
            files_to_rm.append(video_file)
            if not args.k:
                files_to_rm.append(audio_file)

    if audio_file and args.m and mp3_transcode_made == False:
        transcode_to_mp3(audio_file, video_ID)

    return files_to_rm

def remove_premux_files(files_to_rm):
    for file in files_to_rm:
        if file.is_file():
            os.remove(str(file.resolve()))

# currently broken as toolbox mediainfo is not working with "toolbox run" anymore
# returns 3+ letter video codec acronymn (uppercase) if video codec detected in file, else returns an empty string
def get_video_codec(file_path):
    try:
        src_codec = str(subprocess.check_output(["toolbox", "run", 'mediainfo', "--output=Video;%Format%", file_path]))
    except:
        src_codec = "f"
    
    print(src_codec)

    # clean subprocess output, to either isolate video codec, or reduce to empty string
    src_codec = src_codec.replace("b'", "")
    src_codec = src_codec.replace("\\n'", "")
    src_codec = src_codec.replace("\\r", "")

    print(src_codec)

    return src_codec.upper() 

def transcode_to_mp3(file, video_ID):
    output = str(file.name).split("[" + video_ID + "]")[0] + "[" + video_ID + "]" + ".mp3"
    output = output.replace(" ", "_")
    output = output.replace("__", "")
    output = output.replace("___", "")

    subprocess.call(["toolbox", "run", "ffmpeg", "-i", file.name, "-c:a", "libmp3lame", "-q:a", "0", output], shell=False)
    global mp3_transcode_made
    mp3_transcode_made = True

# processes yt-dlp -F output line (streams arg) and returns a dict containing the ID code, resolution, fps, and bitrate of the highest quality video stream
def get_best_video_info(video_streams, stream_offset: int):
    # [9:19] is resolution, [21:24] is fps, [37:43] is bit rate 
    res_start = 9
    res_end = 19
    fps_start = 21
    fps_end = 24
    tbr_start = 40
    tbr_end = 46

    if stream_offset > 0:
        res_start, res_end, fps_start, fps_end, tbr_start, tbr_end = numpy.add([res_start, res_end, fps_start, fps_end, tbr_start, tbr_end], stream_offset)
        
    best_resolution = 0
    best_fps = 0
    highest_bitrate = 0
    best_code = 0
    for stream in video_streams:
        res = int(str(stream[res_start:res_end].replace("x", "").strip()))
        fps = int(stream[fps_start:fps_end].strip())

        tbr = stream[tbr_start:tbr_end].split("k")[0].strip()
        tbr = tbr.replace("B", "")
        tbr = tbr.replace("i", "")
        tbr = int(tbr)

        # not comparing tbr, to place a premium on res and fps, because sometiems lower res streams will have higher tbr than higher res ones.
        if res >= best_resolution and fps >= best_fps:
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
            # if tbr >= highest_bitrate:
            #     print("bitrate is higher")
            #     has_better = True

            if has_better:
                print("The best video stream could not be be clearly determined.")
                exit()

    # print("----")
    # print("best - for unique vcodec")
    # print("code: " + str(best_code))
    # print("res: " + str(best_resolution))
    # print("fps: " + str(best_fps))
    # print("tbr: " + str(highest_bitrate))

    best_video_info = video_stream_info(best_code, best_resolution, best_fps, highest_bitrate)

    return best_video_info

def get_best_audio_info(audio_streams, stream_offset: int):
    # [37:43] is bit rate 
    tbr_start = 40
    tbr_end = 46

    if stream_offset > 0:
        tbr_start, tbr_end = numpy.add([tbr_start, tbr_end], stream_offset)

    highest_bitrate = 0
    best_code = 0

    for stream in audio_streams:
        tbr = stream[tbr_start:tbr_end].split("k")[0].strip()
        tbr = tbr.replace("B", "")
        tbr = tbr.replace("i", "")
        tbr = int(tbr)
        
        if tbr >= highest_bitrate:
            highest_bitrate = tbr
            best_code = int(stream[0:3])
    
    best_audio_info = audio_stream_info(best_code, highest_bitrate)

    return best_audio_info


args = get_args()
output = check_get_output_arg()

cookies_dir_entry = get_cookies()
mp3_transcode_made = False

# get best stream objects
vp9_best, avc_best, opus_best, m4a_best, av1_best = get_best_streams(str(args.url))

if args.a:
    streams_to_dl = get_streams_of_highest_res(vp9_best, avc_best, av1_best)
elif args.v:
    if av1_best and av1_best in get_streams_of_highest_res(vp9_best, avc_best, av1_best):
        streams_to_dl = [av1_best]
    else:
        print("---")
        print("Found no av1 video of highest res (any codec). Exiting..")
        print("-------------------------")
        exit()
elif args.p:
    streams_to_dl = [vp9_best]
else:
    streams_to_dl = [(determine_best_video_codec(vp9_best, avc_best))]


for stream in streams_to_dl:
    download_streams(str(args.url), stream, vp9_best, avc_best, opus_best, m4a_best, av1_best)
    # mux stream with audio and get premux files
    premux_files = mux(stream, vp9_best, avc_best, av1_best, output)
    remove_premux_files(premux_files)

print(args)