import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION ---
SHEET_NAME = "RideBookings"  # Name of your Google Sheet
GOOGLE_SHEETS_CREDENTIALS_FILE = "credentials.json"  # Your uploaded credentials file
ADMIN_PASSWORD = "pasword"  # Same as before

@st.cache_resource
def connect_to_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    #st.write(st.secrets["gcp_service_account"])  # ← TEMPORARY for debugging
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    st.write("✅ Connected to Google Sheets!")
    sheet = client.open(SHEET_NAME).sheet1
    return sheet

sheet = connect_to_sheet()

# --- FUNCTIONS TO HANDLE SHEET DATA ---
def load_data():
    records = sheet.get_all_records()
    st.write("🔍 Loaded records:", records)
    df = pd.DataFrame(records)
    if df.empty:
        st.write("⚠️ No rides found in sheet!")
        return pd.DataFrame(columns=["Name", "Date", "Time", "Pickup", "Dropoff"])
    return df


def save_new_ride(ride_data):
    sheet.append_row(list(ride_data.values()))

def overwrite_sheet(df):
    sheet.clear()
    sheet.append_row(["Name", "Date", "Time", "Pickup", "Dropoff"])
    for index, row in df.iterrows():
        sheet.append_row(row.tolist())

def delete_expired_rides(df):
    now = datetime.now()
    keep_rows = []
    for i, ride in df.iterrows():
        ride_datetime = datetime.strptime(f"{ride['Date']} {ride['Time']}", "%Y-%m-%d %I:%M %p")
        if now < ride_datetime:
            keep_rows.append(i)
    if len(keep_rows) < len(df):
        df = df.loc[keep_rows].reset_index(drop=True)
        overwrite_sheet(df)
    return df

def highlight_overdue(df):
    now = datetime.now()
    def style_row(row):
        ride_datetime = datetime.strptime(f"{row['Date']} {row['Time']}", "%Y-%m-%d %I:%M %p")
        if now > ride_datetime:
            return ['background-color: #ffcccc'] * len(row)
        return [''] * len(row)
    return df.style.apply(style_row, axis=1)

# --- STREAMLIT APP ---

st.title("Ride Booking App 🚗")

# Sidebar
page = st.sidebar.selectbox("Select Page", ["Book a Ride", "Admin Panel"])

if page == "Book a Ride":
    st.write("Book your ride below:")
    
    with st.form(key="ride_form"):
        name = st.text_input("Your Name")
        date = st.date_input("Ride Date", min_value=datetime.now().date())
        
        col1, col2, col3 = st.columns(3)
        with col1:
            hour = st.number_input("Hour (1-12)", min_value=1, max_value=12, step=1, value=11)
        with col2:
            minute = st.number_input("Minute (0-59)", min_value=0, max_value=59, step=1, value=0)
        with col3:
            period = st.selectbox("AM/PM", ["AM", "PM"])
        
        pickup = st.text_input("Pickup Location")
        dropoff = st.text_input("Drop-off Location")
        submit_button = st.form_submit_button(label="Book Ride")

    if submit_button:
        time_str = f"{hour}:{minute:02d} {period}"
        ride_data = {
            "Name": name,
            "Date": date.strftime("%Y-%m-%d"),
            "Time": time_str,
            "Pickup": pickup,
            "Dropoff": dropoff
        }
        save_new_ride(ride_data)
        st.success(f"Ride booked for {name} on {date} at {time_str}!")

    # Show Booked Rides
    st.subheader("Booked Rides")
    df = load_data()
    if not df.empty:
        df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format="%Y-%m-%d %I:%M %p")
        df = df.sort_values('DateTime').drop(columns=['DateTime']).reset_index(drop=True)
        st.table(df)
    else:
        st.write("No rides booked yet.")

elif page == "Admin Panel":
    password = st.text_input("Enter Admin Password", type="password")
    if password == ADMIN_PASSWORD:
        st.success("Access granted!")

        df = load_data()
        df = delete_expired_rides(df)
        
        if not df.empty:
            df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format="%Y-%m-%d %I:%M %p")
            df = df.sort_values('DateTime').drop(columns=['DateTime']).reset_index(drop=True)
            overwrite_sheet(df)

        st.subheader("Admin: Booked Rides")
        if not df.empty:
            st.write("Active rides below (expired rides removed):")
            styled_df = highlight_overdue(df)
            st.dataframe(styled_df)

            st.write("Delete a specific ride:")
            ride_to_delete = st.selectbox("Select Ride to Delete", df.index, format_func=lambda x: f"{df.loc[x, 'Name']} - {df.loc[x, 'Date']} {df.loc[x, 'Time']}")
            if st.button("Delete Selected Ride"):
                df = df.drop(ride_to_delete).reset_index(drop=True)
                overwrite_sheet(df)
                st.success("Ride deleted!")
                st.rerun()
        else:
            st.write("No active rides booked.")
    else:
        if password:
            st.error("Incorrect password. Access denied.")
