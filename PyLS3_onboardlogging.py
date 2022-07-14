#!/usr/bin/python
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import os
import re
import warnings
import copy
from datetime import datetime


def autodetect_onboardlogging_headers2(df: pd.DataFrame, column, odict):
    """
    This function searches for all available header values and indexes in the onboard logging files
    :param column:
    :param df: Dataframe we are working
    :param odict: original dictionary header information we are searching
    :return ldict: dictionary with all found header values and indexes
    """
    ldict = copy.deepcopy(odict)
    # check row_regex_dict
    for k in ldict:
        # index = None
        index = df.loc[ldict[k]['min_index']:ldict[k]['max_index'], column][
            df.loc[ldict[k]['min_index']:ldict[k]['max_index'], column].str.contains(ldict[k]['regex'], regex=True)].first_valid_index()
        # print(k, index)
        if index is not None:
            value = re.search(ldict[k]['regex'], df.loc[index, column]).group(ldict[k]['regex_group'])
            value = ldict[k]['value_type'](value)
            ldict[k]['index'] = index
            ldict[k]['value'] = value

    # try to get Unit from Trigger file in old format
    if not ldict['Unit']['value']:
        value = re.search(ldict['Trig']['regex'], df.loc[ldict['Trig']['index'], column]).group(2)
        ldict['Unit']['value'] = value

    # Default for device if not found
    if not ldict['Device']['value']:
        ldict['Device']['value'] = 'LS3'
    return ldict


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


def time_to_sec(time_str):
    ftr = [3600, 60, 1]
    return sum([a * b for a, b in zip(ftr, map(int, time_str.split(':')))])


def get_subfolders(dir: str) -> list:
    subfolders = []

    for f in os.scandir(dir):
        if f.is_dir():
            subfolders.append(f.path)

    for dir in list(subfolders):
        sf = get_subfolders(dir)
        subfolders.extend(sf)

    return subfolders


def max_min_reading(df: pd.DataFrame, data_offset: int = 8):
    """
    Insert max and min Reading to df
    :param df: source dataframe
    :param data_offset: offset where the measurement values start
    :return: df_final returning dataframe
    """
    # Raise error if starting_row is not an integer 
    if (not isinstance(data_offset, int)):
        raise ValueError('`starting_row` must be an integer')

    maxmin = []
    for i in df.columns:
        max_reading = df.loc[data_offset:, i].dropna().max()
        min_reading = df.loc[data_offset:, i].dropna().min()
        maxmin.append((max_reading, min_reading))

    df_maxmin = pd.DataFrame(maxmin, index=df.columns, columns=['Max', 'Min']).T

    df_final = pd.concat([df_maxmin, df], )

    return df_final


def index_to_sec(df: pd.DataFrame, speed: int = 10, data_offset: int = 10):
    """
    Take in dataframe and starting row to produce a maximum and minimum value for the readings
    :param df: Dataframe we are working with
    :param speed: speed in Hz
    :param data_offset: offset to the first data value
    :return: df_sec
    """
    df_sec = df.copy()
    df_sec.reset_index(inplace=True)
    # Exception if data_offset index is not available
    try:
        df_sec.loc[data_offset:, 'index'] = (df_sec.loc[data_offset:, 'index'] - df_sec.loc[data_offset, 'index']) / speed
    except KeyError:
        pass
    df_sec.rename({'index': 'Seconds'}, axis=1, inplace=True)
    return df_sec


def plot_df(df: pd.DataFrame, col, directory: str, data_offset: int = 10, show_plot: bool = False, no_image: bool = False):
    """
    Take in dataframe and column to produce graph of section
    :param df: Source dataframe
    :param col: current column in dataframe
    :param directory: directory of the source cvs file of the df
    :param data_offset: offset to the first data value
    :param show_plot: if true the plot-window will be show
    :param no_image: if set the plot will not be saved as png
    :return:
    """
    index_max = df[df['Seconds'].astype(str).str.contains('Max', regex=False)].first_valid_index()
    index_min = df[df['Seconds'].astype(str).str.contains('Min', regex=False)].first_valid_index()
    index_date = df[df['Seconds'].astype(str).str.contains('Date', regex=False)].first_valid_index()
    index_time = df[df['Seconds'].astype(str).str.contains('Time', regex=False)].first_valid_index()
    index_speed = df[df['Seconds'].astype(str).str.contains('Speed', regex=False)].first_valid_index()
    index_trig = df[df['Seconds'].astype(str).str.contains('Trig', regex=False)].first_valid_index()

    # index_mode = df[df['Seconds'].astype(str).str.contains('Mode', regex=False)].first_valid_index()
    # if index_mode:
    #     mode = re.match('Mode=([a-zA-Z]+)', df[col][index_mode]).group(1)

    index_unit = df[df['Seconds'].astype(str).str.contains('Unit', regex=False)].first_valid_index()
    if index_unit:
        unit = re.match('Unit=([a-zA-Z]+)', df[col][index_unit]).group(1)
    else:
        unit = re.match('.*[0-9.]+([A-Za-z]+)', df[col][index_trig]).group(1)

    device_name = 'LS3'

    # min_value = df.loc[data_offset:, col].astype('float').min()
    # max_value = df.loc[data_offset:, col].astype('float').max()

    # Plot values vs time
    fig = plt.figure(figsize=[20, 10])
    #fig = plt.figure(figsize=[19.2, 10.8])
    # fig = plt.figure(figsize=[16, 12])
    ax1 = fig.add_subplot(1, 1, 1)
    ax1.plot(df.loc[data_offset:, 'Seconds'], df.loc[data_offset:, col].astype('float'))

    # Plot min and max point
    ax1.plot(df.loc[data_offset:, 'Seconds'][df.loc[data_offset:, col].astype('float').idxmin()], df.loc[data_offset:, col].astype('float').min(), marker=(5, 2), color='y')
    ax1.plot(df.loc[data_offset:, 'Seconds'][df.loc[data_offset:, col].astype('float').idxmax()], df.loc[data_offset:, col].astype('float').max(), marker=(5, 2), color='r')

    # Set Title
    ax1.set_title(
        f"{df[col][index_date]} {df[col][index_time]} {device_name} Max:{df[col][index_max]} Min:{df[col][index_min]} Unit:{unit} Speed:{df[col][index_speed]}Hz",
        fontweight="bold", fontsize=17)

    # Set Axis
    ax1.set_xlabel("Time (s)", fontweight="bold", fontsize=15)
    ax1.set_ylabel(f"Force ({unit})", fontweight="bold", fontsize=15)

    # Clean Graph
    ax1.spines["top"].set_visible(False)
    ax1.spines["bottom"].set_visible(True)
    ax1.spines["left"].set_visible(True)
    ax1.spines["right"].set_visible(False)
    plt.grid(False)

    if not no_image:
        filename = re.sub("(\\.CSV)|(\\.csv)", "", col)
        filename = re.sub(" \\+ ", "_", filename)
        filename = f"{filename}_oplot.png"
        # if os.path.isfile(f'{directory}/{filename}'):
        #     os.remove(f'{directory}/{filename}')
        # on windows the timestamps of the pngs are not updated, but the files are overwritten
        plt.savefig(f'{directory}/{filename}')
    if show_plot:
        # plt.show()
        # plt.draw()
        plt.show(block=False)
    return ""


if __name__ == "__main__":
    warnings.filterwarnings("ignore", 'This pattern has match groups')

    # Parse CLI args
    parser = argparse.ArgumentParser(
        # prog='LineScale3 OnboardLogging',
        description='LinScale3 Tool - This script automatically creates an Excel file from all LineScale csv in one folder and a plot png image.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Have fun ;)")
    #    exit_on_error=False)

    parser.add_argument('-d', '--directory', default='Data', help='Directory of the LinScale3 csv Files')
    parser.add_argument('-nr', '--non-recursive', default=False, action="store_true", help='Non Recursive (only execute in dir)')
    parser.add_argument('-r', '--repeat', default=False, action="store_true", help='Repeat execution in folders which are containing the master excel file')
    parser.add_argument('-ni', '--no-image', default=False, action="store_true", help='Don\'t save plot as image')
    parser.add_argument('-sp', '--show-plot', default=False, action="store_true", help='Open Plot for each csv file')
    parser.add_argument('-ne', '--no-excel', default=False, action="store_true", help='')
    parser.add_argument('-c', '--combine', default=False, action="store_true", help='Combine measurements')
    parser.add_argument('-ct', '--combine_tolerance', default=15, type=int, help='Max tolerance to detect combine measurements')
    parser.add_argument('--debug', default=False, action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # ## Global Settings
    # Testing Values for debugging
    if args.debug: print(f'DEBUG> args={args}')  # Test Output

    row_dict2 = {
        'Device': {
            'regex': '(^[A-Z0-9]{2}:[A-Z0-9]{2}:[A-Z0-9]{2}$)',
            'regex_group': 1,
            'min_index': 0,
            'max_index': 0,
            'index': None,
            'value': None,
            'value_type': str,
        },
        'No': {
            'regex': '^(LogNo=)?(No\\.)?([0-9]+)$',
            'regex_group': 3,
            'min_index': 0,
            'max_index': 4,
            'index': None,
            'value': None,
            'value_type': int,
        },
        'Date': {
            'regex': '([0-9]{2}\\.[0-9]{2}\\.[0-9]{2})',
            'regex_group': 1,
            'min_index': 1,
            'max_index': 25,
            'index': None,
            'value': None,
            'value_type': str,
        },
        'Time': {
            'regex': '([0-9]{2}:[0-9]{2}:[0-9]{2})',
            'regex_group': 1,
            'min_index': 1,
            'max_index': 25,
            'index': None,
            'value': None,
            'value_type': str,
        },
        'Unit': {
            'regex': 'Unit=([a-zA-Z]+)',
            'regex_group': 1,
            'min_index': 1,
            'max_index': 25,
            'index': None,
            'value': None,
            'value_type': str,
        },
        'Speed': {
            'regex': 'Speed=([0-9]+)',
            'regex_group': 1,
            'min_index': 1,
            'max_index': 25,
            'index': None,
            'value': None,
            'value_type': int,
        },
        'Trig': {
            'regex': 'Trig=([0-9\\.]+)([a-zA-Z]*)',
            'regex_group': 1,
            'min_index': 1,
            'max_index': 25,
            'index': None,
            'value': None,
            'value_type': float,
        },
        'Stop': {
            'regex': 'Stop=([0-9\\.]+)',
            'regex_group': 1,
            'min_index': 1,
            'max_index': 25,
            'index': None,
            'value': None,
            'value_type': float,
        },
        'Pre': {
            'regex': 'Pre=([0-9\\.]+)',
            'regex_group': 1,
            'min_index': 1,
            'max_index': 25,
            'index': None,
            'value': None,
            'value_type': int,
        },
        'Catch': {
            'regex': 'Catch=([0-9\\.]+)',
            'regex_group': 1,
            'min_index': 1,
            'max_index': 25,
            'index': None,
            'value': None,
            'value_type': int,
        },
        'Total': {
            'regex': 'Total=([0-9\\.]+)',
            'regex_group': 1,
            'min_index': 1,
            'max_index': 25,
            'index': None,
            'value': None,
            'value_type': int,
        },
        'data_offset': {
            'regex': '^((-)?[0-9]+(\\.[0-9]+)?)$',
            'regex_group': 1,
            'min_index': 5,
            'max_index': 25,
            'index': None,
            'value': None,
            'value_type': float,
        },
    }

    onboardlogging_last_list = None

    # Todo to remove
    # row_regex_dict = {
    #     'Device': '^[A-Z0-9]{2}:[A-Z0-9]{2}:[A-Z0-9]{2}$',
    #     'No': 'No.*|^[0-9]{3,3}$',
    #     'Date': '[0-9]{2}\\.[0-9]{2}\\.[0-9]{2}',
    #     'Time': '[0-9]{2}:[0-9]{2}:[0-9]{2}',
    #     'Speed': 'Speed=',
    #     'Trig': 'Trig=',
    #     'Stop': 'Stop=',
    #     'Pre': 'Pre=',
    #     'Catch': 'Catch=',
    #     'Total': 'Total=',
    # }

    ext = [".csv"]  # searching only for csv Files (could be changed later)
    excelmasterfile = 'master.xlsx'

    # ## End Global Settings

    # Add Starting-Directory folders
    folders = [args.directory]

    # Add all Subfolders to folders to list folders (if recursive)
    if not args.non_recursive:
        folders.extend(get_subfolders(args.directory))
    if args.debug: print(f'DEBUG> folders={folders}')

    # loop through all folders
    for folder in list(folders):
        # get all csv files in folder
        cvsfiles = []
        if args.debug: print(f'\nDEBUG> folders={folder}')
        for f in os.scandir(folder):

            # Skip folders with existing masterfile if not args.repeat
            if not args.repeat:
                if f.name.lower() == excelmasterfile:
                    if args.debug: print(f'DEBUG> found Masterfile, skipping folder')
                    cvsfiles = []
                    break

            # only add csv files to cvsfiles list
            if f.is_file():
                if os.path.splitext(f.name)[1].lower() in ext:
                    if args.debug: print(f'DEBUG> {f.path}')
                    cvsfiles.append(f.path)
        if args.debug: print(f'DEBUG> {folder} - {cvsfiles}')

        # skip empty folders
        if not len(cvsfiles):
            if args.debug: print(f'DEBUG> Skip empty folder')
            continue

        # Make master dataframe
        df = pd.DataFrame()
        #
        # for combine
        last_speed = int()
        last_endtime_sec = int()
        #
        # add all files to df
        for i in range(0, len(cvsfiles)):
            if args.debug: print(f'DEBUG> {cvsfiles[i]}')
            try:
                # df2 = pd.read_csv(f'{cvsfiles[i]}')
                filename = os.path.basename(cvsfiles[i])
                df2 = pd.read_csv(cvsfiles[i], names=[filename])
                header_dict = autodetect_onboardlogging_headers2(df2, filename, row_dict2)
            # except pandas.errors.EmptyDataError:
            except Exception as e:
                if args.debug: print(f'DEBUG> {filename} is empty and has been skipped. Error: {e}')
                continue

            # Skipp if speed line is not found
            if not header_dict['Speed']['value']:
                if args.debug: print(f'DEBUG> {cvsfiles[i]} has wrong format and has been skipped.')
                continue


            # Create Row-Dict
            tmp_row_dict = dict()
            for k in header_dict:
                if header_dict[k]['index'] is not None and k is not 'data_offset':
                    tmp_row_dict[header_dict[k]['index']] = k
            row_dict = dict(sorted(tmp_row_dict.items()))

            data_offset = int(header_dict['data_offset']['index'])

            # Todo to replace / remove
            # for k in row_regex_dict:
            #     index = None
            #     regex = row_regex_dict[k]
            #     index = df2[df2[filename].str.contains(regex, regex=True)].first_valid_index()
            #     tmp_row_dict[index] = k
            #
            # # Skipp if speed line is not found
            # if "Speed (Hz)" not in tmp_row_dict.values():
            #     if args.debug: print(f'DEBUG> {cvsfiles[i]} has wrong format and has been skipped.')
            #     continue
            # row_dict = dict(sorted(tmp_row_dict.items()))
            # index_no = int(list(row_dict.keys())[list(row_dict.values()).index("No")])
            # index_speed = int(list(row_dict.keys())[list(row_dict.values()).index("Speed (Hz)")])
            # index_time = int(list(row_dict.keys())[list(row_dict.values()).index("Time")])
            # index_pre = int(list(row_dict.keys())[list(row_dict.values()).index("Pre")])
            # index_total = int(list(row_dict.keys())[list(row_dict.values()).index("Total")])
            # index_catch = int(list(row_dict.keys())[list(row_dict.values()).index("Catch")])
            # data_offset = int(index_total + 1)  # data starts after total

            # for combine from here
            #############################################################################
            # Remove unnecessary wording from rows
            df2.replace(to_replace=r'Speed=', value='', regex=True, inplace=True)
            df2.replace(to_replace=r'Trig=', value='', regex=True, inplace=True)
            df2.replace(to_replace=r'Stop=', value='', regex=True, inplace=True)
            df2.replace(to_replace=r'Pre=', value='', regex=True, inplace=True)
            df2.replace(to_replace=r'Catch=', value='', regex=True, inplace=True)
            df2.replace(to_replace=r'Total=', value='', regex=True, inplace=True)
            df2.replace(to_replace=r'Hz', value='', regex=True, inplace=True)

            same_measurement = False
            if args.combine:
                speed = header_dict['Speed']['value']
                total = header_dict['Total']['value']
                catch = header_dict['Catch']['value']
                pre = header_dict['Pre']['value']
                date_obj = datetime.strptime(f"{header_dict['Date']['value']} {header_dict['Time']['value']}", '%d.%m.%y %H:%M:%S')
                date_obj.timestamp() - header_dict['Pre']['value']
                starttime_sec = date_obj.timestamp()
                real_start_time_sec = starttime_sec - pre
                endtime_sec = starttime_sec + catch
                start_overlap = last_endtime_sec - real_start_time_sec
                index_no = header_dict['No']['index']
                index_total = header_dict['Total']['index']
                index_catch = header_dict['Catch']['index']

                overlap_index = 0
                onboardlogging_current_list = list(df2.loc[data_offset:, filename])
                if speed == last_speed:
                    if real_start_time_sec <= last_endtime_sec + args.combine_tolerance:
                        if onboardlogging_last_list:
                            overlap_index = find_overlap(onboardlogging_last_list, onboardlogging_current_list)
                        if overlap_index:
                            same_measurement = True
                            last_total = float(df[df.columns[-1]][header_dict['Total']['index']].replace("sec", ""))
                            new_total = last_total + total - start_overlap
                            last_catch = float(df[df.columns[-1]][header_dict['Catch']['index']].replace("sec", ""))
                            new_catch = last_catch + catch
                last_endtime_sec = endtime_sec
                last_speed = speed
                onboardlogging_last_list = onboardlogging_current_list

            if same_measurement:
                if args.debug: print(f'DEBUG> Same measurement - append to column')
                # if start_overlap < 0:
                #     start_overlap = 0
                # offset_overlap = start_overlap * speed + data_offset        # calculate the overlapping data, which is removed on merge
                dflastcolumn = df.columns[-1]
                dflastno = df.iloc[index_no, -1]
                lastandcurrent = df[df.columns[-1]].dropna().append(df2.iloc[overlap_index:, 0], ignore_index=True)
                df = pd.concat([df.iloc[:, :-1], lastandcurrent], axis=1)
                df = df.rename(columns={df.columns[-1]: f'{dflastcolumn} + {df2.columns[-1]}'})
                df.iloc[index_no, -1] = f'{dflastno} + {df2.iloc[index_no, -1]}'
                df[df.columns[-1]][index_total] = f'{new_total}sec'
                df[df.columns[-1]][index_catch] = f'{new_catch}sec'
                # import pdb; pdb.set_trace() # Breakpoint
            else:
                if args.debug: print(f'DEBUG> Different measurement')
                # for combine from here
                df = pd.concat([df, df2], axis=1)

            #######################################################################

        # skip if there is no context
        if df.empty:
            if args.debug: print(f'DEBUG> no Files with context in {folder}, skipped.')
            continue
        if args.debug: print(f'DEBUG> dataframe df in folder:{folder}\n------------------------------\n{df.head(10)}\n------------------------------')

        # Rename rows to match description and parse out values
        df.rename(row_dict, axis='index', inplace=True)

        # Remove unnecessary wording from rows
        df.replace(to_replace=r'Speed=', value='', regex=True, inplace=True)
        df.replace(to_replace=r'Trig=', value='', regex=True, inplace=True)
        df.replace(to_replace=r'Stop=', value='', regex=True, inplace=True)
        df.replace(to_replace=r'Pre=', value='', regex=True, inplace=True)
        df.replace(to_replace=r'Catch=', value='', regex=True, inplace=True)
        df.replace(to_replace=r'Total=', value='', regex=True, inplace=True)
        df.replace(to_replace=r'Hz', value='', regex=True, inplace=True)

        if args.debug: print(f'DEBUG> dataframe df in folder:{folder} (after renaming and replacing)\n------------------------------\n{df.head(10)}\n------------------------------')

        # Make min and max
        df = max_min_reading(df, data_offset)
        data_offset += 2
        if args.debug: print(f'DEBUG> dataframe df in folder:{folder}\n------------------------------ \n{df.head(15)}\n------------------------------')

        # Use Speed row to determine and separate based off of value. Possible values are 10, 40, 640, 1280.
        # These are in object format and not string format and cannot be changed (easily).
        hz_10_data = []
        hz_40_data = []
        hz_640_data = []
        hz_1280_data = []

        for i in df.columns:
            if df[i]['Speed'] == '10':
                hz_10_data.append(df[i].dropna())
            elif df[i]['Speed'] == '40':
                hz_40_data.append(df[i].dropna())
            elif df[i]['Speed'] == '640':
                hz_640_data.append(df[i].dropna())
            elif df[i]['Speed'] == '1280':
                hz_1280_data.append(df[i].dropna())
            else:
                break

        # Do for all Hz.
        df10 = pd.DataFrame(hz_10_data).T
        df40 = pd.DataFrame(hz_40_data).T
        df640 = pd.DataFrame(hz_640_data).T
        df1280 = pd.DataFrame(hz_1280_data).T

        # Do for all Hz.
        df10 = index_to_sec(df10, 10, data_offset)
        df40 = index_to_sec(df40, 40, data_offset)
        df640 = index_to_sec(df640, 640, data_offset)
        df1280 = index_to_sec(df1280, 1280, data_offset)
        if args.debug: print(f'DEBUG> dataframe nums40 in folder:{folder} (after renaming and replacing)\n------------------------------\n{df10.head(10)} {df40.head(10)}\n------------------------------')

        for i in df10.columns:
            if i == 'Seconds': continue
            plot_df(df10, i, folder, data_offset, args.show_plot, args.no_image)

        for i in df40.columns:
            if i == 'Seconds': continue
            plot_df(df40, i, folder, data_offset, args.show_plot, args.no_image)

        for i in df640.columns:
            if i == 'Seconds': continue
            plot_df(df640, i, folder, data_offset, args.show_plot, args.no_image)

        for i in df1280.columns:
            if i == 'Seconds': continue
            plot_df(df1280, i, folder, data_offset, args.show_plot, args.no_image)

        # Write to Excel file
        if not args.no_excel:
            with pd.ExcelWriter(f'{folder}/{excelmasterfile}') as writer:
                df10.to_excel(writer, sheet_name='10Hz Measurements')
                df40.to_excel(writer, sheet_name='40Hz Measurements')
                df640.to_excel(writer, sheet_name='640Hz Measurements')
                df1280.to_excel(writer, sheet_name='1280Hz Measurements')

    # wait if plots are open
    if args.show_plot:
        # end = input("Press Enter to close (all plots will be closed)")
        print(f'Waiting till all Plots are closed {plt.get_fignums()}')
        while plt.get_fignums():
            plt.pause(5000)
