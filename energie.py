# auth.py
from __future__ import print_function
from googleapiclient.discovery import build 
from google.oauth2 import service_account
import os
import pandas as pd
import matplotlib.pyplot as plt


class Energie:
    def __init__(self) -> None:
        # Parameter Settings
        self.SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets'
        ]
        self.SAMPLE_SPREADSHEET_ID = '1AUd0lPyr_g6Ml3odYm1fr6nvLRcw8uPiSeZHxuT0N9E'
        self.SAMPLE_RANGE_NAME = 'A1:D100'

        self.creds_file = os.path.join('.', 'credentials.json')
        self.plot_dir = os.path.join('.', 'plots')

        self.factor_m3_to_kWh = 10

        # get data
        self.get_data()

        # preprocessing
        self.preprocessing()

        # plots and stats
        self.plots_and_stats()

    def get_data(self):

        credentials = service_account.Credentials.from_service_account_file(self.creds_file, scopes=self.SCOPES)
        spreadsheet_service = build('sheets', 'v4', credentials=credentials)

        # Call the Sheets API
        sheet = spreadsheet_service.spreadsheets()
        result_input = sheet.values().get(spreadsheetId=self.SAMPLE_SPREADSHEET_ID,
                                    range=self.SAMPLE_RANGE_NAME).execute()
        values_input = result_input.get('values', [])

        # read as df
        self.df = pd.DataFrame(values_input[1:], columns=values_input[0])

    def preprocessing(self):

        # add columns
        self.df[['day', 'month', 'year']] = self.df['Datum'].str.split('.', 2, expand=True)

        # convert to datetime
        self.df['datetime'] = pd.to_datetime(self.df[['year', 'month', 'day']])

        # change index
        self.df.index = self.df['datetime']

        # resample to daily steps
        self.df_interpol = self.df[['Strom', 'Wasser', 'Gas']].resample('D').mean()

        # interpolate data
        self.df_interpol[['Strom_interp', 'Wasser_interp', 'Gas_interp']] = self.df_interpol[['Strom', 'Wasser', 'Gas']].interpolate()

        # first derivation to get daily consumption
        self.df_interpol[['Strom_interp_der', 'Wasser_interp_der', 'Gas_interp_der']] = self.df_interpol[['Strom_interp', 'Wasser_interp', 'Gas_interp']].diff()

        # monthly comsumption (on average)
        self.df_monthly = self.df_interpol.groupby(pd.PeriodIndex(self.df_interpol.index, freq="M"))[['Strom_interp_der', 'Wasser_interp_der', 'Gas_interp_der']].sum()
        self.df_monthly.index = self.df_monthly.index.strftime('%Y-%m')

    def plots_and_stats(self):
        
        # create folder (if not exist)
        if not os.path.exists(self.plot_dir):
            os.makedirs(self.plot_dir)

        # get yearly stats
        years = self.df['year'].unique()
        month_index = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']

        df_strom = pd.DataFrame(columns=years, index=month_index)
        df_gas = pd.DataFrame(columns=years, index=month_index)
        df_wasser = pd.DataFrame(columns=years, index=month_index)

        strom_legend = []
        gas_legend = []
        wasser_legend = []

        for year in years:
            mask = (self.df_monthly.index >= f'{year}-01') & (self.df_monthly.index <= f'{year}-12')
            data_year = self.df_monthly.loc[mask]

            # change index (remove year)
            idx_new = []
            for idx in data_year.index:
                idx_new.append(idx.split('-')[-1])
            data_year.index = idx_new

            print(f'Consumption for {year}:')
            print(f" Gas: {data_year['Gas_interp_der'].sum() * self.factor_m3_to_kWh:.1f} kWh")
            print(f" Strom: {data_year['Strom_interp_der'].sum():.1f} kWh")
            print(f" Wasser: {data_year['Wasser_interp_der'].sum():.1f} m3")
        
            # df
            df_strom[year] = data_year['Strom_interp_der']
            df_gas[year] = data_year['Gas_interp_der']
            df_wasser[year] = data_year['Wasser_interp_der']

            # legend
            strom_legend.append(f"{year} ({data_year['Strom_interp_der'].sum():.0f} kWh)")
            gas_legend.append(f"{year} ({data_year['Gas_interp_der'].sum() * self.factor_m3_to_kWh:.0f} kWh)")
            wasser_legend.append(f"{year} ({data_year['Wasser_interp_der'].sum():.0f} m3)")
            
            
        # Plots
        # Strom
        df_strom.plot.bar()
        plt.title('Verbrauch Strom')
        plt.xlabel('Month')
        plt.ylabel('[kWh]')
        plt.grid(axis='y')
        plt.legend(strom_legend)
        plt.tight_layout()
        plt.savefig(os.path.join(self.plot_dir, 'strom_verbrauch.png'))
        plt.clf()

        # Gas
        df_gas.plot.bar()
        plt.title('Verbrauch Gas')
        plt.xlabel('Month')
        plt.ylabel('[kWh]')
        plt.grid(axis='y')
        plt.legend(gas_legend)
        plt.tight_layout()
        plt.savefig(os.path.join(self.plot_dir, 'gas_verbrauch.png'))
        plt.clf()

        # Wasser
        df_wasser.plot.bar()
        plt.title('Verbrauch Wasser')
        plt.xlabel('Month')
        plt.ylabel('[kWh]')
        plt.grid(axis='y')
        plt.legend(wasser_legend)
        plt.tight_layout()
        plt.savefig(os.path.join(self.plot_dir, 'wasser_verbrauch.png'))
        plt.clf()

        # Control Plots (Ablesungen)
        # Strom
        plt.plot(self.df_interpol['Strom_interp'], '-')
        plt.plot(self.df_interpol['Strom'], '+')
        plt.title('Ablesungen Strom')
        plt.xticks(rotation=90)
        plt.grid(axis='y')
        plt.tight_layout()
        plt.savefig(os.path.join(self.plot_dir, 'strom_ablesungen.png'))
        plt.clf()

        # Gas
        plt.plot(self.df_interpol['Gas_interp'], '-')
        plt.plot(self.df_interpol['Gas'], '+')
        plt.title('Ablesungen Gas')
        plt.xticks(rotation=90)
        plt.grid(axis='y')
        plt.tight_layout()
        plt.savefig(os.path.join(self.plot_dir, 'gas_ablesungen.png'))
        plt.clf()

        # Wasser
        plt.plot(self.df_interpol['Wasser_interp'], '-')
        plt.plot(self.df_interpol['Wasser'], '+')
        plt.title('Ablesungen Wasser')
        plt.xticks(rotation=90)
        plt.grid(axis='y')
        plt.tight_layout()
        plt.savefig(os.path.join(self.plot_dir, 'wasser_ablesungen.png'))
        plt.clf()
        

if __name__ == '__main__':
    Energie()
