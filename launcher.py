""" Prepares the virtual environment for loggers, installs dependencies, and launches the loggers.
Also launches the archiving of the yesterday's logs.

The idea is to add this script to the list of startup applications, so
it automatically do the logging and archiving.

Each logger is launched as a separate process.

Archivation is done in 2 stages: zip and zpaq.
zpaq provides extreme reduction of size, at the cost of a lot of compute.
If zpaq is successful, the fallback zip archive is deleted. Otherwise, the zip is preserved.

A compiled zpaq715 must be located in the same dir as this script. You can compile it from
 the official zpaq source code located on this site: http://mattmahoney.net/dc/zpaq.html

------------------------------------------------------------
Troubleshooting common problems:

if some loggers stopped working after installing conda, do this:
conda init --reverse

check if the scripts are actually running in some kind of default virtual environment like .pyenv
    is visible in paths in gnome-system-monitor

if zpaqs are not created, try remake the zpaq exec.

"""


import os
import subprocess
import time

from utils import human_timestamp, get_full_path, print_and_log, is_file7

# the script will try to create an venv environment with this name:
env_name = "loggers_env"

# TODO: move it the config
launch_delay_sec = 1  # set it to at least 300, to allow the OS to load peacefully

env_path = get_full_path(env_name)
python3_path = os.path.join(env_path, "/bin/python3")
pip3_path = os.path.join(env_path, "/bin/pip3")


class Logger:
    def __init__(self, script_file, py_version, archive_prefix, output_filetype):
        self.script_file = script_file  # e.g. 'logger_keyboard.py'
        self.py_version = py_version  # e.g. 'python3.6'
        self.archive_prefix = archive_prefix  # e.g. "brainOutput"
        self.output_filetype = output_filetype  # e.g. "txt" (without a point!)


def configure_loggers():
    logger_keyboard = Logger(
        script_file="logger_keyboard.py",
        py_version="python3",
        archive_prefix="brainKeysOutput",  # note that the autodelete script requires "...put" ending
        output_filetype="keystxt",  # to identify what files to archive
    )

    logger_mouse = Logger(
        script_file="logger_mouse.py",
        py_version="python3",
        archive_prefix="brainMouseOutput",
        output_filetype="mousetxt",
    )

    logger_screen = Logger(
        script_file="logger_screen.py",
        py_version="python3",
        archive_prefix="brainScreenInput",
        output_filetype="jpeg",
    )

    logger_headphone = Logger(
        script_file="logger_headphone.py",
        py_version="python3",
        archive_prefix="brainSoundInput",
        output_filetype="mp3",
    )

    logger_mic = Logger(
        script_file="logger_mic.py",
        py_version="python3",
        archive_prefix="brainMicOtput",
        output_filetype="wav",
    )

    return [logger_keyboard, logger_mouse, logger_screen, logger_headphone, logger_mic]


def create_env_if_not_exist():
    """Creates a venv virtual environment to run the loggers in it"""
    if not os.path.exists(env_path):
        subprocess.call(["python3", "-m", "venv", env_path])
        print_and_log("created" + str(env_path))
        existed7 = False
    else:
        print_and_log(str(env_path) + " already exist")
        existed7 = True
    return existed7


def install_piped_requirements():
    requirements_path = get_full_path("requirements.txt")
    subprocess.call([pip3_path, "install", "-r", requirements_path])
    print_and_log("installed dependencies according to requirements.txt")


def run_in_env(script_filename):
    subprocess.Popen([python3_path, script_filename])
    print_and_log("launched the script " + str(script_filename))


def launch_zpaq_stuff(loggers, workingFolder):
    """Launches zpaq processes, to archive the yesterday's logs.

    Done sequentially, not in parallel, as each zpaq process consumes a lot of compute"""
    print_and_log("---------------launching zpaq stuff---------------")

    if is_file7("zpaq715"):
        path2zpaq = os.path.join(workingFolder, "zpaq715")

        for lgr in loggers:
            command = [
                path2zpaq,
                "add",
                lgr.archive_prefix + human_timestamp()[:-4] + ".zpaq",
                "./",
                "-m5",
                "-only",
                "*." + lgr.output_filetype,
            ]

            print_and_log("### ZPAQ command used: ", subprocess.list2cmdline(command))

            try:
                subprocess.call(command, cwd=workingFolder)
            except Exception as e:
                print_and_log("Failed to launch zpaq: ", str(e))

        print_and_log("---------------zpaq stuff finished---------------")
    else:
        print_and_log(
            "zpaq715 not found. Check if you have it in the same dir as this srcipt"
        )


def launch_zipping(loggers, workingFolder):
    """
    Explanation of the zip command arguments:
    -@ file lists.   If  a file list is specified as -@ , zip
       takes the list of input files from standard input instead of  from  the
       command line.
    -m deletes the target directories/files after making the  specified zip  archive
    """
    print_and_log("---------------launching zipping---------------")

    # the resulting command looks similar to this command:
    # command='find . | egrep "\.(txt)$" | zip -@ -m brainOutput$(date +%Y%m%d%H%M%S).zip'
    for lgr in loggers:
        command = (
            'find . | egrep "\.('
            + lgr.output_filetype
            + ')$" | zip -@ -m '
            + lgr.archive_prefix
            + "$(date +%Y%m%d%H%M%S).zip"
        )
        try:
            subprocess.call(command, cwd=workingFolder, shell=True)
        except Exception as e:
            print_and_log("failed to launch zipping:", str(e))

    print_and_log("---------------zipping finished---------------")


def launch_autodelete():
    print_and_log("---------------launching autoDelete in parallel---------------")
    try:
        # popen because it disowns automatically
        subprocess.Popen(["python3", get_full_path("zips_deleter.py")])
    except:
        print_and_log("ERROR IN LAUNCHING autoDelete")


def launch_loggers(loggers):
    print_and_log("---------------launching loggers in parallel---------------")

    for lgr in loggers:
        try:
            # subprocess.Popen([lgr.py_version, get_full_path(lgr.script_file)])
            run_in_env(get_full_path(lgr.script_file))
            print_and_log("launched " + str(lgr.script_file))
        except Exception as e:
            print_and_log("failed to launch " + str(lgr.script_file), str(e))
    print_and_log("---------------loggers launched. Exiting---------------")
    print_and_log(" ")
    print_and_log(" ")


def preserve_source_code(workingFolder):
    """
    Preserves:
        - all the .py files in the dir
        - the zpaq715 file
        - the source_code/ dir and its contents
        - requirements.txt
    """
    command = (
        "zip -r source_code"
        + human_timestamp()
        + ".zip zpaq715 *.py *.ini requirements.txt source_code/"
    )
    try:
        subprocess.call(command, cwd=workingFolder, shell=True)
    except Exception as e:
        print_and_log("failed to launch source code preservation:", str(e))


def create_dummy_files(working_folder):
    """
    Some loggers (e.g. logger_mic) don't create any files in some conditions.
    Because of it, their archives are not created.
    Because of it, zips for all loggers - are not deleted.
    A solution is to always create some empty file for logger_mic.
    """
    filename = "dummy.wav"
    full_path = os.path.join(working_folder, filename)
    with open(full_path, "w") as dummy_f:
        text = "It'a dummy. See create_dummy_files func in launcher.py for details"
        dummy_f.write(text)
    dummy_f.close()


def start_logging():
    print("Waiting for the planned delay")
    time.sleep(launch_delay_sec)  # Delay in seconds
    print("Delay ended. Proceesing")

    working_dir = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

    print_and_log("workingFolder: ", working_dir)

    already_existed7 = create_env_if_not_exist()
    install_piped_requirements()

    loggers_list = configure_loggers()

    create_dummy_files(working_dir)

    launch_zpaq_stuff(loggers_list, working_dir)
    launch_zipping(loggers_list, working_dir)
    launch_autodelete()
    launch_loggers(loggers_list)
    preserve_source_code(working_dir)


if __name__ == "__main__":
    start_logging()
