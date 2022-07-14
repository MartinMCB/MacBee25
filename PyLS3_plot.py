#!/usr/bin/python3
import pandas as pd
import matplotlib.pyplot as plt
import os
import asyncio
import re
import argparse
import warnings


async def plot_csv(filename: str,
                   csv_type: str = "pyls3",
                   header_list: list = ['device_name', 'present_time', 'rx_timestamp', 'rx_delays', 'measured_value', 'unit_value_parsed', 'reference_zero', 'measure_mode_parsed', 'speed_value_parsed', 'electric_quantity', 'working_mode_parsed'],
                   row_index_list: list = ['No', 'Date', 'Time', 'Speed', 'Trig', 'Stop', 'Pre', 'Catch', 'Total', 'DataStart'],
                   show_plot: bool = False,
                   save_image: bool = False,
                   override_image: bool = True,
                   ):
    """
    Create a plot for a csv file with LS3 data
    :param filename: filename of the csv file
    :param csv_type: 'pyls3' | 'onboardlogging'
    :param header_list: only for csv_type 'pyls3': list of all column headers
    :param row_index_list: only for csv_type 'onboardlogging': List of all row index names inc. DataStart
    :param show_plot: False | True # show plot window
    :param save_image: False | True # save plot png
    :param override_image: True | False # override existing image file
    :return:
    """
    # Create dictonary and add some default values
    d = dict()
    d['present_time'] = "NA"
    d['device_name'] = "LS3"
    d['unit_value_parsed'] = "NA"
    d['speed_value_parsed'] = "NA"
    d['measure_mode_parsed'] = "NA"

    if csv_type == 'pyls3':
        # Read CSV
        df = pd.read_csv(filename, names=header_list)

        # Add all Values from the first column to a dictionary
        for k in header_list:
            d[k] = df.loc[0, k]
        d['present_time'] = d['present_time'].split(".")[0]
        d['unit_value_parsed'] = d['unit_value_parsed'].strip()
        d['speed_value_parsed'] = d['speed_value_parsed'].strip()
        d['measure_mode_parsed'] = d['measure_mode_parsed'].strip()

        # Create a 'Seconds' row
        df['Seconds'] = (df['rx_timestamp'] - d['rx_timestamp'])
        data_offset = 0      # no data_offset in pyls3 csv

    elif csv_type == 'onboardlogging':
        # Read CSV
        df = pd.read_csv(filename, names=['measured_value'])

        # Read Info's from Header
        for i, k in enumerate(row_index_list):
            d[k] = df.loc[i, 'measured_value']
        data_offset = i
        speed = int(re.match('Speed=([0-9]+)', d['Speed']).group(1))
        d['present_time'] = f"{d['Date']} {d['Time']}"
        # d['device_name'] = "NA"
        try:
            d['unit_value_parsed'] = re.search('=([A-Za-z]+)', d['Unit']).group(1)
        except KeyError:
            try:
                d['unit_value_parsed'] = re.match('.*Trig=[0-9.]+([A-Za-z]+)', d['Trig']).group(1)
            except Exception:
                d['unit_value_parsed']
        d['speed_value_parsed'] = f"{speed}Hz"
        try:
            d['measure_mode_parsed'] = re.search('=([A-Za-z]+)', d['Mode']).group(1)
        except KeyError:
            # d['measure_mode_parsed'] = "NA"
            pass


        df.loc[data_offset:, 'measured_value'].astype('float')
        # Create Seconds column
        df.reset_index(inplace=True)
        df['index'] = (df['index'] - data_offset) / speed  # -i Data Offset in csv
        df.rename({'index': 'Seconds'}, axis=1, inplace=True)

    else:
        print(f"ERROR: Unknown csv_type '{csv_type}'! Possible values are 'pyls3', 'onboardlogging'.")
        return

    # get min & max
    min_measured_value = df.loc[data_offset:, 'measured_value'].astype('float').min()
    max_measured_value = df.loc[data_offset:, 'measured_value'].astype('float').max()

    # Plot kN vs time
    fig = plt.figure(figsize=[20, 10])
    # fig = plt.figure(figsize=[16, 12])
    ax1 = fig.add_subplot(1, 1, 1)
    ax1.plot(df.loc[data_offset:, 'Seconds'], df.loc[data_offset:, 'measured_value'].astype('float'))

    # Plot min and max point
    ax1.plot(df.loc[data_offset:, 'Seconds'][df.loc[data_offset:, 'measured_value'].astype('float').idxmin()], min_measured_value, marker=(5, 2), color='y')
    ax1.plot(df.loc[data_offset:, 'Seconds'][df.loc[data_offset:, 'measured_value'].astype('float').idxmax()], max_measured_value, marker=(5, 2), color='r')

    # Set Title
    ax1.set_title(
        f"{d['present_time']} {d['device_name']} Max:{max_measured_value} Min:{min_measured_value} Unit:{d['unit_value_parsed']} Speed:{d['speed_value_parsed']} Mode:{d['measure_mode_parsed']}",
        fontweight="bold", fontsize=17)

    # Set Axis
    ax1.set_xlabel("Time (s)", fontweight="bold", fontsize=15)
    ax1.set_ylabel(f"Force ({d['unit_value_parsed']})", fontweight="bold", fontsize=15)

    # Clean Graph
    ax1.spines["top"].set_visible(False)
    ax1.spines["bottom"].set_visible(True)
    ax1.spines["left"].set_visible(True)
    ax1.spines["right"].set_visible(False)
    plt.grid(False)
    # plt.grid(True)

    if save_image:
        image_filename = f"{os.path.splitext(filename)[0]}_plot.png"
        if os.path.isfile(image_filename) and not override_image:
            print(f"INFO> File '{image_filename}' already exists, skipping.")
        else:
            plt.savefig(image_filename)
    if show_plot:
        # plt.show()
        # plt.draw()
        plt.show(block=False)
    return ""


async def main():
    # Parse CLI args
    parser = argparse.ArgumentParser(
        description='PyLS3 Plot - create Plots of LS3py csv files',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Have fun ;)")
    parser.add_argument('-f', '--filename', default='None', required=True, help='CSV File-Name')
    parser.add_argument('-ct', '--csv_type', default='pyls3', help="csv_type: 'pyls3' | 'onboardlogging'")
    parser.add_argument('-hl', '--header_list',
                        default=['device_name', 'present_time', 'rx_timestamp', 'rx_delays', 'measured_value', 'unit_value_parsed', 'reference_zero', 'measure_mode_parsed', 'speed_value_parsed', 'electric_quantity', 'working_mode_parsed'],
                        help="only for csv_type 'pyls3': list of all column headers")
    parser.add_argument('-rl', '--row_index_list',
                        default=['DeviceID', 'Date', 'Time', 'No', 'Unit', 'Mode', 'RelZero', 'Speed', 'Trig', 'Stop', 'Pre', 'Catch', 'Total', 'DataStart'],
                        help="only for csv_type 'onboardlogging': List of all row index names inc. DataStart")
    parser.add_argument('-rlo', '--row_index_list_old', default=False, action="store_true", help='Shortcut to use the old row-list pre LS3 v2.5')
    parser.add_argument('-ni', '--no-image', default=True, action="store_false", dest='save_image', help='Don\'t save plot as image (dest=save_image)')
    parser.add_argument('-sp', '--show-plot', default=False, action="store_true", help='Open Plot for each csv file')
    parser.add_argument('-noi', '--not-override-image', default=True, action="store_false", dest='override_image', help='Open Plot for each csv file (dest=override_image)')
    args = parser.parse_args()

    # Supress warnings
    warnings.filterwarnings("ignore", 'This pattern has match groups')

    # convert args to lists
    for a in ['args.row_index_list', 'args.header_list']:
        if (isinstance(a, str)):
            exec(f"{a} = {eval(a)}")
    # print(type(args.row_index_list), args.row_index_list)

    # Todo: remove the complete row_index_list and replace with autodetection
    if args.row_index_list_old:
        args.row_index_list = ['No', 'Date', 'Time', 'Speed', 'Trig', 'Stop', 'Pre', 'Catch', 'Total', 'DataStart']

    await plot_csv(args.filename, args.csv_type, args.header_list, args.row_index_list, args.show_plot, args.save_image, args.override_image)

    # wait if plots are open
    if args.show_plot:
        print(f'Waiting till all Plots are closed {plt.get_fignums()}')
        while plt.get_fignums():
            plt.pause(5000)
    # # dummy run for testing
    # coro1 = plot_csv('Data/20211229_025926_LS3_1.csv', csv_type='pyls3', show_plot=False, save_image=True)
    # task1 = asyncio.create_task(coro1)
    # await task1
    # coro2 = plot_csv('Data/LS6AEF80/21_12_19/03_19_06.CSV', csv_type='onboardlogging', show_plot=False, save_image=True)
    # task2 = asyncio.create_task(coro2)
    # await task2

if __name__ == "__main__":
    asyncio.run(main())
