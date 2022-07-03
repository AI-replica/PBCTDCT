PBCTDCT: Personal Behavioral Cloning Training Data Collection Tool

# 0. Summary 

The purpose of PBCTDCT is to collect training data for behavioral cloning, 
a machine learning approach that utilizes expert demonstrations to train AIs.

For an intro into behavioural cloning, see, for example, [this article](https://ml.berkeley.edu/blog/posts/bc/). 

PBCTDCT can capture:
- screenshots at regular intervals
- mouse movements
- keystrokes
- sound input / output

It can also automatically archive previously collected data. 

Currently, it only works in Ubuntu, and will fail to work in MacOS or Windows.

# 1. Install

`cd` to the dir where this readme is located on your machine. For example, like this:

`cd /SOME_PATH/PBCTDCT` 

Create and activate a virtual environment (note: don't change its name; it must be "loggers_env"):

`virtualenv -p python3 loggers_env`

`source 'loggers_env/bin/activate'` 

## 1.0. Install general requirements

`sudo apt install libcairo2-dev libgirepository1.0-dev`

`pip3 install -r requirements.txt`

## 1.1. Install logger_headphone requirements

`sudo apt-get install pulseaudio-utils lame mpg123`

## 1.2. Install logger_mic requirements

In many cases, it should work from the box, after you've installed the general requirements.
But if it doesn't, this could help:

`sudo apt-get update && sudo apt-get upgrade`

`sudo apt-get install libasound-dev portaudio19-dev libportaudio2 libportaudiocpp0`
 
`sudo apt-get install libatlas-base-dev`

## 1.3. Build the zpaq archiver

Download ZPAQ source code from here: http://mattmahoney.net/dc/zpaq715.zip

Unpuck the zip and navigate to the dir with the contents. 

delete .o files from it (if exist)

`cd` to the dir. 

Make the exec:

`make`

A file named "zpaq" will apper inside the folder.

Rename it to "zpaq715" and place it in the dir where this readme is located.

# 2. Launch

`python3 launcher.py`

if the launch is successful, you should see:

- *five* `logger_` processes in the gnome-system-monitor, one process for each logger
- the screenshots and other data will start to apper in the dir where this readme is located on your machine

The loggers work independently of each other. 
Thus, if some of them are down (e.g. due to broken dependencies), others will continue to work.

After each relaunch, the script will try to archive the previously collected data, and do it as follows:

1. it creates zips
2. it creates zpaqs (the much more compact archives than zips)
3. it checks if zpaqs are valid
4. if they are valid, the script deleted zips, to keep only zpaqs.

This way, if zpaqs somehow fail, the data will still be archived in zips.

Depending on your machine's compute, the archival could take a hour or longer. 

The logging will not start until the previous training data is archived 
(we are working on fixing this limitation). 