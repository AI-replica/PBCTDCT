import os
import datetime
import subprocess
from utils import print_and_log, human_timestamp

"""Checks if zpaq archives are valid. If valid, it deletes the corresponding zips to save drive space

This script does the following checks before deleting the zips:

- the file must end with .zip
- it's name must contain a pattern like put20181112 (but the current date instead)
- the pattern should indicate not only the today's date, but also current or past HOUR
- finds no more than N files (to avoding deleting anything unnecessary). The latest ones!
- delete only if zpaqs are OK:
---- at least N were created this or past hour
---- all of them have non-zero sizes
---- the internal zpaq check has good outputs


LIMITATIONS:
will not find zips if they were created yeasterday. 
E.g. the scrypt was launched at 23:59, and the zips were created "yesterday" because of it. 
The worst thing that will be because of it: zips are not deleted, which is ok

"""

# TODO: get it from loggers config
num_loggers = 5

# TODO: move it to configs
# to prevent the following situation:
# some loggers doesnt work, and thus there are less than num_loggers archives to delete,
# and thus this script will make a mistake and delete previous archives
archive_prefixes = {
    "brainKeysOutput",
    "brainMouseOutput",
    "brainMicOtput",
    "brainSoundInput",
    "brainScreenInput",
}


# get the location of this very file
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

path_to_zpaq_exec = os.path.join(__location__, "zpaq715")
folder_where_to_delete_stuff = __location__
path4_fake_extract = "/temp"


def delete_given_file(death_row_file):
    if os.path.isfile(death_row_file):
        print_and_log("deleting this file:", death_row_file)
        os.remove(death_row_file)
        print_and_log("deleted")
    else:
        print_and_log(
            "SOMETHING WENT TERRIBLY WRONG. TRIED TO DELETE A NONEXISTENT FILE"
        )


def get_file_size_in_bytes(full_path):
    stat_info = os.stat(full_path)
    return stat_info.st_size  # Output is in bytes


def join_paths(file_name):
    return os.path.join(folder_where_to_delete_stuff, file_name)


def remove_letters(s):
    new = ""
    for letter in s:
        if not (letter.isalpha()):
            new += letter
    return new


def get_the_previous_hour(current_hour_string):  # input is a string
    current_hour = int(current_hour_string)
    if current_hour > 0:
        past_h = str(current_hour - 1)  # output is a string
    else:  # if it 0, then the previous hour was 23
        past_h = str(23)

    if len(past_h) < 2:  # the output should have 2 digital places
        past_h = "0" + past_h
    return past_h


def execute_deletion():
    # TODO: split the code into funcs
    print_and_log("######################### Starting #########################")

    there_are_n_or_more_recent_zpaqs = False
    there_are_n_or_more_recent_zpaqs_checked = False
    the_recent_zpaqs_have_nonzero_sizes = False
    the_recent_zpaqs_have_nonzero_sizes_checked = False
    zpaq_test_outputs_good = False
    zpaq_test_outputs_good_checked = False

    current_hour = datetime.datetime.now()
    current_hour = current_hour.strftime("%H")
    pattern = human_timestamp()
    pattern = "put" + pattern[:-10]  # sample result: put20181112
    current_hour_pattern = pattern + current_hour
    past_hour_pattern = pattern + get_the_previous_hour(current_hour)

    print_and_log("patterns for zpaq search:")
    print_and_log("currentHourPattern: ", current_hour_pattern)
    print_and_log("pastHourPattern:    ", past_hour_pattern)

    # find zpaqs for the checks
    found_zpaqs = []

    alist_filter = [".zpaq"]
    path = folder_where_to_delete_stuff
    for r, d, f in os.walk(path):
        for filename in f:
            if filename[-5:] in alist_filter and current_hour_pattern in filename:
                found_zpaqs.append(filename)
    for r, d, f in os.walk(path):
        for filename in f:
            if filename[-5:] in alist_filter and past_hour_pattern in filename:
                found_zpaqs.append(filename)

    print_and_log("--------------------------------")
    print_and_log("foundZpaqs:")
    for element in found_zpaqs:
        print_and_log(element)
    print_and_log("--------------------------------")

    # check if there N+ resent zpaqs found
    if len(found_zpaqs) >= num_loggers:
        there_are_n_or_more_recent_zpaqs = True
    else:
        print_and_log(
            "there_are_n_or_more_recent_zpaqs", str(there_are_n_or_more_recent_zpaqs)
        )
    there_are_n_or_more_recent_zpaqs_checked = True

    # check if they have non-zero sizes

    if there_are_n_or_more_recent_zpaqs:
        counting_zero_sized_files = 0
        for element in found_zpaqs:
            zp_full_path = join_paths(element)
            if get_file_size_in_bytes(zp_full_path) < 100:
                counting_zero_sized_files += 1

        if counting_zero_sized_files == 0:
            the_recent_zpaqs_have_nonzero_sizes = True
        else:
            print_and_log(
                "the_recent_zpaqs_have_nonzero_sizes",
                the_recent_zpaqs_have_nonzero_sizes,
            )
        the_recent_zpaqs_have_nonzero_sizes_checked = True

    print_and_log("trying to extract zpacs")

    if there_are_n_or_more_recent_zpaqs:
        counting_none_ok_extracts = 0
        for element in found_zpaqs:
            path_to_this_zpaq = join_paths(element)
            print_and_log("    launching the extract command")
            zpaq_output = subprocess.call(
                [
                    path_to_zpaq_exec,
                    "extract",
                    path_to_this_zpaq,
                    "-to",
                    path4_fake_extract,
                    "-test",
                ]
            )
            print_and_log("    the extract command finished")
            # zpaq returns 0 if successful, 1 in case of warnings, or 2 in case of an error.
            if zpaq_output != 0:
                counting_none_ok_extracts = +1

        if counting_none_ok_extracts == 0:
            zpaq_test_outputs_good = True
        else:
            print_and_log("zpaqTestOutputsGood", zpaq_test_outputs_good)
        zpaq_test_outputs_good_checked = True

    print_and_log("extracting zpacs finished")

    if (
        there_are_n_or_more_recent_zpaqs
        & the_recent_zpaqs_have_nonzero_sizes
        & zpaq_test_outputs_good
    ):

        # searching for zips

        found_files = []

        alist_filter = [".zip"]
        path = folder_where_to_delete_stuff
        for r, d, f in os.walk(path):
            for filename in f:
                if filename[-4:] in alist_filter and current_hour_pattern in filename:
                    if (
                        not "source" in filename
                    ):  # don't count the zip with the source code
                        found_files.append(filename)

        for r, d, f in os.walk(path):
            for filename in f:
                if filename[-4:] in alist_filter and past_hour_pattern in filename:
                    if (
                        not "source" in filename
                    ):  # don't count the zip with the source code
                        found_files.append(filename)

        # timestamps from the filenames of the found files
        timestamps_of_found_files = []
        for element in found_files:
            tempst = remove_letters(element)
            tempst = tempst[:-1]
            timestamps_of_found_files.append(tempst)

        timestamps_of_found_files.sort(reverse=True)

        found_files_latest_n = []

        i = 0
        while (i < num_loggers) & (i < len(timestamps_of_found_files)):
            time_str = timestamps_of_found_files[i]
            for j in range(len(found_files)):
                file_str = found_files[j]
                if time_str in file_str:
                    found_files_latest_n.append(file_str)
            i += 1

        found_files_latest_n = list(set(found_files_latest_n))

        print(found_files_latest_n)

        # to prevent the following situation:
        # some loggers doesnt work, and thus there are less than N archives to delete,
        # and thus this script (without this fix) will make a mistake and delete previous archives
        files_by_prefix = dict()
        for prefix in archive_prefixes:
            templist = []
            for found_file in found_files_latest_n:
                if prefix in found_file:
                    templist.append(found_file)
            if len(templist) > 0:
                templist.sort(reverse=True)
                files_by_prefix[prefix] = templist[0]
        print(files_by_prefix)
        found_files_latest_n = list(files_by_prefix.values())
        print(found_files_latest_n)

        # TODO: printANDlog if there is something like this in files_by_prefix:
        # 'brainSoundInput': [], 'brainScreenInput': []
        # it means, some loggers werent working

        print_and_log("-----------------------------")
        print_and_log("foundFilesLatestN zips:")
        for element in found_files_latest_n:
            print_and_log(element)

        if len(found_files_latest_n) < num_loggers:
            print_and_log(
                "THERE ARE ALREADY less than N zips. Some loggers werent working in the previous session?"
            )
        else:
            # deleting zips
            print_and_log("-----------------------------")
            print_and_log("Everything seems to be ok. Commencing deletion of zips")

        for doomed_file in found_files_latest_n:
            death_full_path = os.path.join(folder_where_to_delete_stuff, doomed_file)
            delete_given_file(death_full_path)
        print_and_log("deletion complete")

    else:
        print_and_log("not deleting anything bacause some checks were failed:")
        print_and_log(
            "thereAreNOrMoreRecentZpaqs: "
            + str(there_are_n_or_more_recent_zpaqs)
            + ". Checked? "
            + str(there_are_n_or_more_recent_zpaqs_checked)
        )
        print_and_log(
            "theRecentZpaqsHaveNonzeroSizes: "
            + str(the_recent_zpaqs_have_nonzero_sizes)
            + ". Checked?"
            + str(the_recent_zpaqs_have_nonzero_sizes_checked)
        )
        print_and_log(
            "zpaqTestOutputsGood: "
            + str(zpaq_test_outputs_good)
            + ". Checked?"
            + str(zpaq_test_outputs_good_checked)
        )

    print_and_log("####### Exiting #######")
    print_and_log(" ")
    print_and_log(" ")


if __name__ == "__main__":
    execute_deletion()
