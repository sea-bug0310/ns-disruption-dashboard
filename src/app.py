import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px

# 1. Page Configuration
st.set_page_config(page_title="NS Train Disruptions Dashboard", layout="wide")
st.title("🇳🇱 NS Train Disruptions Dashboard")
st.markdown("Real-time insights into Dutch railway disruptions fetched from Supabase.")

# 2. Initialize Supabase Connection
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("Could not connect to Supabase. Please check your Streamlit secrets!")
    st.stop()

# 3. Load Data from Supabase
@st.cache_data(ttl=300)
def load_data():
    response = supabase.table("disruptions").select("*").execute()
    df = pd.DataFrame(response.data)
    
    if df.empty:
        return df
        
    # --- Data Processing ---
    df['start_time'] = pd.to_datetime(df['start_time'], errors='coerce')
    df['calculated_end'] = pd.to_datetime(df['end_time'], errors='coerce')
    if 'expected_duration_end_time' in df.columns:
        df['calculated_end'] = df['calculated_end'].fillna(pd.to_datetime(df['expected_duration_end_time'], errors='coerce'))
    
    df['duration_minutes'] = (df['calculated_end'] - df['start_time']).dt.total_seconds() / 60.0
    df['duration_minutes'] = df['duration_minutes'].apply(lambda x: max(x, 0) if pd.notnull(x) else 0)
    df['affected_km'] = pd.to_numeric(df['affected_km'], errors='coerce').fillna(0)
    df['weighted_impact'] = df['duration_minutes'] * df['affected_km']
    
    # --- Time Feature Extractions ---
    df = df[df['start_time'].notna()].copy()
    df['Year'] = df['start_time'].dt.year
    df['Month'] = df['start_time'].dt.strftime('%B') 
    df['Year_Month'] = df['start_time'].dt.strftime('%Y-%m') 
    
    # New: Extract Year-Week string format (e.g., '2026-W25')
    df['Year_Week'] = df['start_time'].dt.strftime('%G-W%V') 
    
    return df

with st.spinner("Fetching data from Supabase..."):
    df_raw = load_data()

if df_raw.empty:
    st.warning("No data found in your Supabase 'disruptions' table.")
    st.stop()

# 4. Sidebar Filters
st.sidebar.header("🎯 Filter Options")

# Year Multi-select Filter
available_years = sorted(df_raw['Year'].unique(), reverse=True)
selected_year = st.sidebar.selectbox("Select Year", options=available_years, index=0)

# Month Multi-select Filter
month_order = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
available_months = [m for m in month_order if m in df_raw['Month'].unique()]
selected_months = st.sidebar.multiselect("Select Month(s)", options=available_months, default=available_months)

# New: Disruption Type Multi-select Filter
if 'disruption_type' in df_raw.columns:
    available_types = sorted(df_raw['disruption_type'].dropna().unique())
    selected_types = st.sidebar.multiselect("Select Disruption Type(s)", options=available_types, default=available_types)
else:
    selected_types = []

# Scope Filter (Local vs National/International)
if 'local' in df_raw.columns:
    scope_options = ["All", "Local", "National / International"]
    selected_scope = st.sidebar.radio("Disruption Scope", options=scope_options, index=0)
else:
    selected_scope = "All"

# Apply All Filters Dynamically
df = df_raw[
    (df_raw['Year'] == selected_year) & 
    (df_raw['Month'].isin(selected_months))
]
if 'disruption_type' in df.columns and selected_types:
    df = df[df['disruption_type'].isin(selected_types)]

# Fallback block
if df.empty:
    st.warning("No data matches the selected filter combinations.")
    st.stop()


# 5. KPI Metrics Row
st.header("Key Performance Indicators")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="Total Disruptions", value=f"{len(df):,}")

with col2:
    avg_duration = df[df['duration_minutes'] > 0]['duration_minutes'].mean()
    avg_duration_val = f"{avg_duration:.1f} mins" if pd.notnull(avg_duration) else "0.0 mins"
    st.metric(label="Avg Duration", value=avg_duration_val)

with col3:
    st.metric(label="Total Impact (Mins × Km)", value=f"{df['weighted_impact'].sum():,.0f}")

with col4:
    active_count = df[df['is_active'] == True].shape[0] if 'is_active' in df.columns else 0
    st.metric(label="Active Disruptions", value=active_count)

st.markdown("---")


# 6. Interactive Time Series Breakdown with View Switching Buttons
st.header("📈 Time Series Breakdowns")

view_option = st.radio("Select View", options=["By Month-Year", "By Week-Year"], horizontal=True)

if view_option == "By Month-Year":
    trend_data = df.groupby(['Year_Month']).size().reset_index(name='Disruption Count').sort_values('Year_Month')
    x_col = 'Year_Month'
    x_label = 'Timeline (Year-Month)'
else:
    trend_data = df.groupby(['Year_Week']).size().reset_index(name='Disruption Count').sort_values('Year_Week')
    x_col = 'Year_Week'
    x_label = 'Timeline (Year-Week)'

fig_trend = px.bar(
    trend_data, 
    x=x_col, 
    y='Disruption Count',
    title="Disruptions Count Trend",
    labels={x_col: x_label, 'Disruption Count': 'Number of Incidents'},
    color='Disruption Count',
    color_continuous_scale=px.colors.sequential.Blues[3:]
)

fig_trend.update_layout(xaxis_type='category')
st.plotly_chart(fig_trend, use_container_width=True)

# TEMPORARILY REMOVE

# # 6. Interactive Time Series Breakdown with View Switching Buttons
# st.header("📈 Time Trends")

# # Prepare Month Data aggregation
# trend_month = df.groupby(['Year_Month']).size().reset_index(name='Disruption Count').sort_values('Year_Month')

# # Prepare Week Data aggregation
# trend_week = df.groupby(['Year_Week']).size().reset_index(name='Disruption Count').sort_values('Year_Week')

# # Base figure defaults to Month-Year view
# fig_trend = px.bar(
#     trend_month, 
#     x='Year_Month', 
#     y='Disruption Count',
#     title="Disruptions Count Trend",
#     labels={'Year_Month': 'Timeline', 'Disruption Count': 'Number of Incidents'},
#     color='Disruption Count',
#     color_continuous_scale=px.colors.sequential.Blues[3:]
# )
# fig_trend.update_layout(xaxis_type='category')

# # Add Interactive View-switching Buttons inside Plotly
# fig_trend.update_layout(
#     updatemenus=[
#         dict(
#             type="buttons",
#             direction="right",
#             active=0,
#             x=0.01,
#             y=1.15,
#             buttons=list([
#                 dict(
#                     label="By Month-Year",
#                     method="update",
#                     args=[
#                         {"x": [trend_month['Year_Month']], "y": [trend_month['Disruption Count']], "marker.color": [trend_month['Disruption Count']]},
#                         {"xaxis.title.text": "Timeline (Year-Month)"}
#                     ]
#                 ),
#                 dict(
#                     label="By Week-Year",
#                     method="update",
#                     args=[
#                         {"x": [trend_week['Year_Week']], "y": [trend_week['Disruption Count']], "marker.color": [trend_week['Disruption Count']]},
#                         {"xaxis.title.text": "Timeline (Year-Week)"}
#                     ]
#                 )
#             ]),
#         )
#     ]
# )

# st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("---")


# 7. Categorical Visualizations Row
st.header("Disruption Breakdowns")
left_chart_col, right_chart_col = st.columns(2)

with left_chart_col:
    st.subheader("Breakdown by Disruption Type")
    if 'disruption_type' in df.columns:
        type_counts = df['disruption_type'].value_counts().reset_index()
        type_counts.columns = ['disruption_type', 'count']
        fig_type = px.pie(type_counts, values='count', names='disruption_type', 
                          hole=0.4, color_discrete_sequence=px.colors.sequential.YlOrRd_r)
        st.plotly_chart(fig_type, use_container_width=True)

with right_chart_col:
    st.subheader("Breakdown by Cause")
    if 'cause_label' in df.columns:
        clean_cause_df = df[df['cause_label'].notna() & (df['cause_label'] != "")]
        cause_counts = clean_cause_df['cause_label'].value_counts().reset_index()
        cause_counts.columns = ['cause_label', 'count']
        fig_cause = px.bar(cause_counts.head(10), x='count', y='cause_label', 
                           orientation='h', color='count',
                           color_continuous_scale=px.colors.sequential.Viridis)
        fig_cause.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_cause, use_container_width=True)

# 8. Detailed Data View
st.markdown("---")
with st.expander("🔍 View Live Ingested Records"):
    preview_cols = ['id', 'title', 'disruption_type', 'Year_Month', 'Year_Week', 'is_active', 'from_station', 'to_station', 'affected_km', 'cause_label']
    available_cols = [col for col in preview_cols if col in df.columns]
    st.dataframe(df[available_cols].sort_values(by='Year_Month', ascending=False))