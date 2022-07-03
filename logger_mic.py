"""Records the microphone audio and saves it to .wav.

It records only when the sound level exceeds a predefined volume threshold to save space.

----------------------- TROUBLESHOOTING:-----------------------
 
If there is a gcc-related problem with pyaudio, install this stuff:
sudo apt-get install libasound-dev portaudio19-dev libportaudio2 libportaudiocpp0
 
could also be necessary:
sudo apt-get install libatlas-base-dev
  

if there is problem with 'src/hostapi/alsa/pa_linux_alsa.c'
sudo apt-get update
sudo apt-get upgrade


"""

import datetime
import random
import configparser
import math

import statistics
import struct
import argparse

from array import array
from sys import byteorder

import wave
import os
import traceback

from ctypes import CFUNCTYPE, c_char_p, c_int, cdll
from contextlib import contextmanager  # ALSA error handling
import time


def print_and_log(my_text1, my_text2="", dummy_log_path=None, mode="a"):
    """Writes down the given text to a file. Also prints it to the console.

    Args:
        my_text1: str: the text to be written and printed
        my_text2: str: optional: could be added to the aforementioned text
        dummy_log_path: str: optional: could be used as the write path
        mode: str: optional: can be "w" (rewrite the file) or the default "a" (add to the file)
    Returns:
        None

    >>> set_c_print_switch(True)
    >>> path = "dummy_log.txt"
    >>> with open(path, "w") as f:
    ...     _ = f.write("")
    >>> print_and_log("first text", "second text", dummy_log_path="dummy_log.txt", mode="w")
    first text second text
    >>> with open(path) as f:
    ...     lines = f.readlines()
    >>> "first text second text" in lines[0]
    True
    """
    c_print(my_text1, my_text2)

    log_path = "logger_mic_log.txt"
    if isinstance(dummy_log_path, str):
        log_path = dummy_log_path

    with open(log_path, mode) as fff:
        fff.write(
            filename_timestamp() + " - " + str(my_text1) + " " + str(my_text2) + "\n"
        )
    fff.close()


try:
    import gc
    import pyaudio
except Exception as e:
    msg = "\n\nException while trying to import gc or pyaudio: " + str(e) + "\n\n"
    print_and_log(msg)


c_print_verbose7 = True  # if true, the c_print func will print to stdout


def set_c_print_switch(input_bool):
    """A helper func for c_print(). Controls if c_print() will print or not, which is useful for doc tests.

    Args:
        input_bool: bool: if True, c_print() will print. If False - otherwise.
    Returns:
        None
    """
    global c_print_verbose7
    c_print_verbose7 = input_bool


def c_print(*args):
    """same as print(), but prints only if the c_print_verbose7 == True.

    Useful for debug purposes.

    >>> backup_value = c_print_verbose7
    >>> set_c_print_switch(False)
    >>> c_print("some", {"values" : "here"})
    >>> set_c_print_switch(True)
    >>> c_print("some", {"values" : "here"})
    some {'values': 'here'}
    >>> set_c_print_switch(backup_value)
    """

    if c_print_verbose7:
        print(*args)


def filename_timestamp(custom_datetime=None, random_last_digit7=True):
    """Returns an unique string like this: 202104191244500001, which depends on the current time and random.

    Useful for the cases there you want to write down a file with an unique filename containing the time of its creation

    Args:
        custom_datetime: datetime obj: optional: if you provide it, it will be used instead of the current datetime
        random_last_digit7: bool: optional: if set to False, the result will become deterministic
    Returns:
        time_st: string: a string like this: 202104191244500001

    >>> set_c_print_switch(False)
    >>> res0 = filename_timestamp()
    >>> int(res0) > 202102211006412344 # the time this test was created
    True
    >>> dt = datetime.datetime(year=1984, month=4, day=19, hour=12, minute=44, second=50, microsecond=1)
    >>> filename_timestamp(custom_datetime=dt)[:-1]
    '19840419124450000'
    """
    if isinstance(custom_datetime, datetime.datetime):
        now = custom_datetime
    else:
        now = datetime.datetime.now()
    time_st = now.strftime("%Y%m%d%H%M%S%f")[:-3]

    # random - to avoid rewriting the log if made at the same millisecond
    if random_last_digit7 and custom_datetime is None:
        time_st += str(random.randint(0, 9))
    else:
        time_st += "0"
    return time_st


def read_config():
    """Returns a dict with all the settings, read from config.ini

    Args:
        No args
    Returns:
        res: dict: the key is the setting name, the value is the setting value

    """
    pa = configparser.ConfigParser()
    pa.read("config.ini")

    res = dict()

    res["indicator_part"] = pa.get("hardware", "indicator_part", fallback="USB")
    res["sound_dev_part"] = pa.get("hardware", "sound_dev_part", fallback="pulse")
    res["frame_rate"] = pa.getint("hardware", "frame_rate", fallback=48000)
    res["channels"] = pa.getint("hardware", "channels", fallback=1)
    res["chunk_size"] = pa.getint("hardware", "chunk_size", fallback=4098)

    # originally was defined as = pyaudio.paInt16
    res["sampling_format"] = pa.getint("quality", "sampling_format", fallback=8)

    res["chunk_break_num"] = pa.getint("quality", "chunk_break_num", fallback=430)

    res["trim_level"] = pa.getint("filter", "trim_level", fallback=0)
    res["calibrate_num"] = pa.getint("filter", "calibrate_num", fallback=100)
    res["min_relative_l"] = pa.getint("filter", "min_relative_l", fallback=250)
    res["max_relative_l"] = pa.getint("filter", "max_relative_l", fallback=1700)
    res["consecutive_num"] = pa.getint("filter", "consecutive_num", fallback=2)
    res["silent_num"] = pa.getint("filter", "silent_num", fallback=10)
    res["breath_min_data"] = pa.getint("breathing", "breath_min_data", fallback=1000)

    res = add_calculated_config_keys(res)

    return res


def add_calculated_config_keys(config):
    """Augments the config with a few additional entries, calculated from other entries.

    Args:
        config: dict: the key is the setting name, the value is the setting value
    Returns:
        config: dict: the same stuff, but with a few additional entries
    """
    frame_max_value = 2 ** 15 - 1
    normalize_minus_one_d_b = 10 ** (-1.0 / 20)
    config["normalisation_val"] = float(normalize_minus_one_d_b * frame_max_value)
    config["trim_append"] = config["frame_rate"] * 4
    return config


config_dic = read_config()

dyn_level = 0
breathing_raw_data = []
start_time = None

# ALSA error handling:
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)


def py_error_handler(filename, line, function, err, fmt):  # noqa
    """Error handler for sound_lib. Does nothing, but is probably necessary

    >>> py_error_handler("filename", "line", "function", "err", "fmt")

    """
    pass


c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)


@contextmanager
def sound_handler():
    """A wrapper for libasound.so. Used in constructions like this: "with sound_handler():" . No idea how it works.

    Args:
        No args
    Returns:
        Some strange stuff


    >>> type(sound_handler())
    <class 'contextlib._GeneratorContextManager'>
    >>> with sound_handler():
    ...    pyaudio_obj = pyaudio.PyAudio()
    ...    type(pyaudio_obj)
    <class 'pyaudio.PyAudio'>
    """
    sound_lib = cdll.LoadLibrary("libasound.so")
    sound_lib.snd_lib_error_set_handler(c_error_handler)
    yield
    sound_lib.snd_lib_error_set_handler(None)


def get_absolute_threshold(dynamic_level, percent_louder_than_background):
    """
    >>> get_absolute_threshold(42, 200)
    84.0
    """
    return percent_louder_than_background * dynamic_level / 100


def chunk_is_silent(data_chunk, percent_louder_than_background, dynamic_level=0.0):
    """Returns 'True' if below the 'silent' threshold

    >>> test_chunk0 = [0.3, 0.1, 0.4, 0.1, 0.5]
    >>> percent_louder = 200
    >>> test_dyn_level = 1
    >>> chunk_is_silent(test_chunk0, percent_louder, dynamic_level=test_dyn_level)
    True
    >>> test_chunk1 = [300, 100, 400, 100, 500]
    >>> chunk_is_silent(test_chunk1, percent_louder, dynamic_level=test_dyn_level)
    False
    """
    abs_thresh = get_absolute_threshold(dynamic_level, percent_louder_than_background)
    res = top3avg(data_chunk) - dynamic_level < abs_thresh
    return res


def safe_array_max(input_arr, default=0):
    """Returns max of a list or an array. Unlike the usual max, it doesn't crash if the input is a junk

    Args:
        input_arr: list or array: this func calculates the max of it
        default: optional: the stuff that will be returned if the input list/array is junk, an max doesn't make sense
    Returns:
        res: the max of input_arr
    """
    res = default

    if isinstance(input_arr, type(array("h"))) or isinstance(input_arr, list):
        clean_list = []
        for element in input_arr:
            if isinstance(element, int) or isinstance(element, float):
                clean_list.append(element)
        if len(clean_list) > 0:
            res = max(clean_list)

    return res


def trim(data_all, trimming_thresh, trimming_append):
    """Removes the left and the right of the data_all array according the given threshold, to reduce the file size

    Args:
        data_all: array: the data that must be trimmed
        trimming_thresh: int/float: the value must be higher than this to stay in the array
        trimming_append: int: how many elements to keep from the left and right, even if they don't pass the threshold
    Returns:
        res: array: same as data_all, but without the trimmed elements

    TODO: use the dynamic thresholding as in the rest of the code

    >>> test_data0 = array("h")
    >>> test_data0.extend([1, 4, 1, 5, 9, 2])
    >>> trim(test_data0,trimming_thresh=4, trimming_append=0)
    array('h', [5, 9])
    >>> trim(test_data0,trimming_thresh=4, trimming_append=1)
    array('h', [1, 5, 9, 2])
    >>> trim(test_data0,trimming_thresh=4, trimming_append=5)
    array('h', [1, 4, 1, 5, 9, 2])
    """
    res = array("h")

    if isinstance(data_all, type(array("h"))):
        if len(data_all) > 0:

            _from = 0
            _to = len(data_all) - 1
            for i, b in enumerate(data_all):
                if abs(b) > trimming_thresh:
                    _from = int(max(0, i - trimming_append))
                    break

            for i, b in enumerate(reversed(data_all)):
                if abs(b) > trimming_thresh:
                    candidate_a = len(data_all) - 1
                    candidate_b = len(data_all) - 1 - i + trimming_append
                    _to = int(min(candidate_a, candidate_b))
                    break

            res = data_all[_from : (_to + 1)]

    return res


def count_higher_than_value(input_list, value):
    """Counts the elements in input_list that are higher than the given value.

    Args:
        input_list: list or array: where the elements are counted
        value: int or float: we count only the elements higher than this
    Returns:
        res: int: number of the elements higher than the value

    >>> test_data0 = array("h")
    >>> test_data0.extend([3, 1, 4, 1, 5, -2])
    >>> count_higher_than_value(test_data0, 2)
    3
    >>> count_higher_than_value(test_data0, 6)
    0
    >>> count_higher_than_value(array("h"), 6)
    0
    """
    res = 0
    for element in input_list:
        if isinstance(element, float) or isinstance(element, int):
            if element > value:
                res += 1
    return res


def percentage_of_elements_higher_than_value(input_list, value):
    """Returns the percentage (e.g. 99) of the elements that are higher than the value.

    Args:
        input_list: list or array: the elements of this stuff are evaluated here
        value: int or float: we count only the elements higher than this
    Returns:
        percentage: float: e.g. 42 (meaning: 42%)


    >>> test_data0 = array("h")
    >>> test_data0.extend([3, 1, 4, 1, 5, -2])
    >>> percentage_of_elements_higher_than_value(test_data0, 2)
    50.0
    >>> percentage_of_elements_higher_than_value(test_data0, 6)
    0.0
    >>> percentage_of_elements_higher_than_value(test_data0, -10)
    100.0
    >>> percentage_of_elements_higher_than_value(array("h"), -10)
    100.0
    """
    counter = count_higher_than_value(input_list, value)
    if len(input_list) > 0:
        percentage = 100 * counter / len(input_list)
    else:
        percentage = 100.0
    return percentage


def top3avg(input_list):
    """Returns the average of the top 3 biggest elements in the list.

    Args:
        input_list: list or array: the elements of this stuff are evaluated here
    Returns:
        res: float: the average

    TODO: assume that the list could contain non-integers and non-floats. Implement measures to avoid crashes

    >>> test_list0 = array("h")
    >>> test_list0.extend([3, 1, 4, 1, 5])
    >>> top3avg(test_list0)
    4.0
    >>> test_list1 = array("h")
    >>> test_list1.extend([3, 1])
    >>> top3avg(test_list1)
    3
    """
    if len(input_list) > 2:
        temp = sorted(input_list, reverse=True)
        res = (temp[0] + temp[1] + temp[2]) / 3
    else:
        res = safe_array_max(input_list, default=0)
    return res


def log_plot(value):
    """Returns a string like '######'. The bigger is the input value, the more '#'s. Useful for volume visualisations

    Args:
        value: int or float: some value to be visualized
    Returns:
        res: string: looks like this: '######'

    TODO: simplify this func by using stuff like this: '#' * 20

    >>> log_plot(50)
    ''
    >>> log_plot(100)
    '####'
    >>> log_plot(150)
    '######'
    """
    res = ""
    log_value = int(value / 50)
    if log_value > 1:
        for lp in range(log_value):
            res += "##"
    return res


def console_indicator(data_chunk, dynamic_level, chunks_counter, silent_chunks, config):
    """Prints the current sound volume and some debug output

    Args:
        data_chunk: array of ints: raw audio data
        dynamic_level: float: background noise level
        chunks_counter: int: the current index of the chunk. Determines when to recalibrate, and when to cut recording
        silent_chunks: int: how many consecutive chunks are silent. Determines when to cut recording
        config: dict: the key is the setting name, the value is the setting value
    Returns:
        None

    >>> set_c_print_switch(True)
    >>> test_chunk = array("h")
    >>> test_chunk.extend([300, 100, 400, 100, 500, -200])
    >>> test_config = read_config()
    >>> console_indicator(test_chunk, dynamic_level=100, chunks_counter=42, silent_chunks=3, config=test_config)
    ############300. silent chunks: 3 of 10
    >>> console_indicator(test_chunk, dynamic_level=0, chunks_counter=42, silent_chunks=3, config=test_config)
    ################400. uncalibrated. Counter: 42 of 100. silent chunks: 3 of 10
    """
    vol = int(top3avg(data_chunk)) - dynamic_level

    if dynamic_level > 0:
        calibrated_str = ""
    else:
        calibrated_str = (
            ". uncalibrated. Counter: "
            + str(chunks_counter)
            + " of "
            + str(config["calibrate_num"])
        )
    silent_str = (
        ". silent chunks: " + str(silent_chunks) + " of " + str(config["silent_num"])
    )
    res = log_plot(vol) + str(vol) + calibrated_str + silent_str
    c_print(res)


def create_filename(dir_path, custom_datetime=None):
    """Returns the full path where the script should save the .wav . The filename contains a timestamp.

    Args:
        dir_path: str: the dir where the file should be saved
        custom_datetime: datetime obj: optional: if stated, this datetime will be used instead of the current one
    Returns:
         full_path: str: the full path to the future .wav

    >>> dt = datetime.datetime(year=2021, month=4, day=4, hour=12, minute=44, second=50)
    >>> res0 = create_filename("/some/dir/path/", custom_datetime=dt)
    >>> res0.startswith('/some/dir/path/20210404124450000')
    True
    >>> res0.endswith('mic.wav')
    True
    """
    filename = filename_timestamp(custom_datetime=custom_datetime) + "mic.wav"
    full_path = os.path.join(dir_path, filename)
    return full_path


def get_device_id_and_rate(config, pyaudio_obj, trusted_hardware7, prints7=True):
    """
    TODO: split this func into manageable chunks

    >>> set_c_print_switch(False)
    >>> config0 = read_config()
    >>> with sound_handler():
    ...     pyaudio_obj0 = pyaudio.PyAudio()
    ...     device_id, dev_rate, rep = get_device_id_and_rate(config0, pyaudio_obj0, trusted_hardware7=True)
    >>> isinstance(device_id, int)
    True
    >>> isinstance(dev_rate, int)
    True
    >>> dev_name = pyaudio_obj0.get_device_info_by_index(device_id).get("name")
    >>> config0["indicator_part"] = dev_name  # to emulate the situation there the indicator device is connected
    >>> with sound_handler():
    ...     pyaudio_obj0 = pyaudio.PyAudio()
    ...     device_id, dev_rate, rep = get_device_id_and_rate(config0, pyaudio_obj0, trusted_hardware7=True)
    >>> isinstance(device_id, int)
    True

    """
    report = dict()
    target_device_id = None
    device_rate = None

    devices_count = pyaudio_obj.get_device_count()

    all_names = []
    good_devices_names = []
    good_dev_indexes = []
    good_sample_rates = []
    report["devices_table"] = ""
    for i in range(0, devices_count):

        name = pyaudio_obj.get_device_info_by_index(i).get("name")
        all_names.append(name)
        print(f"Found an audio device: {name}")

        rate = pyaudio_obj.get_device_info_by_index(i).get("defaultSampleRate")

        if pyaudio_obj.get_device_info_by_index(i).get("maxInputChannels") > 0:
            comment = "good: "
            good_devices_names.append(name)
            good_dev_indexes.append(i)
            good_sample_rates.append(rate)

        else:
            comment = "      "
        report["devices_table"] += (
            comment
            + " Input Device id "
            + str(i)
            + " - "
            + name
            + " rate: "
            + str(rate)
        )

    indicator_connected7 = False
    for j in range(len(all_names)):
        if config["indicator_part"] in all_names[j]:
            indicator_connected7 = True
            break

    if trusted_hardware7:
        indicator_connected7 = True
        c_print(
            "Using the trusted hardware mode. Ignoring the absence of the indicator"
        )

    if indicator_connected7:
        for j in range(len(good_devices_names)):
            if config["sound_dev_part"] in good_devices_names[j]:
                target_device_id = good_dev_indexes[j]
                c_print(
                    "using this device:",
                    pyaudio_obj.get_device_info_by_index(target_device_id),
                )
                device_rate = int(good_sample_rates[j])
                break

    if prints7:
        c_print("target_device_id", target_device_id)
        c_print("indicator_connected7", indicator_connected7)
        c_print("get_device_count", devices_count)
        c_print("get_host_api_count", pyaudio_obj.get_host_api_count())

    return (
        target_device_id,
        device_rate,
        {"get_device_id_and_rate": report},
    )


def open_stream_from_scratch(config, trusted_hardware7):
    """
    >>> set_c_print_switch(False)
    >>> config0 = read_config()
    >>> stream0, pyaudio_obj0 = open_stream_from_scratch(config0, trusted_hardware7=True)
    >>> isinstance(stream0, pyaudio.Stream), isinstance(pyaudio_obj0, pyaudio.PyAudio)
    (True, True)
    >>> data_chunk0 = array("h", stream0.read(config0["chunk_size"], exception_on_overflow=False))
    >>> len(data_chunk0) > 0
    True
    >>> _ = close_stream_and_pyaudio_obj(stream0, pyaudio_obj0)
    """
    with sound_handler():
        pyaudio_obj = pyaudio.PyAudio()
        target_device_id, device_rate, _ = get_device_id_and_rate(
            config, pyaudio_obj, trusted_hardware7
        )

        c_print("target_device_id in open_stream_from_scratch", target_device_id)
        c_print("device_rate in open_stream_from_scratch", device_rate)

        stream = pyaudio_obj.open(
            format=config["sampling_format"],
            channels=config["channels"],
            rate=device_rate,
            input=True,
            output=True,
            frames_per_buffer=config["chunk_size"],
            input_device_index=target_device_id,
        )
    return stream, pyaudio_obj


def close_stream_and_pyaudio_obj(stream, pyaudio_obj):
    """
    >>> set_c_print_switch(False)
    >>> config0 = read_config()
    >>> stream0, pyaudio_obj0 = open_stream_from_scratch(config0, trusted_hardware7=True)
    >>> close_stream_and_pyaudio_obj(stream0, pyaudio_obj0)["close_stream_and_pyaudio_obj"]
    {'stream_stop_success7': True, 'stream_close_success7': True, 'pyaudio_obj_terminate_success7': True}
    >>> try:
    ...     data_chunk0 = array("h", stream0.read(config0["chunk_size"], exception_on_overflow=False))
    ... except Exception as closing_e:
    ...    err = closing_e
    >>> "Stream closed" in str(err)
    True
    """
    report = {
        "stream_stop_success7": False,
        "stream_close_success7": False,
        "pyaudio_obj_terminate_success7": False,
    }

    if hasattr(stream, "stop_stream"):
        stream.stop_stream()
        report["stream_stop_success7"] = True
    if hasattr(stream, "close"):
        stream.close()
        report["stream_close_success7"] = True
    if hasattr(pyaudio_obj, "terminate"):
        pyaudio_obj.terminate()
        report["pyaudio_obj_terminate_success7"] = True
    gc.collect()

    return {"close_stream_and_pyaudio_obj": report}


def get_data_chunk(stream, config, custom_byteorder=None):
    """
    >>> set_c_print_switch(False)
    >>> config0 = read_config()
    >>> stream0, pyaudio_obj0 = open_stream_from_scratch(config0, trusted_hardware7=True)
    >>> res0 = get_data_chunk(stream0, config0, custom_byteorder="big")
    >>> len(res0) > 0
    True
    >>> _ = close_stream_and_pyaudio_obj(stream0, pyaudio_obj0)["close_stream_and_pyaudio_obj"]

    """

    # little endian, signed short
    data_chunk = array(
        "h", stream.read(config["chunk_size"], exception_on_overflow=False)
    )

    byteorder_to_use = byteorder
    if isinstance(custom_byteorder, str):
        byteorder_to_use = custom_byteorder

    if byteorder_to_use == "big":
        data_chunk.byteswap()

    return data_chunk


def deterministic_random(iterations):
    """
    Returns a pseudo-random number x, such as 0 < x < 1.
    Returns the same output given the same input.
    e.g. deterministic_random(10000) = 0.78532038479...
    The pseudo-random sequence period is about two billion.
    It passes the Knuth spectral test for dimensions 2,3,4,5, and 6.

    Based on:
    A Pseudo-Random Number Generator for Spreadsheets. Research Note, Jan 2013
    Michael Lampton, Space Sciences Lab, UC Berkeley
    https://web.archive.org/web/20130409155747/https://www.ssl.berkeley.edu/~mlampton/RandomSpreadsheet4.pdf

    >>> res0 = deterministic_random(10000)
    >>> round(res0, 5)
    0.78532
    """

    int_run = 1  # must be an integer greater than zero. Changing it gives a different pseudo-random sequence
    m_const = 2147483647
    a_const = 16807

    # seed
    num = (
        round((int_run * math.exp(1) % 1) * m_const * a_const, 0) % m_const
    ) / m_const

    for j in range(iterations):
        num = (round(m_const * a_const * num, 0) % m_const) / m_const

    return num


def get_mock_chunks(
    list_len,
    chunk_len,
    bias=0.5,
    initial_silent_chunks_num=2,
    after_silent_multiplier=1,
    replace_these_with_silent_chunks=(),
):
    """Note: making bias lower makes it more likely to produce louder "sound"

    >>> get_mock_chunks(list_len=2, chunk_len=3)
    [array('h', [-154, 109, 195]), array('h', [-445, -335, -271])]
    >>> get_mock_chunks(list_len=2, chunk_len=3, bias=0.1)
    [array('h', [246, 509, 595]), array('h', [-45, 65, 129])]

    """
    counter = 0
    loud_count = 0
    combo_loud7 = False
    res = []
    for gmc in range(list_len):
        chunk = array("h")
        for cl in range(chunk_len):
            if gmc in replace_these_with_silent_chunks:
                ra = 0
            else:
                counter += 1
                ra = round((deterministic_random(counter) - bias) * 1000)

                if (ra > 0 and deterministic_random(counter * 2) > 0.9) or combo_loud7:
                    if gmc > initial_silent_chunks_num:
                        ra = 1000 + abs(ra) * 5  # add rare very loud sounds
                        loud_count += 1
                        if loud_count < 5:
                            combo_loud7 = True
                        else:
                            combo_loud7 = False
                            loud_count = 0

                if gmc > initial_silent_chunks_num:
                    ra *= after_silent_multiplier

            chunk.append(ra)
        res.append(chunk)

    return res


def get_mock_config(test_len):
    res = read_config()

    # to make it finish calibrating before max_cycles
    res["calibrate_num"] = round(test_len / 3)

    # to generate breathing data before max_cycles
    res["breath_min_data"] = round(test_len / 2)

    res["chunk_break_num"] = round(test_len / 1.5)
    res["min_relative_l"] = 5  # setting it low to make useful sounds appear more often
    res["consecutive_num"] = 2

    return res


def recording_cycle(
    config,
    trusted_hardware7=False,
    max_cycles=-1,
    saving_path="breathing.txt",
    mock_chunks=None,
):
    """
    TODO: sanitize data_chunk: it should contain only correct data (ints?)
    TODO: add tests where data_chunk is partially corrupted (e.g. contains non-floats and non-integers)

    >>> set_c_print_switch(False)
    >>> test_len = 15
    >>> config0 = get_mock_config(test_len)
    >>> pth = "mock_breathing.txt"
    >>> ch0 = get_mock_chunks(test_len*2, chunk_len=30, bias=0.5, initial_silent_chunks_num=config0["calibrate_num"])
    >>> dat, wid, rep = recording_cycle(config0, True, max_cycles=test_len, saving_path=pth, mock_chunks=ch0)
    >>> len(dat) > 0
    True
    >>> wid > 0
    True
    >>> ch1 = get_mock_chunks(list_len=test_len*2, chunk_len=30, bias=0.5, initial_silent_chunks_num=0)  # high bg level
    >>> dat, wid, rep = recording_cycle(config0, True, max_cycles=test_len, saving_path=pth, mock_chunks=ch1)
    >>> len(dat) > 0, wid > 0
    (True, True)
    >>> ch2 = get_mock_chunks(list_len=test_len*2, chunk_len=30, bias=0.5, initial_silent_chunks_num=0, after_silent_multiplier=5)  # results in a pathologically loud data
    >>> dat, wid, rep = recording_cycle(config0, trusted_hardware7=True, max_cycles=test_len, saving_path=pth, mock_chunks=ch2)
    >>> len(dat) > 0, wid > 0
    (True, True)
    >>> cn = config0["calibrate_num"]
    >>> config0["silent_num"] = 1
    >>> ch3 = get_mock_chunks(list_len=test_len*2, chunk_len=30, bias=0.0, initial_silent_chunks_num=config0["calibrate_num"], replace_these_with_silent_chunks=(9,10))
    >>> dat, wid, rep = recording_cycle(config0, trusted_hardware7=True, max_cycles=test_len, saving_path=pth, mock_chunks=ch3)
    >>> len(dat) > 0, wid > 0
    (True, True)

    """
    report = dict()
    chunks_counter = 0
    silent_chunks = 0
    consecutive_loud_num = 0

    audio_started = False
    end_circle7 = False

    data_all = array("h")
    chunks_for_bg = []

    global dyn_level
    global start_time
    if start_time is None:
        start_time = time.time()

    stream, pyaudio_obj = open_stream_from_scratch(
        config, trusted_hardware7=trusted_hardware7
    )

    cycles_counter = 0
    while True:
        data_chunk = get_data_chunk(stream, config)

        if isinstance(mock_chunks, list):
            del data_chunk
            data_chunk = mock_chunks[cycles_counter]

        if chunks_counter > 0 and chunks_counter % config["calibrate_num"] == 0:

            # TODO: ensure it will not crash if chunks_for_bg contains junk
            dyn_level = statistics.median(chunks_for_bg)
            c_print("new background noise level:", dyn_level)
            c_print(
                "new absolute threshold above the level:",
                get_absolute_threshold(dyn_level, config["min_relative_l"]),
            )
            chunks_for_bg = []

        else:
            chunks_for_bg.append(safe_array_max(data_chunk, default=0))

        chunks_counter += 1

        console_indicator(data_chunk, dyn_level, chunks_counter, silent_chunks, config)

        if audio_started:
            c_print("recording is ongoing")

        if chunks_counter > config["chunk_break_num"]:

            report["closing"] = close_stream_and_pyaudio_obj(stream, pyaudio_obj)
            c_print(report)

            if not audio_started:
                del data_all
                data_all = array("h")
                chunks_counter = 0
                gc.collect()

                stream, pyaudio_obj = open_stream_from_scratch(
                    config, trusted_hardware7=trusted_hardware7
                )

            else:
                c_print(
                    "stopping the recording because chunks_counter > MAX_CHUNKS_BEFORE_BREAK"
                )
                end_circle7 = True

        data_all.extend(data_chunk)

        useful_sound7 = False
        chunk_silent7 = chunk_is_silent(
            data_chunk, config["min_relative_l"], dynamic_level=dyn_level
        )
        if not chunk_silent7:
            consecutive_loud_num += 1
            c_print("consecutive_loud_num", consecutive_loud_num)
            if consecutive_loud_num > config["consecutive_num"]:
                useful_sound7 = True
                consecutive_loud_num = 0
        else:
            consecutive_loud_num = 0

        if audio_started:
            if chunk_silent7:
                silent_chunks += 1
                if silent_chunks > config["silent_num"]:
                    c_print(
                        "ending the circle  because silent, and silent_chunks > SILENT_CHUNKS"
                    )
                    end_circle7 = True  # this there the while cycle ends
            else:
                silent_chunks = 0
        elif useful_sound7 and dyn_level > 0:
            audio_started = True
            c_print("useful sound detected, starting recording")
            report["cycles_counter when recorded started"] = cycles_counter

        if max_cycles > 0:
            if cycles_counter > max_cycles:
                end_circle7 = True

        if end_circle7:
            loud_percentage = percentage_of_elements_higher_than_value(
                data_all, config["max_relative_l"]
            )

            c_print("loud_percentage:", round(loud_percentage))
            if loud_percentage < 20:
                good_data7 = True
            else:
                good_data7 = False

            if good_data7:

                sample_width = pyaudio_obj.get_sample_size(config["sampling_format"])

                report["closing"] = close_stream_and_pyaudio_obj(stream, pyaudio_obj)
                c_print(report)

                break
            else:
                # Happens when the data is bad (e.g.constant loud noise)
                # Discarding it.
                chunks_counter = 0
                audio_started = False
                end_circle7 = False
                del data_all
                data_all = array("h")
                c_print("Pathological data. Discarding it")
                gc.collect()

                stream, pyaudio_obj = open_stream_from_scratch(
                    config, trusted_hardware7=trusted_hardware7
                )

        cycles_counter += 1

    report["closing"] = close_stream_and_pyaudio_obj(stream, pyaudio_obj)
    c_print(report)

    gc.collect()

    return data_all, sample_width, {"recording_cycle": report}


def record_sound(
    config,
    trusted_hardware7=False,
    mock_chunks=None,
    mock_device_id=None,
    saving_path="breathing.txt",
    sleep_time_sec=10,
):
    """Record sound from the microphone and
    return the data as an array of signed shorts.

    >>> set_c_print_switch(False)
    >>> test_len = 15
    >>> config0 = get_mock_config(test_len)
    >>> pth = "mock_breathing.txt"
    >>> ch0 = get_mock_chunks(list_len=test_len*2, chunk_len=30, bias=0.5, initial_silent_chunks_num=config0["calibrate_num"])
    >>> sample_width0, data0 = record_sound(config0, trusted_hardware7=True, mock_chunks=ch0, saving_path=pth)
    >>> sample_width0
    2
    >>> len(data0)
    330
    >>> record_sound(config0, trusted_hardware7=True, mock_chunks=ch0, saving_path=pth, mock_device_id={"bad id"}, sleep_time_sec=1)
    (0, [])
    """

    with sound_handler():
        initial_pyaudio_obj = pyaudio.PyAudio()
        target_device_id, device_rate, _ = get_device_id_and_rate(
            config, initial_pyaudio_obj, trusted_hardware7
        )
        initial_pyaudio_obj.terminate()

    if mock_device_id is not None:
        target_device_id = mock_device_id

    if isinstance(target_device_id, int):

        c_print("device_rate", device_rate)

        data_all, sample_width, rep = recording_cycle(
            config,
            trusted_hardware7=trusted_hardware7,
            mock_chunks=mock_chunks,
            saving_path=saving_path,
        )
        c_print("len(data_all) as the output of recording_cycle", len(data_all))

        # we trim before normalize as threshold applies to un-normalized wave (as well as is_silent() function)
        data_all_trimmed = trim(data_all, config["trim_level"], config["trim_append"])
        data_all_normalized = data_all_trimmed
        c_print("finished recording")
        del data_all
    else:
        indicator_device_name_part = config["indicator_part"]
        use_this_device_name_part = config["sound_dev_part"]
        error_msg = f"The indicator device with a name part '{indicator_device_name_part}' is not found "
        error_msg += f"and/or the input device with a name part '{use_this_device_name_part}' is not found."
        error_msg += f"Sleeping for {sleep_time_sec} sec"
        c_print(error_msg)
        time.sleep(sleep_time_sec)  # in sec
        data_all_normalized = []
        sample_width = 0

    gc.collect()
    return sample_width, data_all_normalized


def record_to_file(
    config,
    dir_path,
    trusted_hardware7=False,
    discard_wav7=False,
    breathing_saving_path="breathing.txt",
    mock_chunks=None,
    custom_datetime=None,
):
    """Records from the microphone and outputs the resulting data to 'path'

    >>> set_c_print_switch(False)
    >>> test_len = 15
    >>> config0 = get_mock_config(test_len)
    >>> pth = "mock_breathing.txt"
    >>> dir_path0 = get_this_script_dir() + "/resources/mock_output_dir/"
    >>> ch0 = get_mock_chunks(list_len=test_len*2, chunk_len=30, bias=0.5, initial_silent_chunks_num=config0["calibrate_num"])
    >>> dt0 = datetime.datetime(year=2021, month=5, day=2, hour=11, minute=24, second=44)
    >>> res0 = record_to_file(config0, dir_path=dir_path0, trusted_hardware7=True, discard_wav7=False, breathing_saving_path=pth, mock_chunks=ch0, custom_datetime=dt0)
    >>> "logger_mic wrote the result" in str(res0)
    True
    >>> res0["record_to_file"]["data_len"]
    330
    >>> res1 = record_to_file(config0, dir_path=dir_path0, trusted_hardware7=True, discard_wav7=True, breathing_saving_path=pth, mock_chunks=ch0, custom_datetime=dt0)
    >>> "not saving" in str(res1)
    True


    """

    report = dict()

    sample_width, data = record_sound(
        config,
        trusted_hardware7=trusted_hardware7,
        saving_path=breathing_saving_path,
        mock_chunks=mock_chunks,
    )

    report["data_len"] = len(data)

    if len(data) > 0:

        if not discard_wav7:
            struct_format = "<" + ("h" * len(data))
            data_bytes = struct.Struct(struct_format).pack(*data)

            # TODO: move it to a separate func
            path = create_filename(dir_path=dir_path, custom_datetime=custom_datetime)
            wave_file = wave.open(path, "wb")
            wave_file.setnchannels(config["channels"])
            wave_file.setsampwidth(sample_width)
            wave_file.setframerate(config["frame_rate"])
            wave_file.writeframes(data_bytes)
            wave_file.close()

            write_msg = "logger_mic wrote the result to " + str(path)
            print_and_log(write_msg)
            report["main"] = write_msg

            del data_bytes
            del struct_format
            struct._clearcache()  # noqa . Is required to avoid memory leaks
        else:
            not_saving = "not saving the audio file because discard_wav7==True"
            c_print(not_saving)
            report["main"] = not_saving

        del data
        gc.collect()

    return {"record_to_file": report}


def parse_command_line_args():
    """
    >>> parse_command_line_args()
    Namespace(discard_wav7=False, trusted_hardware7=False)
    """
    parser = argparse.ArgumentParser(description="some descriptions")

    parser.add_argument(
        "-th",
        "--trusted_hardware",
        dest="trusted_hardware7",
        action="store_true",
        help="force it to work even if the desirable hardware is not detected",
    )

    parser.add_argument(
        "-nr",
        "--discard_wav",
        dest="discard_wav7",
        action="store_true",
        help="don't save the audio to files",
    )

    res = parser.parse_args()

    return res


def get_this_script_dir():
    # get location of this very file to put the log in the same folder
    res = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    return res


def run_everything(
    config,
    cycles_max=-1,
    breathing_saving_path="breathing.txt",
    custom_datetime=None,
    mock_chunks=None,
    mock_dir_path=None,
    mock_args=None,
):
    """By default, it runs forever. Set cycles_max to a positive int if you want to stop it at some point

    >>> set_c_print_switch(False)
    >>> test_len = 15
    >>> config0 = get_mock_config(test_len)
    >>> pth = "mock_breathing.txt"
    >>> dt0 = datetime.datetime(year=2021, month=5, day=2, hour=12, minute=52, second=19)
    >>> dir_path0 = get_this_script_dir() + "/resources/mock_output_dir/"
    >>> ch0 = get_mock_chunks(list_len=test_len*2, chunk_len=30, bias=0.5, initial_silent_chunks_num=config0["calibrate_num"])
    >>> args0 = parse_command_line_args()
    >>> args0.trusted_hardware7 = True
    >>> args0.discard_wav7 = False
    >>> res0 = run_everything(config0, cycles_max=2, mock_dir_path=dir_path0, breathing_saving_path=pth, mock_chunks=ch0, custom_datetime=dt0, mock_args=args0)
    >>> "logger_mic wrote the result" in str(res0)
    True
    """

    args = parse_command_line_args()
    if mock_args is not None:
        args = mock_args

    script_dir = get_this_script_dir()
    if isinstance(mock_dir_path, str):
        script_dir = mock_dir_path

    c_print("If you want to start a recording, say something; be silent to stop it")
    top_counter = cycles_max
    latest_report = "no report"
    while True:
        # TODO: add a command line arg: allow_crashing - to launch it without "try", for tests
        try:
            latest_report = record_to_file(
                config=config,
                dir_path=script_dir,
                trusted_hardware7=args.trusted_hardware7,
                discard_wav7=args.discard_wav7,
                breathing_saving_path=breathing_saving_path,
                mock_chunks=mock_chunks,
                custom_datetime=custom_datetime,
            )

        except Exception as recording_e:
            recording_msg = (
                "\n\nException in logger_mic: "
                + str(recording_e)
                + "\n\n"
                + "\nTraceback:\n"
                + str(traceback.print_exc())
            )
            print_and_log(recording_msg)
            time.sleep(10)  # Delay in seconds.

        if cycles_max > 0:
            top_counter -= 1
            if top_counter < 0:
                break

    return latest_report


if __name__ == "__main__":
    run_everything(config=config_dic)

"""
Inspired by this code by OliverLengwinat:
https://github.com/OliverLengwinat/raspi_recorder
... which was based on these pieces of code:
https://stackoverflow.com/a/16385946/11736660
https://stackoverflow.com/a/17673011/11736660

"""
