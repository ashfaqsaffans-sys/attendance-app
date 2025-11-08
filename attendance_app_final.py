import streamlit as st
import pandas as pd
from datetime import datetime, time
from io import BytesIO

SHOWROOM_SHIFT = (time(10, 0), time(20, 30))
OFFICE_SHIFT = (time(10, 0), time(18, 0))

st.title("📋 Detailed Attendance Tracker with Friday Rule")

uploaded_file = st.file_uploader("Upload Fingerprint Excel File", type=["xlsx"])
dept_file = st.file_uploader("Optional: Upload Branch/Department Mapping (Name, Branch/Dept)", type=["csv", "xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df['Date'] = pd.to_datetime(df['Date'])

    all_employees = sorted(df['Name'].unique())
    office_staff_selected = st.multiselect("Select Office Staff", options=all_employees)

    branch_map = {}
    if dept_file:
        dept_df = pd.read_excel(dept_file) if dept_file.name.endswith('xlsx') else pd.read_csv(dept_file)
        branch_map = dict(zip(dept_df['Name'], dept_df['Branch/Dept']))

    all_dates = pd.date_range(start=df['Date'].min(), end=df['Date'].max(), freq='D')

    summary = []
    daily_records = []

    for emp_name in all_employees:
        group = df[df['Name'] == emp_name].copy()
        group.set_index('Date', inplace=True)

        is_office_staff = emp_name.strip() in office_staff_selected
        shift_start, shift_end = OFFICE_SHIFT if is_office_staff else SHOWROOM_SHIFT

        all_present_dates = set(group.index.date)

        late_entries = 0
        food_cut_days = 0
        half_days = 0
        present_days = 0
        absent_days = 0
        missing_records = 0
        jummah_violations = 0

        for date in all_dates:
            date_only = date.date()
            weekday = date.strftime('%A')
            status = "Absent"
            in_time_str = ""
            out_time_str = ""
            jummah_ok = ""

            row = group.loc[group.index.date == date_only]
            if row.empty:
                absent_days += 1
                daily_records.append({
                    'Employee Name': emp_name,
                    'Date': date_only,
                    'Weekday': weekday,
                    'Branch/Dept': branch_map.get(emp_name, "Unknown"),
                    'In Time': "",
                    'Out Time': "",
                    'Status': "Absent",
                    'Jummah Break OK': ""
                })
                continue

            row = row.iloc[0]
            present_days += 1
            is_friday = weekday == 'Friday'

            try:
                in_time = datetime.strptime(str(row['1']), "%H:%M:%S").time()
                in_time_str = in_time.strftime("%H:%M:%S")
            except:
                in_time = None

            if is_friday:
                try:
                    break_start = datetime.strptime(str(row['2']), "%H:%M:%S").time()
                    break_end = datetime.strptime(str(row['3']), "%H:%M:%S").time()
                    out_time = datetime.strptime(str(row['4']), "%H:%M:%S").time()
                    out_time_str = out_time.strftime("%H:%M:%S")

                    # Calculate break duration in minutes
                    break_start_dt = datetime.combine(date_only, break_start)
                    break_end_dt = datetime.combine(date_only, break_end)
                    break_duration = (break_end_dt - break_start_dt).total_seconds() / 60.0
                    duration_minutes = int(round(break_duration))

                    break_time_range = f"{break_start.strftime('%H:%M')} – {break_end.strftime('%H:%M')}"

                    if break_duration <= 63:
                        jummah_ok = f"✅ ({break_time_range}) | {duration_minutes} min"
                    else:
                        jummah_ok = f"❌ ({break_time_range}) | {duration_minutes} min"
                        jummah_violations += 1
                except:
                    out_time = None
                    jummah_ok = "❌ (Invalid break data)"
                    jummah_violations += 1
            else:
                try:
                    out_time = datetime.strptime(str(row['2']), "%H:%M:%S").time()
                    out_time_str = out_time.strftime("%H:%M:%S")
                except:
                    out_time = None

            # Attendance status logic with half day for late in or early out
            if not in_time or not out_time:
                missing_records += 1
                status = "Missing Record"
            else:
                half_day_flag = False
                early_out_flag = False

                # Late clock-in check
                if in_time > time(10, 10, 0):
                    half_day_flag = True
                    late_entries += 1

                # Early clock-out check
                if out_time < shift_end:
                    early_out_flag = True
                    half_day_flag = True  # Half Day but no late entry count here

                if half_day_flag:
                    if early_out_flag and in_time <= time(10, 10, 0):
                        # Early out only, no late entry count
                        status = "Half Day (Early Out)"
                        half_days += 1
                    else:
                        # Late clock-in or both late in and early out
                        status = "Half Day"
                        half_days += 1
                elif in_time <= time(9, 59, 59):
                    status = "On Time"
                elif in_time <= time(10, 10, 0):
                    status = "Late – Food Cut"
                    food_cut_days += 1
                    late_entries += 1
                else:
                    # fallback safety
                    status = "Half Day"
                    half_days += 1
                    late_entries += 1

            daily_records.append({
                'Employee Name': emp_name,
                'Date': date_only,
                'Weekday': weekday,
                'Branch/Dept': branch_map.get(emp_name, "Unknown"),
                'In Time': in_time_str,
                'Out Time': out_time_str,
                'Status': status,
                'Jummah Break OK': jummah_ok
            })

        summary.append({
            'Employee Name': emp_name,
            'Branch/Dept': branch_map.get(emp_name, "Unknown"),
            'Days Present': present_days,
            'Days Absent': absent_days,
            'Late Entries': late_entries,
            'Food Cut Days': food_cut_days,
            'Half Days': half_days,
            'Jummah Missed': jummah_violations,
            'Missing Records': missing_records
        })

    summary_df = pd.DataFrame(summary)
    detail_df = pd.DataFrame(daily_records)

    st.subheader("📊 Attendance Summary")
    st.dataframe(summary_df)

    st.subheader("📅 Detailed Daily Records")
    st.dataframe(detail_df)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Summary")
        detail_df.to_excel(writer, index=False, sheet_name="Daily Detail")
    output.seek(0)

    st.download_button(
        label="📥 Download Excel Report",
        data=output,
        file_name="attendance_detailed_jummah_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
