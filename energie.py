from __future__ import print_function
from googleapiclient.discovery import build 
from google.oauth2 import service_account
import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


class Energie:
    def __init__(self) -> None:
        # Parameter Settings
        self.SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets'
        ]
        self.SAMPLE_SPREADSHEET_ID = '1AUd0lPyr_g6Ml3odYm1fr6nvLRcw8uPiSeZHxuT0N9E'
        self.RANGE_READINGS = 'A1:D100'
        self.RANGE_PRICES_STROM = 'H2:J20'
        self.RANGE_PRICES_GAS = 'L2:N20'
        self.RANGE_PRICES_WASSER = 'P2:R20'

        #self.creds_file = os.path.join('repos', 'energie', 'credentials.json')
        self.creds_file = os.path.join('.', 'credentials.json')
        self.plot_dir = os.path.join('.', 'plots')

        self.factor_m3_to_kWh = 10.5

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
        result_readings = sheet.values().get(spreadsheetId=self.SAMPLE_SPREADSHEET_ID,
                                    range=self.RANGE_READINGS).execute()
        values_readings = result_readings.get('values', [])
        result_prices_strom = sheet.values().get(spreadsheetId=self.SAMPLE_SPREADSHEET_ID,
                                    range=self.RANGE_PRICES_STROM).execute()
        values_prices_strom = result_prices_strom.get('values', [])
        result_prices_gas = sheet.values().get(spreadsheetId=self.SAMPLE_SPREADSHEET_ID,
                            range=self.RANGE_PRICES_GAS).execute()
        values_prices_gas = result_prices_gas.get('values', [])
        result_prices_wasser = sheet.values().get(spreadsheetId=self.SAMPLE_SPREADSHEET_ID,
                            range=self.RANGE_PRICES_WASSER).execute()
        values_prices_wasser = result_prices_wasser.get('values', [])

        # read as df
        self.df_readings = pd.DataFrame(values_readings[1:], columns=values_readings[0])
        self.df_prices_strom = pd.DataFrame(values_prices_strom[1:], columns=values_prices_strom[0])
        self.df_prices_gas = pd.DataFrame(values_prices_gas[1:], columns=values_prices_gas[0])
        self.df_prices_wasser = pd.DataFrame(values_prices_wasser[1:], columns=values_prices_wasser[0])

    def preprocessing(self):

        # add columns
        self.df_readings[['day', 'month', 'year']] = self.df_readings['Datum'].str.split('.', expand=True)
        self.df_prices_strom[['day', 'month', 'year']] = self.df_prices_strom['Datum'].str.split('.', expand=True)
        self.df_prices_gas[['day', 'month', 'year']] = self.df_prices_gas['Datum'].str.split('.', expand=True)
        self.df_prices_wasser[['day', 'month', 'year']] = self.df_prices_wasser['Datum'].str.split('.', expand=True)

        # convert to datetime
        self.df_readings['datetime'] = pd.to_datetime(self.df_readings[['year', 'month', 'day']])
        self.df_prices_strom['datetime'] = pd.to_datetime(self.df_prices_strom[['year', 'month', 'day']])
        self.df_prices_gas['datetime'] = pd.to_datetime(self.df_prices_gas[['year', 'month', 'day']])
        self.df_prices_wasser['datetime'] = pd.to_datetime(self.df_prices_wasser[['year', 'month', 'day']])

        # change index
        self.df_readings.index = self.df_readings['datetime']
        self.df_prices_strom.index = self.df_prices_strom['datetime']
        self.df_prices_gas.index = self.df_prices_gas['datetime']
        self.df_prices_wasser.index = self.df_prices_wasser['datetime']

        # resample to daily steps
        self.df_interpol = self.df_readings[['Strom', 'Wasser', 'Gas']].astype('float16').resample('D').mean()
        self.df_prices_strom_daily = self.df_prices_strom[['Arbeitspreis', 'Grundpreis']].astype('float32').resample('D').mean()
        self.df_prices_gas_daily = self.df_prices_gas[['Arbeitspreis', 'Grundpreis']].astype('float32').resample('D').mean()
        self.df_prices_wasser_daily = self.df_prices_wasser[['Arbeitspreis', 'Grundpreis']].astype('float32').resample('D').mean()

        # interpolate/pad data
        self.df_interpol[['Strom_interp', 'Wasser_interp', 'Gas_interp']] = self.df_interpol[['Strom', 'Wasser', 'Gas']].interpolate()
        self.df_prices_strom_daily[['Arbeitspreis_daily', 'Grundpreis_daily']] = self.df_prices_strom_daily[['Arbeitspreis', 'Grundpreis']].astype('float32').ffill(axis=0)
        self.df_prices_gas_daily[['Arbeitspreis_daily', 'Grundpreis_daily']] = self.df_prices_gas_daily[['Arbeitspreis', 'Grundpreis']].astype('float32').ffill(axis=0)
        self.df_prices_wasser_daily[['Arbeitspreis_daily', 'Grundpreis_daily']] = self.df_prices_wasser_daily[['Arbeitspreis', 'Grundpreis']].astype('float32').ffill(axis=0)

        # first derivation to get daily consumption
        self.df_interpol[['Strom_interp_der', 'Wasser_interp_der', 'Gas_interp_der']] = self.df_interpol[['Strom_interp', 'Wasser_interp', 'Gas_interp']].diff()

        # monthly comsumption (on average)
        self.df_monthly = self.df_interpol.groupby(pd.PeriodIndex(self.df_interpol.index, freq="M"))[['Strom_interp_der', 'Wasser_interp_der', 'Gas_interp_der']].sum()
        #self.df_monthly.index = self.df_monthly.index.strftime('%Y-%m')

        # calculate monthly prices (on average)
        self.df_monthly_prices_strom = self.df_prices_strom_daily.groupby(pd.PeriodIndex(self.df_prices_strom_daily.index, freq="M"))[['Arbeitspreis_daily', 'Grundpreis_daily']].mean()
        self.df_monthly_prices_gas = self.df_prices_gas_daily.groupby(pd.PeriodIndex(self.df_prices_gas_daily.index, freq="M"))[['Arbeitspreis_daily', 'Grundpreis_daily']].mean()
        self.df_monthly_prices_wasser = self.df_prices_wasser_daily.groupby(pd.PeriodIndex(self.df_prices_wasser_daily.index, freq="M"))[['Arbeitspreis_daily', 'Grundpreis_daily']].mean()

        # join dfs (via index)
        self.df_strom_final = self.df_monthly[['Strom_interp_der']].join(self.df_monthly_prices_strom)
        self.df_strom_final['Kosten'] = self.df_strom_final['Strom_interp_der'] * self.df_strom_final['Arbeitspreis_daily'] + self.df_strom_final['Grundpreis_daily']
        self.df_gas_final = self.df_monthly[['Gas_interp_der']].join(self.df_monthly_prices_gas)
        # m3 to kWh
        self.df_gas_final['Gas_interp_der'] = self.df_gas_final['Gas_interp_der'] * self.factor_m3_to_kWh
        self.df_gas_final['Kosten'] = self.df_gas_final['Gas_interp_der'] * self.df_gas_final['Arbeitspreis_daily'] + self.df_gas_final['Grundpreis_daily']
        self.df_wasser_final = self.df_monthly[['Wasser_interp_der']].join(self.df_monthly_prices_wasser)
        self.df_wasser_final['Kosten'] = self.df_wasser_final['Wasser_interp_der'] * self.df_wasser_final['Arbeitspreis_daily'] + self.df_wasser_final['Grundpreis_daily']

    def plots_and_stats(self):
        
        # create folder (if not exist)
        if not os.path.exists(self.plot_dir):
            os.makedirs(self.plot_dir)

        # get yearly stats
        years = self.df_readings['year'].unique()        
        month_index = np.arange(1, 13, dtype=np.int64)

        # verbrauch
        df_strom = pd.DataFrame(columns=years, index=month_index)
        df_gas = pd.DataFrame(columns=years, index=month_index)
        df_wasser = pd.DataFrame(columns=years, index=month_index)
        strom_legend = []
        gas_legend = []
        wasser_legend = []

        # cost
        df_strom_cost = pd.DataFrame(columns=years, index=month_index)
        df_gas_cost = pd.DataFrame(columns=years, index=month_index)
        df_wasser_cost = pd.DataFrame(columns=years, index=month_index)
        strom_cost_legend = []
        gas_cost_legend = []
        wasser_cost_legend = []

        # Strom
        for year in years:
            mask = (self.df_strom_final.index >= f'{year}-01') & (self.df_strom_final.index <= f'{year}-12')
            data_year = self.df_strom_final.loc[mask]

            # change index (remove year)
            idx_new = []
            for idx in data_year.index:
                idx_new.append(idx.month)
            data_year.index = idx_new
        
            # df
            df_strom[year] = data_year['Strom_interp_der']
            df_strom_cost[year] = data_year['Kosten']

            # legend
            strom_legend.append(f"{year} ({data_year['Strom_interp_der'].sum():.0f} kWh)")
            strom_cost_legend.append(f"{year} ({data_year['Kosten'].sum():.0f} Euro)")

        # Gas
        for year in years:
            mask = (self.df_gas_final.index >= f'{year}-01') & (self.df_gas_final.index <= f'{year}-12')
            data_year = self.df_gas_final.loc[mask]

            # change index (remove year)
            idx_new = []
            for idx in data_year.index:
                idx_new.append(idx.month)
            data_year.index = idx_new
        
            # df
            df_gas[year] = data_year['Gas_interp_der']
            df_gas_cost[year] = data_year['Kosten']

            # legend
            gas_legend.append(f"{year} ({data_year['Gas_interp_der'].sum():.0f} kWh)")
            gas_cost_legend.append(f"{year} ({data_year['Kosten'].sum():.0f} Euro)")

        # Wasser
        for year in years:
            mask = (self.df_wasser_final.index >= f'{year}-01') & (self.df_wasser_final.index <= f'{year}-12')
            data_year = self.df_wasser_final.loc[mask]

            # change index (remove year)
            idx_new = []
            for idx in data_year.index:
                idx_new.append(idx.month)
            data_year.index = idx_new
        
            # df
            df_wasser[year] = data_year['Wasser_interp_der']
            df_wasser_cost[year] = data_year['Kosten']

            # legend
            wasser_legend.append(f"{year} ({data_year['Wasser_interp_der'].sum():.0f} m3)")
            wasser_cost_legend.append(f"{year} ({data_year['Kosten'].sum():.0f} Euro)")
            
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

        # Strom Kosten
        df_strom_cost.plot.bar()
        plt.title('Kosten Strom')
        plt.xlabel('Month')
        plt.ylabel('[Euro]')
        plt.grid(axis='y')
        plt.legend(strom_cost_legend)
        plt.tight_layout()
        plt.savefig(os.path.join(self.plot_dir, 'strom_kosten.png'))
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

        # Gas Kosten
        df_gas_cost.plot.bar()
        plt.title('Kosten Gas')
        plt.xlabel('Month')
        plt.ylabel('[Euro]')
        plt.grid(axis='y')
        plt.legend(gas_cost_legend)
        plt.tight_layout()
        plt.savefig(os.path.join(self.plot_dir, 'gas_kosten.png'))
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

        # Wasser Kosten
        df_wasser_cost.plot.bar()
        plt.title('Kosten Wasser')
        plt.xlabel('Month')
        plt.ylabel('[Euro]')
        plt.grid(axis='y')
        plt.legend(wasser_cost_legend)
        plt.tight_layout()
        plt.savefig(os.path.join(self.plot_dir, 'wasser_kosten.png'))
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
