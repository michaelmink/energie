# auth.py
from __future__ import print_function
from googleapiclient.discovery import build 
from google.oauth2 import service_account
import os
import pandas as pd
import matplotlib.pyplot as plt


SCOPES = [
'https://www.googleapis.com/auth/spreadsheets'
]
creds_file = os.path.join('.', 'energie', 'credentials.json')

credentials = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
spreadsheet_service = build('sheets', 'v4', credentials=credentials)


SAMPLE_SPREADSHEET_ID = '1AUd0lPyr_g6Ml3odYm1fr6nvLRcw8uPiSeZHxuT0N9E'
SAMPLE_RANGE_NAME = 'A1:D100'

# Call the Sheets API
sheet = spreadsheet_service.spreadsheets()
result_input = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                            range=SAMPLE_RANGE_NAME).execute()
values_input = result_input.get('values', [])

# read as df
df=pd.DataFrame(values_input[1:], columns=values_input[0])

# parameters
search_year = '2022'
factor_m3_to_kWh = 12

# add columns
df[['day', 'month', 'year']] = df['Datum'].str.split('.', 2, expand=True)

# slice to years
data = df[df['year'] == search_year]

# get yearly stats
print(f'Consumption for {search_year}:')
print(f" Gas: {(float(data['Gas'].iloc[-1]) - float(data['Gas'].iloc[0])) * factor_m3_to_kWh:.1f} kWh")
print(f"  from {data['Datum'].iloc[0]} to {data['Datum'].iloc[-1]}")

# convert to datetime
data['datetime'] = pd.to_datetime(data[['year', 'month', 'day']])

# change index
data.index = data['datetime']

# resample to daily steps
df_interpol = data[['Strom', 'Wasser', 'Gas']].resample('D').mean()

# interpolate data
df_interpol[['Strom_interp', 'Wasser_interp', 'Gas_interp']] = df_interpol[['Strom', 'Wasser', 'Gas']].interpolate()

# first derivation to get daily consumption
df_interpol[['Strom_interp_der', 'Wasser_interp_der', 'Gas_interp_der']] = df_interpol[['Strom_interp', 'Wasser_interp', 'Gas_interp']].diff()

# monthly comsumption (on average)
df_monthly = df_interpol.groupby(pd.PeriodIndex(df_interpol.index, freq="M"))[['Strom_interp_der', 'Wasser_interp_der', 'Gas_interp_der']].sum()
df_monthly.index = df_monthly.index.strftime('%Y-%m')

# plots

# absolute
plt.plot(df_interpol['Strom_interp'], '-')
plt.plot(df_interpol['Strom'], '+')
plt.savefig('strom.png')
plt.clf()

# relative
plt.plot(df_interpol['Strom_interp_der'], '-')
plt.savefig('strom_rel.png')
plt.clf()

# monthly
df_monthly['Strom_interp_der'].plot(kind='bar')
plt.title('Verbrauch Strom 2022')
plt.xlabel('Month')
plt.ylabel('kWh')
plt.tight_layout()
plt.savefig('strom_monthly.png')
plt.clf()

df_monthly['Wasser_interp_der'].plot(kind='bar')
plt.title('Verbrauch Wasser 2022')
plt.xlabel('Month')
plt.ylabel('m3')
plt.tight_layout()
plt.savefig('wasser_monthly.png')
plt.clf()

df_monthly['Gas_interp_der'].plot(kind='bar')
plt.title('Verbrauch Gas 2022')
plt.xlabel('Month')
plt.ylabel('kWh')
plt.tight_layout()
plt.savefig('gas_monthly.png')
plt.clf()







