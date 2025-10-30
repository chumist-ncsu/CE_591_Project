import pandas as pd
import matplotlib.pyplot as plt

# Load RTM data from Excel files
rtm_months = pd.read_excel("rtm_2024.xlsx", sheet_name=None)
rtm_jan_2025 = pd.read_excel("rtm_2025.xlsx", sheet_name="Jan")

# Combine monthly data into a single DataFrame
rtm_full = pd.DataFrame([], columns=rtm_months["Jan"].columns)

for month in rtm_months:
    rtm_full = pd.concat([rtm_full, rtm_months[month]], ignore_index=True)    

rtm_full = pd.concat([rtm_full, rtm_jan_2025], ignore_index=True)

# Create a datetime column for accurate time representation
rtm_full["Delivery Hour"] = rtm_full["Delivery Hour"] - 1
rtm_full["Time"] = pd.to_datetime(
    rtm_full["Delivery Date"] 
    + " " 
    + rtm_full["Delivery Hour"].astype(str) 
    + ":" 
    + ((rtm_full["Delivery Interval"] - 1) * 15).astype(str)
) \
    + pd.to_timedelta("15min")


# Filter for Houston LZ Jan 1 2024 to Jan 2 2025
rtm_full = rtm_full[
    (rtm_full["Settlement Point Name"] == "LZ_HOUSTON") &
    (rtm_full["Settlement Point Type"] == "LZ") & 
    (rtm_full["Time"] <= "2025-01-02 00:00:00")
]

# Subset Time and Settlement Point Price columns
rtm = rtm_full[["Time", "Settlement Point Price"]]

# Save to CSV
rtm.to_csv("rtm_2024.csv", index=False)