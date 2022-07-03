import datetime
import random
import os

""" Provides utils for the loggers."""

cprint_verbose7 = True  # if true, the cprint func will print to sdout


def set_cprint_switch(ibool):
    global cprint_verbose7
    cprint_verbose7 = ibool


def cprint(*args):
    if cprint_verbose7:
        print(args)


def human_timestamp():
    now = datetime.datetime.now()
    time_st = now.strftime("%Y%m%d%H%M%S%f")[:-3]

    # to avoid rewriting the log if made at the same millisecond:
    time_st += str(random.randint(0, 9))
    return time_st


def get_full_path(filename, fake_parent_location=None):
    """Returns the full path of a file assuming that it's located in the
    same dir as this script.
    If the input is already a full path (with or without "~/"), it will return
    the input.
    """
    if isinstance(filename, str):
        if filename.strip()[0:2] == "~/":
            full_path = filename
        else:
            if fake_parent_location is None:
                parent_location = os.path.realpath(
                    os.path.join(os.getcwd(), os.path.dirname(__file__))
                )
            else:
                parent_location = fake_parent_location
            full_path = os.path.join(parent_location, filename)
    else:
        full_path = None
        cprint("Error: this filename is not a string:", str(filename))
    return full_path


def is_file7(fpath):
    """Returns True if there is a file on the given path, False otherwise.

    The relative path is converted to the absolute path.
    """

    if isinstance(fpath, str):
        res = os.path.isfile(get_full_path(fpath))
    else:
        res = False
    return res


def print_and_log(my_text1, my_text2=""):
    # TODO: create a separate func about writing down files, with exceptions etc
    cprint(my_text1, my_text2)

    with open("mylog.txt", "a") as fff:
        fff.write(
            human_timestamp() + " - " + str(my_text1) + " " + str(my_text2) + "\n"
        )
    fff.close()
