import sys
import os
import time

from gi.repository import Gdk, GdkPixbuf

from utils import human_timestamp

"""
Makes screenshots on regular intervals, and saves them. 

The frequency of saving depends on what happens on the screen:
if there are a lot of changes (e.g. video is playing), the frequency is higher. 
"""


test_screen_divides = 64  # the more, the better is the estimate of the difference between frames. But it costs resources. 16 is enough for most applications.

jpeg_quality_normal = 7  # from 0 to 100, 100 means the highest quality. 7 is the smallest for readable text
jpeg_quality_in_low_speed = 3
jpeg_quality_in_high_speed = 14

scale_factor_normal = 1  # 1 means no scaling. 2 - scaling down by a factor of 2 etc
scale_factor_in_low_speed = 2
scale_factor_in_high_speed = 1

time_between_saves = 6.0  # how often should it be saved in file, in seconds. Always use the point (2.0 instead of 2 etc)

dymanic_timing = True
how_much_faster_in_high_speed = 8.0  # how much faster it will be on the high speed
how_much_slower_in_low_speed = 8.0  # how much slower it will be on the slow speed
high_speed_trashhold = 4.0  # the lower - the ofter, the high speed mode will be engaged. Sensitive to timeBetweenSaves
low_speed_trashhold = 0.05  # the higher - the ofter the slow speed mode will be engaged. Sensitive to timeBetweenSaves

# if dymanicTiming is true, the time between saves will change dynamically:
# if a lot of stuff is happening on the screen, the frequency
# will be temporarly increased 8x
# initally, the timeBetweenSaves is the default:
dynamic_time_between_saves = time_between_saves
current_speed_mode = "normal"
jpeg_quality = jpeg_quality_normal
scale_factor = 1
previous_differ_speed = 66.6


# linux only!
assert "linux" in sys.platform


def image_difference(img1, img2):
    # the idea is to detect if two images are significiantly different
    # we do it by extremelly scaling down the images (for speed), and comparing the bytes
    # it could be done more elegantly with numPy, but external libs must be avoided

    img1_scaled = img1.scale_simple(
        test_screen_divides, test_screen_divides, GdkPixbuf.InterpType.NEAREST
    )
    img1_bytes = img1_scaled.get_pixels()
    img1_bytes_arr = list(img1_bytes)

    img2_scaled = img2.scale_simple(
        test_screen_divides, test_screen_divides, GdkPixbuf.InterpType.NEAREST
    )
    img2_bytes = img2_scaled.get_pixels()
    img2_bytes_arr = list(img2_bytes)

    diff_count = 0
    for j in range(len(img1_bytes_arr)):
        if img1_bytes_arr[j] != img2_bytes_arr[j]:
            diff_count += 1

    percent_changed = 100 * diff_count / len(img1_bytes_arr)

    return percent_changed


def fetch_screen():
    w = Gdk.get_default_root_window()
    sz = w.get_geometry()[2:4]
    pb = Gdk.pixbuf_get_from_window(w, 0, 0, sz[0], sz[1])

    if scale_factor != 1:
        pb = pb.scale_simple(
            int(sz[0] / scale_factor),
            int(sz[1] / scale_factor),
            GdkPixbuf.InterpType.HYPER,
        )

    if pb is not None:
        return pb
    else:
        print("ERROR: unable to get the screenshot.")
        raise ValueError("ERROR: unable to get the screenshot.")


def log(done, callback):
    while not done():
        time.sleep(dynamic_time_between_saves)
        myscreen = fetch_screen()
        callback(myscreen)


imgStack = []

# get location of this very file to put the log in the same folder
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


def get_full_path_screen():
    file_name = human_timestamp() + "screen.jpeg"
    full_path = os.path.join(__location__, file_name)
    return full_path


# save the screen into a file
def save_screen(img):
    img.savev(get_full_path_screen(), "jpeg", ["quality"], [str(jpeg_quality)])

    # storing the last 4 screens. Needed for dynamic time between saves:
    imgStack.append(img)
    if len(imgStack) > 4:
        del imgStack[0]


def main_circle_stuff():
    global dynamic_time_between_saves
    global previous_differ_speed
    global current_speed_mode
    global jpeg_quality
    global scale_factor
    global previous_differ_speed

    if dymanic_timing:
        if len(imgStack) > 3:
            differ1 = image_difference(imgStack[0], imgStack[1])
            differ2 = image_difference(imgStack[2], imgStack[3])
            differ = (differ1 + differ2) / 2
            differ_speed = differ / dynamic_time_between_saves
            str2out = "%.2f" % differ_speed
            if differ_speed > high_speed_trashhold:
                dynamic_time_between_saves = (
                    time_between_saves / how_much_faster_in_high_speed
                )
                current_speed_mode = "HIGH SPEED"
                jpeg_quality = jpeg_quality_in_high_speed
                scale_factor = scale_factor_in_high_speed
            else:
                # % only change to slow if it's not high. Because if no big screen chages for a little time,
                # it will fall to slow, but should fall to normal. differ_speed+PreviousDifferSpeed to reduce
                # oscillations between normal and slow
                if ((differ_speed + previous_differ_speed) < low_speed_trashhold) and (
                    current_speed_mode != "HIGH SPEED"
                ):
                    dynamic_time_between_saves = (
                        time_between_saves * how_much_slower_in_low_speed
                    )
                    current_speed_mode = "Sloow... speeed..."
                    jpeg_quality = jpeg_quality_in_low_speed
                    scale_factor = scale_factor_in_low_speed
                else:
                    dynamic_time_between_saves = time_between_saves
                    current_speed_mode = "normal speed"
                    jpeg_quality = jpeg_quality_normal
                    scale_factor = scale_factor_normal
            previous_differ_speed = differ_speed
            print(
                "differ_speed is "
                + str2out
                + " percent per second. "
                + current_speed_mode
            )
    else:
        dynamic_time_between_saves = time_between_saves
        current_speed_mode = "normal speed"

    now = time.time()
    done = lambda: time.time() > now + dynamic_time_between_saves
    log(done, save_screen)


while True:
    try:
        main_circle_stuff()
    except Exception as e:
        print("logger_screen caused an exception:", str(e))


# The code was inspired by this code::
# https://stackoverflow.com/questions/69645/take-a-screenshot-via-a-python-script-linux
# a manual (outdated) for the save function:
# https://developer.gnome.org/gdk-pixbuf/stable/gdk-pixbuf-File-saving.html#gdk-pixbuf-save
