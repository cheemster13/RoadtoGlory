import streamlit as st
from yahoo_oauth import OAuth2
import requests
import urllib.parse
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px  # Import Plotly Express for advanced visualizations

# Mapping league keys to season years
league_key_to_year = {
    "359": "2016",
    "371": "2017",
    "380": "2018",
    "390": "2019",
    "399": "2020",
    "406": "2021",
    "414": "2022",
    "423": "2023"
}

# Function to authenticate with Yahoo API (cached)
@st.cache_resource
def authenticate_yahoo():
    oauth = OAuth2(None, None, from_file='yahoo_oauth.json')
    if not oauth.token_is_valid():
        oauth.refresh_access_token()
    return oauth

# Function to fetch league and standings data (cached)
@st.cache_data
def fetch_league_and_standings_data(league_key):
    oauth = authenticate_yahoo()
    encoded_league_key = urllib.parse.quote(league_key)
    
    # Fetch league data
    league_url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{encoded_league_key}"
    league_response = oauth.session.get(league_url, params={'format': 'json'})
    
    if league_response.status_code != 200:
        st.error(f"Error fetching league data: {league_response.status_code}, {league_response.text}")
        return None, None
    
    league_data = league_response.json()
    
    # Fetch standings data
    standings_url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{encoded_league_key}/standings"
    standings_response = oauth.session.get(standings_url, params={'format': 'json'})
    
    if standings_response.status_code != 200:
        st.error(f"Error fetching standings: {standings_response.status_code}, {standings_response.text}")
        return league_data, None
    
    standings_data = standings_response.json()
    return league_data, standings_data

# Function to fetch matchup data for a given week and league (cached)
@st.cache_data
def fetch_matchup_data(league_key, week):
    oauth = authenticate_yahoo()
    encoded_league_key = urllib.parse.quote(league_key)
    url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{encoded_league_key}/scoreboard;week={week}"
    response = oauth.session.get(url, params={'format': 'json'})
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error fetching matchup data for week {week}: {response.status_code}, {response.text}")
        return None

# Helper function to extract manager name
def extract_manager_name(team_data):
    try:
        team_attributes = team_data[0]
        if len(team_attributes) > 20 and 'managers' in team_attributes[20]:
            managers_info = team_attributes[20]['managers']
            if managers_info and len(managers_info) > 0:
                manager_data = managers_info[0]['manager']
                manager_name = manager_data.get('nickname', 'Unknown')
                if manager_name == '-- hidden --':  # Replace '--hidden--' with 'Vikram'
                    return 'Vikram'
                return manager_name
    except Exception as e:
        st.error(f"Error extracting manager name: {e}")
    return 'Unknown'

# Function to extract manager data
def extract_manager_data(standings_data):
    manager_info = []
    teams = standings_data['fantasy_content']['league'][1]['standings'][0]['teams']
    
    for team_key, team in teams.items():
        if team_key == 'count':
            continue  # Skip the count key

        try:
            team_list = team['team']
            team_attributes = team_list[0]
            team_name = team_attributes[2]['name']
            
            manager_name = extract_manager_name(team_list)
            
            team_standings = team_list[2]['team_standings']
            final_standing = int(team_standings['rank'])
            wins = int(team_standings['outcome_totals']['wins'])
            losses = int(team_standings['outcome_totals']['losses'])
            ties = int(team_standings['outcome_totals'].get('ties', 0))

            manager_info.append({
                'Manager': manager_name,
                'Team': team_name,
                'Final Standing': final_standing,
                'Wins': wins,
                'Losses': losses,
                'Ties': ties,
                'Season': team_list[0][0]['team_key'].split('.')[0]  # Add season for filtering later
            })
        except (KeyError, IndexError, TypeError, ValueError) as e:
            st.error(f"Error accessing data for team {team_key}: {e}")
            continue
    
    return pd.DataFrame(manager_info)

# Function to calculate head-to-head comparison using matchup data
def head_to_head_comparison(manager_1, manager_2, league_keys):
    manager_1_wins = 0
    manager_2_wins = 0
    ties = 0
    matchups_played = 0
    
    for league_key in league_keys:
        season_year = league_key_to_year[league_key.split('.')[0]]
        league_data, _ = fetch_league_and_standings_data(league_key)
        if not league_data:
            continue
        
        start_week = int(league_data['fantasy_content']['league'][0]['start_week'])
        end_week = int(league_data['fantasy_content']['league'][0]['end_week'])
        
        for week in range(start_week, end_week + 1):
            matchup_data = fetch_matchup_data(league_key, week)
            if not matchup_data:
                continue
            
            try:
                matchups = matchup_data['fantasy_content']['league'][1]['scoreboard']['0']['matchups']
                for matchup_key, matchup in matchups.items():
                    if matchup_key == 'count':
                        continue
                    teams = matchup['matchup']['0']['teams']
                    team1 = teams['0']['team']
                    team2 = teams['1']['team']
                    
                    manager1_name = extract_manager_name(team1)
                    manager2_name = extract_manager_name(team2)
                    
                    if {manager1_name, manager2_name} == {manager_1, manager_2}:
                        matchups_played += 1
                        team1_points = float(team1[1]['team_points']['total'])
                        team2_points = float(team2[1]['team_points']['total'])
                        if team1_points > team2_points:
                            winner = manager1_name
                        elif team2_points > team1_points:
                            winner = manager2_name
                        else:
                            winner = 'Tie'
                        
                        if winner == manager_1:
                            manager_1_wins += 1
                        elif winner == manager_2:
                            manager_2_wins += 1
                        else:
                            ties += 1
            except Exception as e:
                st.error(f"Error processing matchup data for week {week}, season {season_year}: {e}")
                continue
    
    return manager_1_wins, manager_2_wins, ties, matchups_played

# Function to get detailed matchup history between two managers
def get_matchup_history(manager_1, manager_2, league_keys):
    matchup_records = []
    for league_key in league_keys:
        season_year = league_key_to_year[league_key.split('.')[0]]
        league_data, _ = fetch_league_and_standings_data(league_key)
        if not league_data:
            continue
        start_week = int(league_data['fantasy_content']['league'][0]['start_week'])
        end_week = int(league_data['fantasy_content']['league'][0]['end_week'])
        for week in range(start_week, end_week + 1):
            matchup_data = fetch_matchup_data(league_key, week)
            if not matchup_data:
                continue
            try:
                matchups = matchup_data['fantasy_content']['league'][1]['scoreboard']['0']['matchups']
                for matchup_key, matchup in matchups.items():
                    if matchup_key == 'count':
                        continue
                    teams = matchup['matchup']['0']['teams']
                    team1 = teams['0']['team']
                    team2 = teams['1']['team']
                    manager1_name = extract_manager_name(team1)
                    manager2_name = extract_manager_name(team2)
                    if {manager1_name, manager2_name} == {manager_1, manager_2}:
                        team1_points = float(team1[1]['team_points']['total'])
                        team2_points = float(team2[1]['team_points']['total'])
                        if team1_points > team2_points:
                            winner = manager1_name
                        elif team2_points > team1_points:
                            winner = manager2_name
                        else:
                            winner = 'Tie'
                        matchup_records.append({
                            'Season': season_year,
                            'Week': week,
                            'Manager 1': manager1_name,
                            'Manager 2': manager2_name,
                            'Manager 1 Points': team1_points,
                            'Manager 2 Points': team2_points,
                            'Winner': winner
                        })
            except Exception as e:
                st.error(f"Error processing matchup data for week {week}, season {season_year}: {e}")
                continue
    return pd.DataFrame(matchup_records)

# Function to plot manager performance
def plot_manager_performance(manager_name, data):
    manager_data = data[data['Manager'] == manager_name]
    
    plt.figure(figsize=(10, 6))
    plt.plot(manager_data['Season'], manager_data['Final Standing'], marker='o', linestyle='-')
    plt.gca().invert_yaxis()  # Lower numbers are better in standings
    plt.title(f"Performance of {manager_name} Over the Seasons")
    plt.xlabel("Season")
    plt.ylabel("Final Standing")
    st.pyplot(plt)

# Streamlit App Title
st.title("Road to Glory - Deep Dive")

# Authenticate Yahoo API
oauth = authenticate_yahoo()
if oauth.token_is_valid():
    st.success("Yahoo API Authentication successful!")
else:
    st.error("Failed to authenticate with Yahoo API.")

# Historical league keys
league_keys = [
    "359.l.749915", "371.l.587962", "380.l.900787", "390.l.442716", 
    "399.l.821242", "406.l.418209", "414.l.195525", "423.l.347398"
]

# Collect data across seasons
historical_data = []

for league_key in league_keys:
    league_data, standings_data = fetch_league_and_standings_data(league_key)
    
    if league_data and standings_data:
        season_year = league_key_to_year[league_key.split('.')[0]]
        df = extract_manager_data(standings_data)
        df['Season'] = season_year
        historical_data.append(df)

# Combine historical data
if historical_data:
    historical_df = pd.concat(historical_data)
    
    # Replace '--hidden--' with 'Vikram'
    historical_df['Manager'] = historical_df['Manager'].replace('--hidden--', 'Vikram')
    
    st.write("Combined Historical Data:")
    
    # View 1: Manager Overview
    manager_names = historical_df['Manager'].unique()
    selected_manager = st.selectbox('Select a Manager:', manager_names)
    
    # Show total wins, losses, ties, and total games for the manager
    manager_data = historical_df[historical_df['Manager'] == selected_manager]
    total_wins = manager_data['Wins'].sum()
    total_losses = manager_data['Losses'].sum()
    total_ties = manager_data['Ties'].sum()
    total_games = total_wins + total_losses + total_ties
    
    st.markdown(f"**Total Wins:** <b>{total_wins}</b>, **Total Losses:** <b>{total_losses}</b>, **Total Ties:** <b>{total_ties}</b>, **Total Games:** <b>{total_games}</b>", unsafe_allow_html=True)
    plot_manager_performance(selected_manager, historical_df)

    # Advanced Visualization: Win-Loss-Tie Distribution per Manager
    st.header("Win-Loss-Tie Distribution per Manager")

    # Aggregate wins, losses, and ties per manager
    win_loss_df = historical_df.groupby('Manager')[['Wins', 'Losses', 'Ties']].sum().reset_index()

    # Melt the dataframe for plotting
    win_loss_melted = win_loss_df.melt(id_vars='Manager', value_vars=['Wins', 'Losses', 'Ties'], var_name='Outcome', value_name='Count')

    # Create stacked bar chart with custom colors
    fig = px.bar(
        win_loss_melted,
        x='Manager',
        y='Count',
        color='Outcome',
        title='Win-Loss-Tie Distribution per Manager',
        text='Count',
        color_discrete_map={'Wins': 'green', 'Losses': 'lightcoral', 'Ties': 'yellow'}
    )
    fig.update_layout(xaxis={'categoryorder':'total descending'})

    st.plotly_chart(fig, use_container_width=True)

    # View 2: Head-to-Head Comparison
    st.header("Head-to-Head Comparison")
    manager_1 = st.selectbox('Select Manager 1:', manager_names, key='manager1_h2h')
    manager_2 = st.selectbox('Select Manager 2:', manager_names, key='manager2_h2h')

    if manager_1 != manager_2:
        manager_1_wins, manager_2_wins, ties, matchups_played = head_to_head_comparison(manager_1, manager_2, league_keys)
        st.write(f"Total Matchups Played: {matchups_played}")
        st.write(f"Ties: {ties}")

        # Determine the winner and apply formatting
        if manager_1_wins > manager_2_wins:
            manager_1_display = f"<b>{manager_1} Wins: {manager_1_wins}</b> 🥇"
            manager_2_display = f"<b>{manager_2} Wins: {manager_2_wins}</b> 🥈"
        elif manager_2_wins > manager_1_wins:
            manager_1_display = f"<b>{manager_1} Wins: {manager_1_wins}</b> 🥈"
            manager_2_display = f"<b>{manager_2} Wins: {manager_2_wins}</b> 🥇"
        else:
            # If tied, both are gold
            manager_1_display = f"<b>{manager_1} Wins: {manager_1_wins}</b> 🥇"
            manager_2_display = f"<b>{manager_2} Wins: {manager_2_wins}</b> 🥇"

        # Display the formatted result
        st.markdown(manager_1_display, unsafe_allow_html=True)
        st.markdown(manager_2_display, unsafe_allow_html=True)

        # Detailed Head-to-Head Matchup History
        matchup_history_df = get_matchup_history(manager_1, manager_2, league_keys)
        if not matchup_history_df.empty:
            st.subheader("Detailed Head-to-Head Matchup History")
            # Sort by Season and Week
            matchup_history_df = matchup_history_df.sort_values(['Season', 'Week'])
            # Reset index and display the table without the index column
            st.dataframe(matchup_history_df.reset_index(drop=True), use_container_width=True)
        else:
            st.write("No matchup history available between these managers.")
    else:
        st.warning("Please select two different managers for head-to-head comparison.")

    # View 3: Season Standings
    selected_season = st.selectbox('Select a Season:', sorted(historical_df['Season'].unique()), key='season_select')
    season_data = historical_df[historical_df['Season'] == selected_season]

    # Adding medals and poop emoji based on Final Standing
    season_data = season_data.sort_values('Final Standing')
    num_teams = len(season_data)
    season_data['Medal'] = ''
    season_data.loc[season_data['Final Standing'] == 1, 'Medal'] = '🥇'
    season_data.loc[season_data['Final Standing'] == 2, 'Medal'] = '🥈'
    season_data.loc[season_data['Final Standing'] == 3, 'Medal'] = '🥉'
    season_data.loc[season_data['Final Standing'] == num_teams, 'Medal'] = '💩'

    # Remove the index column and display the standings table
    st.write(f"Standings for Season {selected_season}")
    st.dataframe(season_data[['Medal', 'Manager', 'Team', 'Final Standing', 'Wins', 'Losses', 'Ties']].reset_index(drop=True), use_container_width=True)

    # Additional Statistics
    st.header("Additional Statistics")

    # Championships Won per Manager
    st.subheader("Championships Won per Manager")
    championships_df = historical_df[historical_df['Final Standing'] == 1].groupby('Manager').size().reset_index(name='Championships')
    championships_df = championships_df.sort_values(by='Championships', ascending=False).reset_index(drop=True)

    # Highlighting the top rows (gold, silver, bronze)
    def highlight_top_rows(row):
        if row.name == 0:
            return ['font-weight: bold; color: gold'] * len(row)
        elif row.name == 1:
            return ['font-weight: bold; color: silver'] * len(row)
        elif row.name == 2:
            return ['font-weight: bold; color: brown'] * len(row)
        else:
            return [''] * len(row)

    st.dataframe(championships_df.style.apply(highlight_top_rows, axis=1), use_container_width=True)

    # Average Final Standing per Manager
    st.subheader("Average Final Standing per Manager")
    avg_standing_df = historical_df.groupby('Manager')['Final Standing'].mean().reset_index()
    avg_standing_df = avg_standing_df.sort_values(by='Final Standing', ascending=True).reset_index(drop=True)

    # Highlighting top rows for Average Final Standing
    st.dataframe(avg_standing_df.style.apply(highlight_top_rows, axis=1), use_container_width=True)

    # Top 3 Finishes per Manager
    st.subheader("Top 3 Finishes per Manager")
    top_3_df = historical_df[historical_df['Final Standing'] <= 3].groupby('Manager').size().reset_index(name='Top 3 Finishes')
    top_3_df = top_3_df.sort_values(by='Top 3 Finishes', ascending=False).reset_index(drop=True)

    # Highlighting top rows for Top 3 Finishes
    st.dataframe(top_3_df.style.apply(highlight_top_rows, axis=1), use_container_width=True)

    # Overall Win Percentage per Manager
    st.subheader("Overall Win Percentage per Manager")
    historical_df['Total Games'] = historical_df['Wins'] + historical_df['Losses'] + historical_df['Ties']
    historical_df['Win Percentage'] = historical_df['Wins'] / historical_df['Total Games']
    win_percentage_df = historical_df.groupby('Manager')['Win Percentage'].mean().reset_index()
    win_percentage_df = win_percentage_df.sort_values(by='Win Percentage', ascending=False).reset_index(drop=True)

    win_percentage_df['Win Percentage'] = win_percentage_df['Win Percentage'].apply(lambda x: f"{x:.2%}")

    # Highlighting top rows for Win Percentage
    st.dataframe(win_percentage_df.style.apply(highlight_top_rows, axis=1), use_container_width=True)

else:
    st.error("No historical data available.")
