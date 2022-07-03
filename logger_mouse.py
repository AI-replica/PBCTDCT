import sys
import os
import time
from ctypes import *  # TODO: import only the necessary parts. Find by commenting this out

from utils import human_timestamp

"""Records mouse movements as the coordinates of the cursor, with timestamps. 
"""

time_between_saves = 18.0  # how oft should it be saved in file, in seconds
time_between_fetches = 0.01  # how of should the coordinates be fetched, in seconds


# linux only!
assert "linux" in sys.platform


def fetch_xy():
    if display == 0:
        sys.exit(2)
    w = Xlib.XRootWindow(display, c_int(0))
    (root_id, child_id) = (c_uint32(), c_uint32())
    (root_x, root_y, win_x, win_y) = (c_int(), c_int(), c_int(), c_int())
    mask = c_uint()
    ret = Xlib.XQueryPointer(
        display,
        c_uint32(w),
        byref(root_id),
        byref(child_id),
        byref(root_x),
        byref(root_y),
        byref(win_x),
        byref(win_y),
        byref(mask),
    )
    if ret == 0:
        sys.exit(1)
    return root_x, root_y


def log(done, callback):
    while not done():
        time.sleep(time_between_fetches)
        my_x, my_y = fetch_xy()
        callback(time.time(), my_x, my_y)


# get location of this very file to put the log in the same folder
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


def get_full_path_mouse():
    file_name = human_timestamp() + ".mousetxt"
    full_path = os.path.join(__location__, file_name)
    return full_path


# writing the log into array
def record_moves(t, x, y):
    temp = "%.6f   %r   %r" % (t, x, y)
    temp += "\n"
    temp = temp.replace("c_int(", "")
    temp = temp.replace(")", "")
    logArray.append(temp)


while True:
    try:
        logArray = []
        now = time.time()
        done = lambda: time.time() > now + time_between_saves

        # this two strings should be here to avoid "too many clients" error:
        Xlib = CDLL("libX11.so.6")
        display = Xlib.XOpenDisplay(None)

        log(done, record_moves)

        with open(get_full_path_mouse(), "w") as myFile:
            for s in logArray:
                myFile.write(s)
            myFile.flush()
        myFile.close()
        Xlib.XCloseDisplay(display)
        print("Saved a logger_mouse file with this many entries:", len(logArray))

    except Exception as e:
        print("logger_mouse caused an exception:", str(e))

# This code is inspired by this code:
# https://stackoverflow.com/questions/35137007/get-mouse-position-on-linux-pure-python
