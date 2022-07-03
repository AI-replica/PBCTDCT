import subprocess
import os
import time

from utils import human_timestamp, print_and_log, is_file7

""" Records that the user hears, and saves the audio on regular intervals.

Troubleshooting:

dependencies: 
sudo apt-get install pulseaudio-utils lame mpg123

if no sound, check if you have several hardware outputs, and you capture the wrong one. Could happen if you attached headphones etc. 
pacmd list-sinks | grep -e 'name:' -e 'index' -e 'Speakers'

"""

# Stability settings
# reducing it makes the probability of data loss smaller.
# also reduces the risk of loosing data because the situation with sinks has changed (e.g. pluged in a headset)
# But if too small - will cause too many breaches in recordings, and will increase harddrive wear

save_frequency_min = 3

# Size/quality settings are described here:  https://linux.die.net/man/1/lame
variable_bitrate_quality = 9  # 0 <= n <= 9. Highest quality: 0

# max_allowed_bitrate can be 8, 16, 24, 32, 40, 48, 56, 64. The higher - the better quality.
# If set to -1 - not limits the bitrate.
max_allowed_bitrate = 24
# Observations:
# 8:  is too low for rock music. And it general the quality is way too low. Don't use it.
# 16: the lyrics is understandable even in rock (although only barely). But there are annoying sound artifacts.
# 24: lyrics is fully understdable. There are some slightly annoying sound artifacts, but nothing sirious.
# -1: the quality is perfect, but the file is larger

mono7 = True  # If true, will reduce stereo sound to mono


# get location of this very file to put the log in the same folder
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


def get_full_path_sound():
    filename = human_timestamp() + "sound.mp3"
    fullpath = os.path.join(__location__, filename)
    return fullpath


def get_all_sinks(raw_str):
    all_rows = raw_str.split("\n")
    counter = -1
    sinks_info = dict()

    first_index_row = -1
    for i in range(len(all_rows)):
        if "index:" in all_rows[i]:
            first_index_row = i
            break

    if first_index_row == -1:
        print_and_log("logger_headphone: Can't find any start of a sink info!")
        sinks_info = None
    else:
        for i in range(first_index_row, len(all_rows)):
            if "index:" in all_rows[i]:
                counter += 1
                sinks_info[counter] = []
            sinks_info[counter].append(all_rows[i])
    return sinks_info


def select_active_sink(sinks_info):
    res = 0
    for key, value in sinks_info.items():
        first_string = value[0]
        if "* index:" in first_string:
            res = key
            break
    return res


def extract_sink_name(raw_str):
    sinks_info = get_all_sinks(raw_str)

    if sinks_info is not None:
        active_sink_ind = select_active_sink(sinks_info)
        print("active_sink_ind:", active_sink_ind)

        rows = sinks_info[active_sink_ind]

        name_row = ""
        for row in rows:
            if "name:" in row:
                name_row = row
                break
        # name_row looks something like this:
        # "name: <alsa_output.pci-0000_00_14.2.analog-stereo>"
        name = name_row.partition("<")[2].partition(">")[0]
        monitor_str = ".monitor"
        if not monitor_str in name:
            name += monitor_str
        print("sink name:\n", name)
    else:
        name = None
    return name


def get_speakers_stream_str():
    # https://askubuntu.com/a/850174
    pacmd_command_str = "pacmd list-sinks"
    pacmd_command_list = pacmd_command_str.split(" ")
    raw_str = subprocess.run(pacmd_command_list, stdout=subprocess.PIPE).stdout.decode(
        "utf-8"
    )

    stream_str = extract_sink_name(raw_str)

    return stream_str


def build_main_command():

    timeout_command = "timeout"
    ending_time_str = str(save_frequency_min) + "m"

    speakers_stream_str = get_speakers_stream_str()

    if speakers_stream_str is not None:
        parec_fixed_part = "parec -d "
        parec_command = parec_fixed_part + speakers_stream_str
        pipe = "|"

        if max_allowed_bitrate != -1:
            max_bitstr = " -B" + str(max_allowed_bitrate)
        else:
            max_bitstr = ""
        bitrate_command = "-V" + str(variable_bitrate_quality) + max_bitstr
        if mono7:
            monostr = "-m s -a"
        else:
            monostr = ""
        base_lame_command = "lame -r"
        full_lame_command = (
            base_lame_command + " " + monostr + " " + bitrate_command + " -"
        )

        recording_command = parec_command + " " + pipe + " " + full_lame_command
        res = timeout_command + " " + ending_time_str + " " + recording_command
    else:
        res = None
    return res


def get_filesize_bytes(fpath):
    if is_file7(fpath):
        res = os.path.getsize(fpath)
    else:
        res = 0
    return res


def pathologically_small_previous_output7(fpath):
    if fpath != "":
        if get_filesize_bytes(fpath) < 2000:
            res = True
        else:
            res = False
    else:
        res = False
    return res


filename_str = ""

already_waited = False  # the already_waited logic below is useful for the cases where the user deleted the current audio file

if __name__ == "__main__":
    while True:

        print("\n\nlogger_headphone is entering a new circle.")
        print("already_waited:", str(already_waited))

        try:

            if already_waited or not pathologically_small_previous_output7(
                filename_str
            ):
                already_waited = False
                filename_str = get_full_path_sound()

                main_command = build_main_command()
                if main_command is not None:
                    full_command = main_command + " " + filename_str
                    print("recording comand:\n", full_command)

                    subprocess.run(full_command, shell=True)
                else:
                    print_and_log(
                        "logger_headphone: main_command is None. Skipping this circle, with a delay"
                    )
                    time.sleep(300)

            else:
                print_and_log(
                    "\n\n Caution: a patologically small previous record. Will sleep for a while"
                )
                time.sleep(300)  # Delay in seconds.
                already_waited = True

        except Exception as e:
            msg = "\n\nException in logger_headphone: " + str(e) + "\n\n"
            print_and_log(msg)
            # Delay in seconds. Don't set it below 300, to avoid flooding the harddrive with small damaged files (it happened)
            time.sleep(300)
            already_waited = True
