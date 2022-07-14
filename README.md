# PyLS3

A little Python script to connect to the Linegrip LineScale3 via Bluetooth or USB Serial connection and capture the log data.

## Description
PyLs3 can connect to several LS3 at the same time.   
On Startup PyLs3  could set the desired mode, unit, speed on the LS3 (using the 'InitialCommands').  
After connecting PyLs3 automatically starts capture the logging data, when the load is higher than the 'StartTrigger'.  
The capture is stopped after the 'MaxCaptureTime_s' or 'MinCaptureTime_s' when the load is below the 'StopTrigger'.  
When the capture is stopped the captured logging data is saved to a csv-file.
When 'Capture: AutoGeneratePlot' is activated, a plot is automatically generated and saved as png image.

The OnboardLogging could also be downloaded via USB Serial connection (using 'InitialCommands SaveOnboardLogging').  
If 'OnboardLogging: AutoGeneratePlot' is activated, a plot is automatically generated and saved as png image.

The configuration is stored in PyLS3_AppCfg.yml, PyLS3_UserCfg.yml and could be passed via cli.
PyLS3_AppCfg.yml are overwritten by PyLS3_UserCfg.yml and both are overwritten by cli values.

PyLS3_onboardlogging.py is based on Rocco's code, thanks.  
PyLS3_onboardlogging.py recursively searches all LS3 Onboardlogging csv files in a given directory (and optional all sub directories).  
(Optional) plots for all file are automatically generated and saved as png image.  
When continues logging data has been recoreded, matching measurements could automatically be merged (-c option).
 (When continues logging is used, precapture on the LS3 should be activated, the overlapping data is automaticlly factored out).

## Supported LS3 Firmware Versions
current-Branch: 2.411, 2.520, 2.530, 2.600  

## Installation

PyLS3 is a python script. So python and all required packages need to be installed.  
To install the all required packages run:  
`pip install -r requirements.txt`

Currently, tested with Windows 10 and Linux, Python 3.7.9 and Python 3.8 (may work with other versions)

## Infos

### Serial 'UART Baud'
The configured Serial Baud in PyLS3 must match the 'UART Baud' on LS3.  
The following rates are available: 9600, 38400, 230400, 460800  
For 1280Hz measurements via USB-Serial the Serial-Baud-Rate should be set to 460800, else data is lost.
The Serial-Baud-Rate could be configured per device in the PyLS3_UserCfg.yml (if it is not configured 230400 is used).  
The USB cable must be connected to LS3 slave port.

```
Device:
    LS3_1:
        USB_Speed: 460800   # 9600 38400 230400 460800 (if not set 230400 is used) (Speed here and on LS3 'UART Baud' must match) (for 1280Hz 460800 should be used, or data is lost)
```

## Usage
```
usage: PyLS3.py [-h] [-ca APPCFG] [-cu USERCFG] [-nsc] [-c CONF] [-nuc] [-nc]

PyLS3 - This Python script connects to Linescale3 via Bluetooth or Serial (USB
UART).

optional arguments:
  -h, --help            show this help message and exit
  -ca APPCFG, --appcfg APPCFG
                        PyLS3 App configuration File (default:PyLS3_AppCfg.yml)
  -cu USERCFG, --usercfg USERCFG
                        PyLS3 User configuration File (overrides PyLS3 App
                        configurations and args override both) (default:PyLS3_UserCfg.yml)
  -nsc, --not_save_cfg  Do not save a Backup of PyLS3_AppCfg and
                        PyLS3_UserCfg.yml at startup (default: False)
  -c CONF, --conf CONF  could be applied multiple times: e.g. -c AppSettings: 
                        UseDevices:LS3_1:InitialCommands:["'Speed40', 'ModeREL'"] -c AppSettings:
                        UseDevices:LS3_1:ConnectionType:Bluetooth (default:None)
  -nuc, --no_user_console
                        Do not start user-console (default: False)
  -nc, --no_color       Logging without color (e.g. for windows cmd) (default:False)

```

```
usage: PyLS3_plot.py [-h] -f FILENAME [-ct CSV_TYPE] [-hl HEADER_LIST]
                     [-rl ROW_INDEX_LIST] [-rlo] [-ni] [-sp] [-noi]

PyLS3 Plot - create Plots of LS3py csv files

optional arguments:
  -h, --help            show this help message and exit
  -f FILENAME, --filename FILENAME
                        CSV File-Name (default: None)
  -ct CSV_TYPE, --csv_type CSV_TYPE
                        csv_type: 'pyls3' | 'onboardlogging' (default: pyls3)
  -hl HEADER_LIST, --header_list HEADER_LIST
                        only for csv_type 'pyls3': list of all column headers
                        (default: ['device_name', 'present_time',
                        'rx_timestamp', 'rx_delays', 'measured_value',
                        'unit_value_parsed', 'reference_zero',
                        'measure_mode_parsed', 'speed_value_parsed',
                        'electric_quantity', 'working_mode_parsed'])
  -rl ROW_INDEX_LIST, --row_index_list ROW_INDEX_LIST
                        only for csv_type 'onboardlogging': List of all row
                        index names inc. DataStart (default: ['DeviceID',
                        'No', 'Date', 'Time', 'Unit', 'Speed', 'Trig', 'Stop',
                        'Pre', 'Catch', 'Total', 'DataStart'])
  -rlo, --row_index_list_old
                        Shortcut to use the old row-list pre LS3 v2.5
                        (default: False)
  -ni, --no-image       Don't save plot as image (dest=save_image) (default:
                        True)
  -sp, --show-plot      Open Plot for each csv file (default: False)
  -noi, --not-override-image
                        Open Plot for each csv file (dest=override_image)
                        (default: True)
```

```
usage: PyLS3_onboardlogging.py [-h] [-d DIRECTORY] [-nr] [-r] [-ni] [-sp]
                               [-ne] [-c] [-ct COMBINE_TOLERANCE]

LinScale3 Tool - This script automatically creates an Excel file from all
LineScale csv in one folder and a plot png image.

optional arguments:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        Directory of the LinScale3 csv Files (default: Data)
  -nr, --non-recursive  Non Recursive (only execute in dir) (default: False)
  -r, --repeat          Repeat execution in folders which are containing the
                        master excel file (default: False)
  -ni, --no-image       Don't save plot as image (default: False)
  -sp, --show-plot      Open Plot for each csv file (default: False)
  -ne, --no-excel
  -c, --combine         Combine measurements (default: False)
  -ct COMBINE_TOLERANCE, --combine_tolerance COMBINE_TOLERANCE
                        Max tolerance to detect combine measurements (default:
                        15)
```

```
usage: PyLS3_multiplot.py [-h] [-fp FILENAME_PYLS3]
                          [-fo FILENAME_ONBOARDLOGGING] [-hl HEADER_LIST]  
                          [-ni] [-if IMAGE_FILE] [-noi] [-sp]
                          [-pll {0,1,2,3,4,5,6,7,8,9,10,11}]
                          [-pcl PLOT_COLOR_LIST] [-ptmo] [-pt PLOT_TITLE]  
                          [-ptfs PLOT_TITLE_FONTSIZE]
                          [-pfu {as_first_file,unchanged,kN,kgf,lbf}]      
                          [-ts TIME_SHIFT] [-noa] [-ot OVERLAP_TOLERANCE]  
                          [-pst] [-nc] [-ca APPCFG] [-cu USERCFG] [-c CONF]
                          [-tcf TIMING_CORRECTION_FACTOR]

PyLS3 Plot - create Plots of multiple csv files

optional arguments:
  -h, --help            show this help message and exit
  -fp FILENAME_PYLS3, --filename_pyls3 FILENAME_PYLS3
                        pyls3 CSV File-Name (could be applied multiple times)
                        (default: None)
  -fo FILENAME_ONBOARDLOGGING, --filename_onboardlogging FILENAME_ONBOARDLOGGING
                        onboardlogging CSV File-Name (could be applied
                        multiple times) (default: None)
  -hl HEADER_LIST, --header_list HEADER_LIST
                        only for csv_type 'pyls3': list of all column headers
                        (default: ['device_name', 'present_time',
                        'rx_timestamp', 'rx_delays', 'measured_value',
                        'unit_value_parsed', 'reference_zero',
                        'measure_mode_parsed', 'speed_value_parsed',
                        'electric_quantity', 'working_mode_parsed'])
  -ni, --no-image       Don't save plot as image (dest=save_image) (default:
                        True)
  -if IMAGE_FILE, --image_file IMAGE_FILE
                        Path/Filename where the image should be saved
                        (Default: take filename from first file) (default:
                        None)
  -noi, --not-override-image
                        Open Plot for each csv file (dest=override_image)
                        (default: True)
  -sp, --show-plot      Open Plot for each csv file (default: False)
  -pll {0,1,2,3,4,5,6,7,8,9,10,11}, --plot_legend_location {0,1,2,3,4,5,6,7,8,9,10,11}
                        Location of the plot legend: {0: 'best', 1: 'upper
                        right', 2: 'upper left', 3: 'lower left', 4: 'lower
                        right', 5: 'right', 6: 'center left', 7: 'center
                        right', 8: 'lower center', 9: 'upper center', 10:
                        'center', 11: 'off'} (default: 0)
  -pcl PLOT_COLOR_LIST, --plot_color_list PLOT_COLOR_LIST
                        Color for all Plot-Line. misc/print_plot_colortable.py
                        could be used to show all possible colorsMultiple
                        values are supported:"'r','g','y'"A list with the same
                        length as all files is generated. If the list is
                        smaller it's filled up with tha last given value
                        (default: auto)
  -ptmo, --plot_minmax_total_only
                        mark only total Min and Max (default: False)
  -pt PLOT_TITLE, --plot_title PLOT_TITLE
                        Title of the Plot (default: f'LS3 Multi
                        Plot\nMax:{max_total} Min:{min_total}')
  -ptfs PLOT_TITLE_FONTSIZE, --plot_title_fontsize PLOT_TITLE_FONTSIZE
                        The plot title fontsize (default: 15)
  -pfu {as_first_file,unchanged,kN,kgf,lbf}, --plot_force_unit {as_first_file,unchanged,kN,kgf,lbf}
                        Print the plot in selected forece Unit (default:
                        as_first_file)
  -ts TIME_SHIFT, --time_shift TIME_SHIFT
                        Time_shift for all files. A list with the same length
                        as all files is generated. If the list is smaller it's
                        filled up with tha last given value. Multiple values
                        are supported: "1.5, 2.3 -1.3" the time is added or
                        delete from the timestamp (default: 0)
  -noa, --not-autocorrect-offset
                        Disable auto correcetion of time an offset for
                        onboardlogging (dest=autocorrect_offset) (default:
                        True)
  -ot OVERLAP_TOLERANCE, --overlap_tolerance OVERLAP_TOLERANCE
                        Max tolerance to detect overlapping measurements (Data
                        is still compared) (default: 15)
  -pst, --pyls3_smooth_timestamps
                        Smooth timestamps in pyls3. All timestamps will have
                        the same difference. Do not use if different speeds
                        are used, or data is partially interrupted. (default:
                        False)
  -nc, --no_color       Logging without color (e.g. for windows cmd) (default:
                        False)
  -ca APPCFG, --appcfg APPCFG
                        PyLS3 App configuration File (default:
                        PyLS3_AppCfg.yml)
  -cu USERCFG, --usercfg USERCFG
                        PyLS3 User configuration File (overrides PyLS3 App
                        configurations and args override both) (default:
                        PyLS3_UserCfg.yml)
  -c CONF, --conf CONF  could be applied multiple times: e.g. -c AppSettings:
                        UseDevices:LS3_1:InitialCommands:["'Speed40',
                        'ModeREL'"] -c AppSettings:
                        UseDevices:LS3_1:ConnectionType:Bluetooth (default:
                        None)
  -tcf TIMING_CORRECTION_FACTOR, --timing_correction_factor TIMING_CORRECTION_FACTOR
                        Correct timing inaccuracy in Onboardlogging-Files
                        (True|False|Float) (default: True)
```

------

open items / under observation

### Timing / Rate inaccuracy

I've noticed that there is a timing/rate inaccuracy on the LS3 (at least on my devices).
When data is captured it doesn't seem to happen with the exactly configured speed value.

These observations have been made:

 - When the LS3 captures the "Time" (on LS3 display) counts about 54-55 seconds, when in reality 60 seconds have passed  
   (therefore a 60 second onboard-logging capture takes about 66 seconds in reality. But the number of data entries is exactly 60s * configured speed, so the real speed (Hz) is lower)
 - When data is captured via USB Serial the received readings does not exactly match configured speed
 - The time deviation on the LS3 and the rate deviation is the same factor independent of the configured speed
 - The deviation is differs per LS3 device (but seems to be constant while changing the Firmwares)
 - When not corrected
   - comparing results of multiple LS3 onbaord logs in the test-setup in nearly impossible, because events seems to occur at a different time 
   - comparing LS3 onbaord logs and PyLS3 logs is hard, because of the different timing

So far all tested firmwares (2.411, 2.520, 2.530, 2.600) seem to be affected

| Configured Hz | Onboard-Logging<br/>Hz (real value*) | Onboard-Logging<br/>deviation factor* | Serial 230400<br/>Hz (real value) | Serial 230400<br/>deviation factor | Serial 460800<br/>Hz (real value) | Serial 460800<br/>deviation factor | Bluetooth<br/>Hz (real value) |
| :-----------: | :----------------------------------: | :-----------------------------------: | :-------------------------------: | :--------------------------------: | :-------------------------------: | :--------------------------------: | :---------------------------: |
|      10       |                 9,00                 |                  0,9                  |               8,98                |         0,897996538191106          |               8,98                |         0,897837832900186          |             10,00             |
|      40       |                36,00                 |                  0,9                  |               35,91               |          0,89784566800526          |               35,91               |         0,897749444922552          |             46,48             |
|      640      |                576,00                |                  0,9                  |              574,51               |         0,897671351005605          |              574,58               |         0,897785228888166          |               -               |
|     1280      |               1.152,00               |                  0,9                  |             574,49**              |        0,448823278911447**         |             1.149,04              |         0,897685911067219          |               -               |

\* rate values for Onboard-Logging are calculated using LS3 counts 54 seconds in a real minute  
** Serial-Baud-Rate is too low for  1280Hz measurements

The deviation factor can be determined as follows:

 - via Serial measurement
   Capture date for a dedicated time, at a dedicated rate (speed Hz)  
       real-rate = number-of-readings / capture-time  
       deviation factor = real-rate / configured-rate  
       e.g. configured-rate=640Hz, capture-time=120s number-of-received-readings=68949  
       real-rate = 68949 / 120 = 574,575  
       deviation factor = 574,575 / 640 = 0,8977734375

Captures for different rates could be created automatically by PyLS3. e.g.:

```
UseDevices:
    LS3_1:
        InitialCommands:
            - ModeABS
            - UnitSwitchTokN
            - Speed10
            - StartCapture
            - Wait140
            - Speed40
            - StartCapture
            - Wait140
            - Speed640
            - StartCapture
            - Wait140
            - Speed1280
            - StartCapture
            - Wait140
Capture:
    PreCaptureTime_s: 0
    MaxCaptureTime_s: 120
    MinCaptureTime_s: 120
```

 - via time (this method is not very accurate)  
      deviation factor = capture time / real time  
       e.g deviation factor = 54 / 60 = 0.9

The TimingCorrectionFactor could be configured per device (if it is not configured 0.9 is used).  
But currently the TimingCorrectionFactor is only used for graphs created by PyLS3_multiplot.py  
(The TimingCorrectionFactor is only needed for plotting onboard-log files, since PyLS3 capture files are using receiving timestamps and are  therefore not affected) 

```
Device:
    LS3_1:
        TimingCorrectionFactor: 0.91122090   # correct timing inaccuracy (default 0.9)
```

------

