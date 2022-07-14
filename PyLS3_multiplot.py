#!/usr/bin/python3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import os
import asyncio
import re
import argparse
import glob
from datetime import datetime, timedelta
import warnings
import copy
# import platform


def autodetect_onboardlogging_headers(df: pd.DataFrame, odict):
    """
    This function searches for all available header values and indexes in the onboard logging files
    :param df: Dataframe we are working
    :param odict: original dictionary header information we are searching
    :return ldict: dictionary with all found header values and indexes
    """
    ldict = copy.deepcopy(odict)
    # check row_regex_dict
    for k in ldict:
        # index = None
        index = df.loc[ldict[k]['min_index']:ldict[k]['max_index'], 'measured_value'][
            df.loc[ldict[k]['min_index']:ldict[k]['max_index'], 'measured_value'].str.contains(ldict[k]['regex'], regex=True)].first_valid_index()
        if index is not None:
            value = re.search(ldict[k]['regex'], df.loc[index, 'measured_value']).group(ldict[k]['regex_group'])
            value = ldict[k]['value_type'](value)
            ldict[k]['index'] = index
            ldict[k]['value'] = value
            # print(k, index, value)

    # try to get Unit from Trigger file in old format
    if not ldict['Unit']['value']:
        value = re.search(ldict['Trig']['regex'], df.loc[ldict['Trig']['index'], 'measured_value']).group(2)
        ldict['Unit']['value'] = value

    # Default for device if not found
    if not ldict['Device']['value']:
        ldict['Device']['value'] = 'LS3'
    return ldict


# def autodetect_pyls3_headers(df: pd.DataFrame, header_list: list):
#     d = dict()
#     # Add all Values from the first column to a dictionary
#     for k in header_list:
#         d[k] = df.loc[0, k]
#     d['present_time'] = d['present_time'].split(".")[0]
#     d['unit_value_parsed'] = d['unit_value_parsed'].strip()
#     d['Speed'] = d['speed_value_parsed'] = d['speed_value_parsed'].strip()
#     d['measure_mode_parsed'] = d['measure_mode_parsed'].strip()
#     speed_list = [10, 40, 640, 1280]
#     if not d['Speed'] in speed_list:
#         d['Speed'] = None
#     return d


def create_filename_list(inlist):
    outlist = list()
    if inlist:
        for f in inlist:
            f = os.path.normpath(f)
            outlist = outlist + glob.glob(f, recursive=False)
    # Remove Duplicates entries in outlist
    outlist = list(dict.fromkeys(outlist))
    # sort outlist
    outlist.sort()
    return outlist


def find_overlap(last: list, current: list):
    """
    Compares the beginning of current and the end of last. When these are the same, returns the index till where current has the same values as last at the end.
    If no overlapping data is found 0 is returned.
    :param last: last list with data values
    :param current: current list with data values
    :return: the index for the overlapping data. current[overlap_index] will have the same value as last[-1] () same for df.loc[overlap_index:,]
    """
    min_list_len = min(len(last), len(current))
    overlap_index = 0
    for i in range(min_list_len, 0, -1):
        last_index = len(last) - i
        # print(f"{i} {current[0:i]} - {last[last_index:-1]}")
        if current[0:i] == last[last_index:]:
            overlap_index = i - 1
            break
    return overlap_index


def generate_same_length_list(in_value, reference_list):
    """
    generates a list of same length as reference_list
    :param in_value: string, tuple, list
    :param reference_list: reference_list for lenth
    :return: list of min same length as reference_list
    """
    # in_value should have the same length as reference_list
    # try:
    #     in_value = eval(in_value)
    # except Exception:
    #     pass
    # if isinstance(in_value, tuple):
    #     in_value = list(in_value)
    in_value = generate_list_from_str(in_value)
    if not isinstance(in_value, list):
        in_value = [in_value] * reference_list.__len__()
    elif in_value.__len__() < reference_list.__len__():
        for i in range(reference_list.__len__() - in_value.__len__()):
            in_value.append(in_value[-1])
    return in_value


def generate_list_from_str(in_value):
    try:
        in_value = eval(in_value)
    except Exception:
        pass
    if isinstance(in_value, tuple) or isinstance(in_value, list):
        in_value = list(in_value)
    return in_value


def find_device_by_device_short_id(device_short_id, PyLS3_Conf):
    for d in PyLS3_Conf['Device']:
        # print(d, PyLS3_Conf['Device'][d]['MAC'], device_short_id)
        if PyLS3_Conf['Device'][d]['MAC'].endswith(device_short_id):
            return d
    return None


def get_unit_convert_factor(in_unit, out_unit):
    kgf_to_kn = 0.00980665
    kgf_to_lbf = 2.2046226218488
    if in_unit.lower() == out_unit.lower():
        return 1
    if in_unit.lower() == 'kn' and out_unit.lower() == 'kgf':
        return 1 / kgf_to_kn
    if in_unit.lower() == 'kn' and out_unit.lower() == 'lbf':
        return 1 / kgf_to_kn * kgf_to_lbf
    if in_unit.lower() == 'kgf' and out_unit.lower() == 'kn':
        return kgf_to_kn
    if in_unit.lower() == 'kgf' and out_unit.lower() == 'lbf':
        return kgf_to_lbf
    if in_unit.lower() == 'lbf' and out_unit.lower() == 'kgf':
        return 1 / kgf_to_lbf
    if in_unit.lower() == 'lbf' and out_unit.lower() == 'kn':
        return 1 / kgf_to_lbf * kgf_to_kn
    print('WARNING> Wrong force units, use factor 1')
    return 1


async def main():
    plot_legend_location = {
        0: 'best',
        1: 'upper right',
        2: 'upper left',
        3: 'lower left',
        4: 'lower right',
        5: 'right',
        6: 'center left',
        7: 'center right',
        8: 'lower center',
        9: 'upper center',
        10: 'center',
        11: 'off',
    }

    # Parse CLI args
    parser = argparse.ArgumentParser(
        description='PyLS3 Plot - create Plots of multiple csv files',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Have fun ;)")
    parser.add_argument('-fp', '--filename_pyls3', default=None, action='append', help='pyls3 CSV File-Name (could be applied multiple times)')
    parser.add_argument('-fo', '--filename_onboardlogging', default=None, action='append', help='onboardlogging CSV File-Name (could be applied multiple times)')
    parser.add_argument('-hl', '--header_list',
                        default=['device_name', 'present_time', 'rx_timestamp', 'rx_delays', 'measured_value', 'unit_value_parsed', 'reference_zero', 'measure_mode_parsed', 'speed_value_parsed', 'electric_quantity', 'working_mode_parsed'],
                        help="only for csv_type 'pyls3': list of all column headers")
    parser.add_argument('-ni', '--no-image', default=True, action="store_false", dest='save_image', help='Don\'t save plot as image (dest=save_image)')
    parser.add_argument('-if', '--image_file', default=None, help='Path/Filename where the image should be saved (Default: take filename from first file)')
    parser.add_argument('-noi', '--not-override-image', default=True, action="store_false", dest='override_image', help='Open Plot for each csv file (dest=override_image)')
    parser.add_argument('-sp', '--show-plot', default=False, action="store_true", help='Open Plot for each csv file')
    parser.add_argument('-pll', '--plot_legend_location', default=0, type=int, choices=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], help=f"Location of the plot legend: {plot_legend_location}")
    parser.add_argument('-pcl', '--plot_color_list', default='auto', type=str, help='Color for all Plot-Line. '
                                                                                    'misc/print_plot_colortable.py could be used to show all possible colors'
                                                                                    'Multiple values are supported:'
                                                                                    '"\'r\',\'g\',\'y\'"'
                                                                                    'A list with the same length as all files is generated. If the list is smaller it\'s filled up with tha last given value')
    parser.add_argument('-ptmo', '--plot_minmax_total_only', default=False, action="store_true", help='mark only total Min and Max')
    parser.add_argument('-pt', '--plot_title',
                        default="f'LS3 Multi Plot\\nMax:{max_total} Min:{min_total}'",
                        help="Title of the Plot")
    parser.add_argument('-ptfs', '--plot_title_fontsize', default=15, type=int, help="The plot title fontsize")
    parser.add_argument('-pfu', '--plot_force_unit', default='as_first_file', type=str, choices=['as_first_file', 'unchanged', 'kN', 'kgf', 'lbf'], help="Print the plot in selected forece Unit")

    parser.add_argument('-ts', '--time_shift', default='0', type=str,
                        help='Time_shift for all files. '
                             'A list with the same length as all files is generated. If the list is smaller it\'s filled up with tha last given value. '
                             'Multiple values are supported: '
                             '"1.5, 2.3 -1.3" the time is added or delete from the timestamp')
    parser.add_argument('-noa', '--not-autocorrect-offset', default=True, action="store_false", dest='autocorrect_offset', help='Disable auto correcetion of time an offset for onboardlogging (dest=autocorrect_offset)')
    parser.add_argument('-ot', '--overlap_tolerance', default=15, type=int, help='Max tolerance to detect overlapping measurements (Data is still compared)')
    parser.add_argument('-pst', '--pyls3_smooth_timestamps', default=False, action="store_true", help='Smooth timestamps in pyls3. All timestamps will have the same difference. Do not use if different speeds are used, or data is partially interrupted.')

    parser.add_argument('-nc', '--no_color', default=False, action="store_true", help='Logging without color (e.g. for windows cmd)')
    parser.add_argument('-ca', '--appcfg', default='PyLS3_AppCfg.yml', help='PyLS3 App configuration File')
    parser.add_argument('-cu', '--usercfg', default='PyLS3_UserCfg.yml', help='PyLS3 User configuration File (overrides PyLS3 App configurations and args override both)')
    parser.add_argument("-c", '--conf', default=None,
                        action='append',
                        help='''could be applied multiple times: 
                             e.g. -c AppSettings: UseDevices:LS3_1:InitialCommands:["\'Speed40\', \'ModeREL\'"]\
                                  -c AppSettings: UseDevices:LS3_1:ConnectionType:Bluetooth
                             '''
                        )
    parser.add_argument('-tcf', '--timing_correction_factor', default='True', help='Correct timing inaccuracy in Onboardlogging-Files (True|False|Float) ')
    args = parser.parse_args()

    # Todo check functionality and move imports to top
    from PyLS3 import CustomFormatter, CustomFormatterNoColor, load_PyLS3_Conf, norm_file_and_path
    import platform
    import logging

    # Clear screen on Windows (workaround, so colors are working in cmd)
    if platform.system() == 'Windows':
        os.system('cls')

    # create logger with 'spam_application'
    logger = logging.getLogger("PyLS3 Multiplot")
    logger.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    if args.no_color:
        ch.setFormatter(CustomFormatterNoColor())
    else:
        ch.setFormatter(CustomFormatter())
    logger.addHandler(ch)

    PyLS3_Conf = load_PyLS3_Conf(args)

    # Todo: replace row_dict / row_dict2 ...
    row_dict = PyLS3_Conf['LS3OS']['Generic']['OnboardLogging_row_dict'].copy()

    if not args.filename_pyls3 and not args.filename_onboardlogging:
        print(f"Error at least --filename_pyls3 or --filename_onboardlogging must be set. Use -h option to display help")
        return

    # get all filenames
    filename_pyls3_list = create_filename_list(args.filename_pyls3)
    filename_onboardlogging_list = create_filename_list(args.filename_onboardlogging)

    # Merge both lists
    filename_list = filename_pyls3_list + filename_onboardlogging_list

    # Create some dicts and generate some default values
    df = dict()
    date_obj = dict()
    date_list = list()
    data_offset = dict()
    time_shift = dict()
    header_dict = dict()
    color_dict = dict()
    overlap_offset = dict()
    onboardlogging_last_list = None

    # Generate list
    args.header_list = generate_list_from_str(args.header_list)
    # Generate same length lists
    args.time_shift = generate_same_length_list(args.time_shift, filename_list)
    args.plot_color_list = generate_same_length_list(args.plot_color_list, filename_list)

    # Add time_shift to each files
    for i, f in enumerate(filename_list):
        time_shift[f] = args.time_shift[i]
        color_dict[f] = args.plot_color_list[i]

    # read all files to dataframes and get lowest starttime
    # pyls3 csv files
    for f in filename_pyls3_list[:]:
        try:
            file_error = False
            df[f] = pd.read_csv(f, names=args.header_list)
            speed_ok = df[f].loc[0, 'speed_value_parsed'].strip() in ['10Hz', '40Hz', '640Hz', '1280Hz']
        # except (pd.errors.UnsortedIndexError, AttributeError):
        except Exception:
            file_error = True
        if file_error or not speed_ok:
            print(f"WARNING> File:'{f}' has wrong format and will be skipped.")
            del df[f]
            filename_pyls3_list.remove(f)
            filename_list.remove(f)
            continue
        date_obj[f] = datetime.strptime(df[f].loc[0, 'present_time'], ' %Y-%m-%d %H:%M:%S.%f') + timedelta(seconds=time_shift[f])
        date_list.append(date_obj[f].timestamp())

    # onboardlogging csv files
    for i, f in enumerate(filename_onboardlogging_list[:]):
        try:
            file_error = False
            if f in df.keys():
                print(f"WARNING> File:'{f}' already opened and will be skipped.")
                filename_onboardlogging_list.remove(f)
                continue
            df[f] = pd.read_csv(f, names=['measured_value'])
            header_dict[f] = autodetect_onboardlogging_headers(df[f], row_dict)
        # except pd.errors.UnsortedIndexError:
        except Exception:
            file_error = True
        # check if cvs file has the correct format
        if file_error or not header_dict[f]['Speed']['value']:
            print(f"WARNING> File:'{f}' has wrong format and will be skipped.")
            del df[f]
            filename_onboardlogging_list.remove(f)
            filename_list.remove(f)
            continue

        # dateformat = '%d.%m.%y %H:%M:%S'
        dateformat = f"{PyLS3_Conf['OnboardLogging']['CSVDateFormatFromLS3']} {PyLS3_Conf['OnboardLogging']['CSVTimeFormatFromLS3']}"
        date_obj[f] = datetime.strptime(f"{header_dict[f]['Date']['value']} {header_dict[f]['Time']['value']}", dateformat) + timedelta(seconds=time_shift[f])
        date_list.append(date_obj[f].timestamp() - header_dict[f]['Pre']['value'])

    if not filename_list:
        print(f"ERROR> No valid files in filename_list. Check -fp/-fo file(s). Use -h option to display help")
        return

    # Min date/time is 0 reference for the plot
    date_min = min(date_list)

    # Plot Force vs time
    fig = plt.figure(figsize=[20, 10])
    # fig = plt.figure(figsize=[16, 12])
    ax1 = fig.add_subplot(1, 1, 1)

    #
    for f in filename_pyls3_list:
        data_offset[f] = 0                                                          # Not used for pyls3 csv files
        overlap_offset[f] = 0                                                       # Not used for pyls3 csv files
        # Create adjusted seconds column
        second_value = (date_obj[f].timestamp() - date_min)                          # calculate start offset
        df[f]['Seconds'] = pd.Series(dtype='float')                                  # add new column

        real_start_timestamp = round(df[f].iloc[0, :]['rx_timestamp'], 8)
        real_end_timestamp = round(df[f].iloc[-1, :]['rx_timestamp'], 8)
        start_timestamp = round(real_start_timestamp - date_min + time_shift[f], 8)
        end_timestamp = round(real_end_timestamp - date_min + time_shift[f], 8)
        if args.pyls3_smooth_timestamps:
            # calculate same delay between each row (smooth_timestamps)
            row_count = df[f]['rx_timestamp'].count()                                                   # smooth_timestamps
            delay_per_row = (end_timestamp - start_timestamp) / (row_count - 1)                         # smooth_timestamps

        # Converting Units - set to first value
        if args.plot_force_unit == 'as_first_file':
            args.plot_force_unit = df[f].loc[0, 'unit_value_parsed'].lstrip()

        for i in df[f].index:
            # Converting Units
            if not args.plot_force_unit == 'unchanged':
                unit_convert_factor = get_unit_convert_factor(df[f].loc[0, 'unit_value_parsed'].lstrip(), args.plot_force_unit)
                if unit_convert_factor != 1:
                    df[f].loc[i, 'measured_value'] = round(df[f].loc[i, 'measured_value'].astype('float') * unit_convert_factor, 2)

            df[f].loc[i, 'Seconds'] = second_value
            # Timestamp correction does not work as expected
            # Rates does not seem to be accurate over serial??? 45 instead of 40 ??
            # second_value = round(second_value + 1 / int(re.search('([0-9]+)', df[f]['speed_value_parsed'][i]).group(1)), 8)
            #
            if args.pyls3_smooth_timestamps:
                # or use same delay_per row                                                             # smooth_timestamps
                second_value += delay_per_row                                                           # smooth_timestamps
            else:
                # use rx_timestamp                                                                      # rx_timestamps
                second_value = round(df[f].loc[i, 'rx_timestamp'] - date_min + time_shift[f], 8)        # rx_timestamps

        print(f"Start:{start_timestamp} End:{end_timestamp} Dur:({end_timestamp - start_timestamp}) - (values include time_shift:{time_shift[f]}) - file:{f}")

    # prepare filename_onboardlogging_list
    last_end_time = 0
    for f in filename_onboardlogging_list:
        data_offset[f] = header_dict[f]['data_offset']['index']
        # Converting Units
        if args.plot_force_unit == 'as_first_file':
            args.plot_force_unit = header_dict[f]['Unit']['value']
        if args.plot_force_unit == 'unchanged':
            # Nothing to do
            pass
        else:
            unit_convert_factor = get_unit_convert_factor(header_dict[f]['Unit']['value'], args.plot_force_unit)
            if unit_convert_factor != 1:
                df[f].loc[data_offset[f]:, 'measured_value'] = round(df[f].loc[data_offset[f]:, 'measured_value'].astype('float') * unit_convert_factor, 2)

        # check if is this measurement overlapping
        real_start_time = date_obj[f].timestamp() - header_dict[f]['Pre']['value']
        end_time = date_obj[f].timestamp() + header_dict[f]['Catch']['value']
        onboardlogging_current_list = list(df[f].loc[data_offset[f]:, 'measured_value'])
        overlap_index = 0
        info_msg = "INFO   : time overlap outside tolerance & no data overlap "
        # if args.autocorrect_offset and real_start_time - args.overlap_tolerance <= last_end_time:
        if args.autocorrect_offset and -args.overlap_tolerance <= real_start_time - last_end_time <= args.overlap_tolerance:
            # for finding overlapping data
            if onboardlogging_last_list:
                overlap_index = find_overlap(onboardlogging_last_list, onboardlogging_current_list)
                if overlap_index:
                    info_msg = "INFO   : time overlap in tolerance & data overlap found   "
                else:
                    info_msg = "WARNING: time overlap in tolerance, but no data overlap found"
        # only change start time if overlapping data is found
        if overlap_index > 0:
            # second_value = last_second_value + time_drift[f]
            second_value = last_second_value
        else:
            # second_value = (date_obj[f].timestamp() - header_dict[f]['Pre']['value'] + time_drift[f] - date_min)
            second_value = (date_obj[f].timestamp() - header_dict[f]['Pre']['value'] - date_min)
        onboardlogging_last_list = onboardlogging_current_list
        overlap_offset[f] = overlap_index

        # Create adjusted seconds column
        df[f].reset_index(inplace=True)
        # timing_correction_factor for LS3
        try:
            args.timing_correction_factor = float(args.timing_correction_factor)
        except ValueError:
            pass
        if type(args.timing_correction_factor) in (float, int):
            timingcorrectionfactor = args.timing_correction_factor
        elif args.timing_correction_factor == "False" or not args.timing_correction_factor:
            timingcorrectionfactor = 1
        else:
            d = find_device_by_device_short_id(header_dict[f]['Device']['value'], PyLS3_Conf)
            try:
                timingcorrectionfactor = PyLS3_Conf['Device'][d]['TimingCorrectionFactor']
            except KeyError:
                timingcorrectionfactor = 0.9
        # print('DEBUG> timingcorrectionfactor', timingcorrectionfactor)  # Todo to remove, only for debugging

        df[f]['index'] = (df[f]['index'] - data_offset[f] - overlap_offset[f]) / header_dict[f]['Speed']['value'] / timingcorrectionfactor + second_value    # -i Data Offset in csv
        # without timingcorrectionfactor # df[f]['index'] = (df[f]['index'] - data_offset[f] - overlap_offset[f]) / header_dict[f]['Speed']['value'] + second_value    # -i Data Offset in csv
        df[f].rename({'index': 'Seconds'}, axis=1, inplace=True)
        last_second_value = df[f].loc[df[f].index[-1], 'Seconds']

        print(f"{info_msg} - overlap_offset:{overlap_offset[f]} - Start:{second_value} End:{last_second_value} Dur:({last_second_value - second_value}) - real_start_time:{real_start_time} end_time:{end_time} - file:{f}")
        last_end_time = end_time

    line_list = list()
    min_list = list()
    max_list = list()
    min_index_list = list()
    max_index_list = list()
    for i, f in enumerate(filename_list):
        # plot df (with color support)
        if color_dict[f] in (list(mcolors.BASE_COLORS.keys()) + list(mcolors.TABLEAU_COLORS.keys()) + list(mcolors.CSS4_COLORS.keys())):
            line_list += ax1.plot(df[f].loc[data_offset[f] + overlap_offset[f]:, 'Seconds'], df[f].loc[data_offset[f] + overlap_offset[f]:, 'measured_value'].astype('float'), label=f, color=color_dict[f])
        else:
            line_list += ax1.plot(df[f].loc[data_offset[f] + overlap_offset[f]:, 'Seconds'], df[f].loc[data_offset[f] + overlap_offset[f]:, 'measured_value'].astype('float'), label=f)

        # Plot min and max point
        min_measured_value = df[f].loc[data_offset[f] + overlap_offset[f]:, 'measured_value'].astype('float').min()
        min_list.append(min_measured_value)
        min_index = df[f].loc[data_offset[f] + overlap_offset[f]:, 'Seconds'][df[f].loc[data_offset[f] + overlap_offset[f]:, 'measured_value'].astype('float').idxmin()]
        min_index_list.append(min_index)
        max_measured_value = df[f].loc[data_offset[f] + overlap_offset[f]:, 'measured_value'].astype('float').max()
        max_list.append(max_measured_value)
        max_index = df[f].loc[data_offset[f] + overlap_offset[f]:, 'Seconds'][df[f].loc[data_offset[f] + overlap_offset[f]:, 'measured_value'].astype('float').idxmax()]
        max_index_list.append(max_index)
        # Print min max for each file
        if not args.plot_minmax_total_only:
            ax1.plot(min_index, min_measured_value, marker=(5, 2), color='y')
            ax1.plot(max_index, max_measured_value, marker=(5, 2), color='r')

        # file_name, dir_name, file = norm_file_and_path(f)
        # debug_file = os.path.join(dir_name, f"xdebug_{file_name}")
        # df[f].to_csv(debug_file)

    # Get total min and max (could be used in title)
    min_total = min(min_list)
    max_total = max(max_list)

    # Plot min and max point only for min_total and max_total
    if args.plot_minmax_total_only:
        ax1.plot(min_index_list[min_list.index(min_total)], min_total, marker=(5, 2), color='y')
        ax1.plot(max_index_list[max_list.index(max_total)], max_total, marker=(5, 2), color='r')

    # Plot title
    try:
        title = eval(args.plot_title)
    except Exception:
        title = args.plot_title
    ax1.set_title(f"{title}", fontweight="bold", fontsize=args.plot_title_fontsize)

    # display legend
    if not args.plot_legend_location == 11:
        ax1.legend(handles=line_list, loc=plot_legend_location[args.plot_legend_location])

    # Set Axis
    ax1.set_xlabel("Time (s)", fontweight="bold", fontsize=15)
    if args.plot_force_unit == 'unchanged':
        ax1.set_ylabel(f"Force", fontweight="bold", fontsize=15)
    else:
        ax1.set_ylabel(f"Force ({args.plot_force_unit})", fontweight="bold", fontsize=15)

    # Clean Graph
    ax1.spines["top"].set_visible(False)
    ax1.spines["bottom"].set_visible(True)
    ax1.spines["left"].set_visible(True)
    ax1.spines["right"].set_visible(False)
    plt.grid(False)
    # plt.grid(True)

    if args.save_image:
        if args.image_file:
            image_filename = args.image_file
        else:
            image_filename = f"{os.path.splitext(filename_list[0])[0]}_mplot.png"
        if os.path.isfile(image_filename) and not args.override_image:
            print(f"INFO> File '{image_filename}' already exists, skipping.")
        else:
            plt.savefig(image_filename)

    if args.show_plot:
        # plt.show()
        # plt.draw()
        plt.show(block=False)

    # wait if plots are open
    if args.show_plot:
        print(f'Waiting till all Plots are closed {plt.get_fignums()}')
        while plt.get_fignums():
            plt.pause(5000)

if __name__ == "__main__":
    # Supress warnings
    warnings.filterwarnings("ignore", 'This pattern has match groups')
    asyncio.run(main())
    # print(df.to_string())                            # print complete dataframe as
    # print(df[f].to_string())
    # from pprint import pprint; import pdb; pdb.set_trace()       # Todo: Remove for debugging only
    # df.to_csv(file_name, sep='\t', encoding='utf-8')
    #
    # f = "Data/test/old.CSV"
    # f = "Data/test/mid.CSV"
    # f = "Data/test/new.CSV"
    #
    # df = pd.read_csv(f, names=['measured_value'])
    # x = autodetect_onboardlogging_headers(df, row_dict)
    # print(id(x), id(row_dict))
    # print(id(x['Device']), id(row_dict['Device']))
    # from pprint import pprint; import pdb; pdb.set_trace()
    # file_name = os.path.basename(f)  # Todo to remove
    # dir_name = os.path.normpath((os.path.dirname(f)))  # Todo to remove
    # file_name = f"xxx{file_name}"  # Todo to remove
    # file = os.path.join(dir_name, file_name)  # Todo to remove
    # df[f].to_csv(f"{file}", sep=',', encoding='utf-8')  # Todo to remove
