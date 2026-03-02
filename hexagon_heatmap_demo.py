"""
Hexagonal Heatmap Demo using H3 and Plotly
Based on: https://towardsdatascience.com/constructing-hexagon-maps-with-h3-and-plotly-a-comprehensive-tutorial-8f37a91573bb

This creates a hexagonal heatmap visualization of postcode data using Uber's H3 library.
Run on port 8051 to test separately from the main app.

Advantages of hexagonal maps over traditional choropleth:
- Balanced geometry for better regional comparisons
- Improved territorial coverage
- Minimizes visual bias (equal representation of areas)
- Uniform shape and size eliminates irregular administrative boundary distortion
"""

import pandas as pd
import numpy as np
import os
import h3
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, callback
import geopandas as gpd
from shapely.geometry import Polygon
from scipy import stats as scipy_stats

# ============================================
# SAMPLE UK POSTCODE DATA (Test Dataset)
# ============================================
# Sample postcodes with lat/lng and simulated IMD scores
# Covers areas around England, Scotland, Wales, and Northern Ireland

SAMPLE_POSTCODE_DATA = [
    # London area
    {"postcode": "SW1A 1AA", "lat": 51.5014, "lon": -0.1419, "imd_decile": 7, "region": "England", "users": 15},
    {"postcode": "EC1A 1BB", "lat": 51.5188, "lon": -0.1000, "imd_decile": 5, "region": "England", "users": 8},
    {"postcode": "W1A 1AB", "lat": 51.5182, "lon": -0.1414, "imd_decile": 8, "region": "England", "users": 12},
    {"postcode": "E1 6AN", "lat": 51.5173, "lon": -0.0558, "imd_decile": 2, "region": "England", "users": 25},
    {"postcode": "E14 5AB", "lat": 51.5052, "lon": -0.0285, "imd_decile": 3, "region": "England", "users": 18},
    {"postcode": "SE1 9SG", "lat": 51.5044, "lon": -0.0864, "imd_decile": 4, "region": "England", "users": 22},
    {"postcode": "N1 9GU", "lat": 51.5362, "lon": -0.1033, "imd_decile": 5, "region": "England", "users": 14},
    {"postcode": "NW1 4NP", "lat": 51.5234, "lon": -0.1427, "imd_decile": 6, "region": "England", "users": 9},
    {"postcode": "SW3 1EW", "lat": 51.4894, "lon": -0.1622, "imd_decile": 9, "region": "England", "users": 7},
    {"postcode": "W2 1RH", "lat": 51.5152, "lon": -0.1819, "imd_decile": 7, "region": "England", "users": 11},
    
    # Birmingham area
    {"postcode": "B1 1RS", "lat": 52.4797, "lon": -1.9026, "imd_decile": 3, "region": "England", "users": 20},
    {"postcode": "B4 6AH", "lat": 52.4815, "lon": -1.8949, "imd_decile": 4, "region": "England", "users": 16},
    {"postcode": "B5 4BU", "lat": 52.4734, "lon": -1.8967, "imd_decile": 2, "region": "England", "users": 28},
    {"postcode": "B15 2TT", "lat": 52.4539, "lon": -1.9259, "imd_decile": 5, "region": "England", "users": 13},
    {"postcode": "B29 6BD", "lat": 52.4384, "lon": -1.9413, "imd_decile": 4, "region": "England", "users": 17},
    
    # Manchester area
    {"postcode": "M1 1AE", "lat": 53.4808, "lon": -2.2426, "imd_decile": 3, "region": "England", "users": 22},
    {"postcode": "M2 4WU", "lat": 53.4819, "lon": -2.2458, "imd_decile": 4, "region": "England", "users": 19},
    {"postcode": "M3 4FP", "lat": 53.4856, "lon": -2.2537, "imd_decile": 5, "region": "England", "users": 15},
    {"postcode": "M4 5BD", "lat": 53.4864, "lon": -2.2324, "imd_decile": 2, "region": "England", "users": 30},
    {"postcode": "M14 5SX", "lat": 53.4512, "lon": -2.2207, "imd_decile": 3, "region": "England", "users": 24},
    
    # Liverpool area
    {"postcode": "L1 1JF", "lat": 53.4065, "lon": -2.9880, "imd_decile": 2, "region": "England", "users": 26},
    {"postcode": "L2 2LW", "lat": 53.4067, "lon": -2.9883, "imd_decile": 3, "region": "England", "users": 21},
    {"postcode": "L8 5TH", "lat": 53.3896, "lon": -2.9616, "imd_decile": 1, "region": "England", "users": 35},
    {"postcode": "L15 4LP", "lat": 53.4012, "lon": -2.9106, "imd_decile": 4, "region": "England", "users": 18},
    
    # Leeds area
    {"postcode": "LS1 1UR", "lat": 53.7968, "lon": -1.5453, "imd_decile": 4, "region": "England", "users": 16},
    {"postcode": "LS2 9HD", "lat": 53.8018, "lon": -1.5537, "imd_decile": 5, "region": "England", "users": 14},
    {"postcode": "LS11 9PX", "lat": 53.7809, "lon": -1.5547, "imd_decile": 2, "region": "England", "users": 27},
    
    # Sheffield
    {"postcode": "S1 2GU", "lat": 53.3811, "lon": -1.4701, "imd_decile": 3, "region": "England", "users": 19},
    {"postcode": "S10 2TN", "lat": 53.3817, "lon": -1.5011, "imd_decile": 6, "region": "England", "users": 12},
    
    # Newcastle
    {"postcode": "NE1 7RU", "lat": 54.9738, "lon": -1.6132, "imd_decile": 4, "region": "England", "users": 17},
    {"postcode": "NE6 2PA", "lat": 54.9809, "lon": -1.5689, "imd_decile": 2, "region": "England", "users": 23},
    
    # Bristol
    {"postcode": "BS1 5TR", "lat": 51.4545, "lon": -2.5879, "imd_decile": 5, "region": "England", "users": 13},
    {"postcode": "BS8 1TH", "lat": 51.4584, "lon": -2.6142, "imd_decile": 8, "region": "England", "users": 8},
    
    # Scotland - Edinburgh
    {"postcode": "EH1 1QS", "lat": 55.9486, "lon": -3.2008, "imd_decile": 6, "region": "Scotland", "users": 14},
    {"postcode": "EH7 5HG", "lat": 55.9581, "lon": -3.1638, "imd_decile": 3, "region": "Scotland", "users": 21},
    {"postcode": "EH8 9AG", "lat": 55.9445, "lon": -3.1795, "imd_decile": 5, "region": "Scotland", "users": 16},
    
    # Scotland - Glasgow
    {"postcode": "G1 1DN", "lat": 55.8609, "lon": -4.2514, "imd_decile": 2, "region": "Scotland", "users": 28},
    {"postcode": "G4 0TQ", "lat": 55.8689, "lon": -4.2478, "imd_decile": 1, "region": "Scotland", "users": 33},
    {"postcode": "G12 8QQ", "lat": 55.8740, "lon": -4.2925, "imd_decile": 7, "region": "Scotland", "users": 10},
    {"postcode": "G42 8HA", "lat": 55.8402, "lon": -4.2580, "imd_decile": 3, "region": "Scotland", "users": 24},
    
    # Wales - Cardiff
    {"postcode": "CF10 1EP", "lat": 51.4816, "lon": -3.1791, "imd_decile": 5, "region": "Wales", "users": 15},
    {"postcode": "CF24 0ED", "lat": 51.4892, "lon": -3.1620, "imd_decile": 3, "region": "Wales", "users": 20},
    {"postcode": "CF11 9JR", "lat": 51.4700, "lon": -3.2000, "imd_decile": 4, "region": "Wales", "users": 18},
    
    # Wales - Swansea
    {"postcode": "SA1 3QJ", "lat": 51.6195, "lon": -3.9436, "imd_decile": 4, "region": "Wales", "users": 16},
    {"postcode": "SA4 3RR", "lat": 51.6551, "lon": -4.0282, "imd_decile": 3, "region": "Wales", "users": 19},
    
    # Northern Ireland - Belfast
    {"postcode": "BT1 1HB", "lat": 54.5984, "lon": -5.9301, "imd_decile": 3, "region": "Northern Ireland", "users": 22},
    {"postcode": "BT7 1NN", "lat": 54.5827, "lon": -5.9308, "imd_decile": 5, "region": "Northern Ireland", "users": 17},
    {"postcode": "BT9 6AD", "lat": 54.5722, "lon": -5.9527, "imd_decile": 8, "region": "Northern Ireland", "users": 9},
    {"postcode": "BT12 5EF", "lat": 54.5883, "lon": -5.9565, "imd_decile": 2, "region": "Northern Ireland", "users": 26},
    
    # More scattered data points
    {"postcode": "OX1 2JD", "lat": 51.7520, "lon": -1.2577, "imd_decile": 7, "region": "England", "users": 11},
    {"postcode": "CB2 1TN", "lat": 52.2053, "lon": 0.1218, "imd_decile": 8, "region": "England", "users": 9},
    {"postcode": "YO1 7HH", "lat": 53.9583, "lon": -1.0803, "imd_decile": 6, "region": "England", "users": 13},
    {"postcode": "DD1 4QB", "lat": 56.4640, "lon": -2.9719, "imd_decile": 4, "region": "Scotland", "users": 15},
    {"postcode": "AB10 1XG", "lat": 57.1497, "lon": -2.0943, "imd_decile": 6, "region": "Scotland", "users": 12},
    {"postcode": "IV1 1JF", "lat": 57.4791, "lon": -4.2247, "imd_decile": 5, "region": "Scotland", "users": 14},
    {"postcode": "PL4 6AB", "lat": 50.3755, "lon": -4.1427, "imd_decile": 3, "region": "England", "users": 18},
    {"postcode": "EX4 4QJ", "lat": 50.7260, "lon": -3.5275, "imd_decile": 5, "region": "England", "users": 14},
    {"postcode": "LL57 2DG", "lat": 53.2274, "lon": -4.1293, "imd_decile": 4, "region": "Wales", "users": 16},
]


# ============================================
# H3 HEXAGON GRID FUNCTIONS
# ============================================

def get_hexagon_grid(center_lat, center_lon, resolution=7, ring_size=30):
    """
    Create a hexagonal grid using H3 library.
    
    Parameters:
    - center_lat, center_lon: Center point for the grid
    - resolution: H3 resolution (0-15). Higher = smaller hexagons
      Resolution 7 ≈ 5.16 km² per hexagon
      Resolution 8 ≈ 0.74 km² per hexagon
      Resolution 9 ≈ 0.11 km² per hexagon
    - ring_size: Number of concentric rings around center
    
    Returns: GeoDataFrame with hexagon geometries
    """
    # Get center hexagon ID
    center_hex = h3.latlng_to_cell(center_lat, center_lon, resolution)
    
    # Get all hexagons in the grid (center + rings)
    hexagons = h3.grid_disk(center_hex, ring_size)
    
    # Convert to GeoDataFrame
    hex_data = []
    for hex_id in hexagons:
        # Get hexagon boundary
        boundary = h3.cell_to_boundary(hex_id)
        # Convert to Shapely polygon (h3 returns lat/lng, Shapely expects lng/lat)
        polygon = Polygon([(lng, lat) for lat, lng in boundary])
        hex_data.append({
            'hex_id': hex_id,
            'geometry': polygon,
            'center_lat': h3.cell_to_latlng(hex_id)[0],
            'center_lon': h3.cell_to_latlng(hex_id)[1]
        })
    
    gdf = gpd.GeoDataFrame(hex_data, crs="EPSG:4326")
    return gdf


def assign_points_to_hexagons(df, resolution=7):
    """
    Assign each point (postcode) to its corresponding H3 hexagon.
    
    Parameters:
    - df: DataFrame with 'lat' and 'lon' columns
    - resolution: H3 resolution
    
    Returns: DataFrame with added 'hex_id' column
    """
    df = df.copy()
    df['hex_id'] = df.apply(
        lambda row: h3.latlng_to_cell(row['lat'], row['lon'], resolution),
        axis=1
    )
    return df


def aggregate_by_hexagon(df):
    """
    Aggregate data by hexagon ID with mean, median, and mode.
    
    Returns: DataFrame with aggregated statistics per hexagon
    """
    def calc_mode(x):
        """Calculate mode, return first value if multiple modes"""
        mode_result = scipy_stats.mode(x, keepdims=True)
        return mode_result.mode[0] if len(mode_result.mode) > 0 else x.iloc[0]
    
    agg_df = df.groupby('hex_id').agg({
        'imd_decile': ['mean', 'median', calc_mode, 'min', 'max', 'count'],
        'users': 'sum',
        'postcode': lambda x: '<br>'.join(x),  # HTML line break for hover
        'lat': 'mean',
        'lon': 'mean',
        'region': 'first'
    }).reset_index()
    
    # Flatten column names
    agg_df.columns = ['hex_id', 'mean_imd', 'median_imd', 'mode_imd', 'min_imd', 'max_imd', 'postcode_count',
                      'total_users', 'postcodes', 'center_lat', 'center_lon', 'region']
    return agg_df


def create_hexagon_geojson(hex_ids):
    """
    Create GeoJSON features for hexagons.
    
    Parameters:
    - hex_ids: List of H3 hexagon IDs
    
    Returns: GeoJSON dict
    """
    features = []
    for hex_id in hex_ids:
        boundary = h3.cell_to_boundary(hex_id)
        # GeoJSON uses [lng, lat] order
        coordinates = [[lng, lat] for lat, lng in boundary]
        coordinates.append(coordinates[0])  # Close the polygon
        
        features.append({
            "type": "Feature",
            "id": hex_id,
            "properties": {"hex_id": hex_id},
            "geometry": {
                "type": "Polygon",
                "coordinates": [coordinates]
            }
        })
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


# ============================================
# VISUALIZATION FUNCTIONS
# ============================================

def create_hexagon_choropleth(df, resolution=7, color_by='mean_imd', stat_type='mean', show_labels=True, title="Hexagonal Heatmap"):
    """
    Create an interactive hexagonal choropleth map with labels inside hexagons.
    
    Parameters:
    - df: Original DataFrame with postcode data
    - resolution: H3 resolution
    - color_by: Variable to color hexagons by ('mean_imd', 'median_imd', 'mode_imd', 'total_users')
    - stat_type: 'mean', 'median', or 'mode'
    - show_labels: Whether to show text labels inside hexagons
    - title: Map title
    
    Returns: Plotly figure
    """
    # Assign postcodes to hexagons
    df_hex = assign_points_to_hexagons(df, resolution)
    
    # Aggregate by hexagon
    hex_stats = aggregate_by_hexagon(df_hex)
    
    if hex_stats.empty:
        return go.Figure()
    
    # Map stat_type to column name
    stat_column = f'{stat_type}_imd'
    
    # Create GeoJSON for hexagons
    geojson = create_hexagon_geojson(hex_stats['hex_id'].tolist())
    
    # Color settings based on variable
    if color_by in ['mean_imd', 'median_imd', 'mode_imd']:
        color_scale = "RdYlGn"  # Red (deprived) to Green (least deprived)
        color_range = [1, 10]
        stat_labels = {'mean_imd': 'Mean IMD', 'median_imd': 'Median IMD', 'mode_imd': 'Mode IMD'}
        color_label = stat_labels.get(color_by, 'IMD Decile')
    else:
        color_scale = "Viridis"
        color_range = [hex_stats['total_users'].min(), hex_stats['total_users'].max()]
        color_label = "Total Users"
    
    # Create choropleth
    fig = px.choropleth_mapbox(
        hex_stats,
        geojson=geojson,
        locations='hex_id',
        color=color_by,
        color_continuous_scale=color_scale,
        range_color=color_range,
        mapbox_style="carto-positron",
        zoom=5,
        center={"lat": hex_stats['center_lat'].mean(), "lon": hex_stats['center_lon'].mean()},
        opacity=0.7,
        hover_data={
            'hex_id': False,
            'mean_imd': ':.1f',
            'median_imd': ':.1f',
            'mode_imd': ':.0f',
            'min_imd': ':.0f',
            'max_imd': ':.0f',
            'postcode_count': True,
            'total_users': True,
            'region': True,
            'postcodes': True
        },
        labels={
            'mean_imd': 'Mean IMD',
            'median_imd': 'Median IMD',
            'mode_imd': 'Mode IMD',
            'min_imd': 'Min IMD',
            'max_imd': 'Max IMD',
            'postcode_count': 'Postcodes',
            'total_users': 'Total Users',
            'region': 'Region',
            'postcodes': 'Postcode List'
        }
    )
    
    # Add text labels inside hexagons
    if show_labels:
        # Create text for display inside hexagons
        display_texts = []
        for _, row in hex_stats.iterrows():
            imd_val = row[stat_column]
            users = row['total_users']
            pc_count = row['postcode_count']
            display_texts.append(f"IMD:{imd_val:.1f}\nU:{users}\nPC:{pc_count}")
        
        fig.add_trace(go.Scattermapbox(
            lat=hex_stats['center_lat'],
            lon=hex_stats['center_lon'],
            mode='text',
            text=display_texts,
            textfont=dict(size=9, color='black', family='Arial Black'),
            textposition='middle center',
            hoverinfo='skip',
            showlegend=False
        ))
    
    fig.update_layout(
        title=dict(text=title, x=0.5),
        margin={"r": 0, "t": 50, "l": 0, "b": 0},
        height=700,
        coloraxis_colorbar=dict(title=color_label)
    )
    
    return fig, hex_stats


def create_comparison_view(df, resolution=7):
    """
    Create side-by-side comparison: Points vs Hexagons
    """
    from plotly.subplots import make_subplots
    
    # Assign hexagons
    df_hex = assign_points_to_hexagons(df, resolution)
    hex_stats = aggregate_by_hexagon(df_hex)
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Point Markers (Traditional)", f"Hexagonal Grid (H3 Res {resolution})"),
        specs=[[{"type": "mapbox"}, {"type": "mapbox"}]]
    )
    
    # Left: Point markers
    fig.add_trace(
        go.Scattermapbox(
            lat=df['lat'],
            lon=df['lon'],
            mode='markers',
            marker=dict(
                size=df['users'] / 2,
                color=df['imd_decile'],
                colorscale='RdYlGn',
                cmin=1, cmax=10,
                opacity=0.8
            ),
            text=df['postcode'],
            hovertemplate='<b>%{text}</b><br>IMD: %{marker.color}<br>Users: %{marker.size:.0f}<extra></extra>',
            name='Postcodes'
        ),
        row=1, col=1
    )
    
    # Right: Hexagon centers (simplified view)
    fig.add_trace(
        go.Scattermapbox(
            lat=hex_stats['center_lat'],
            lon=hex_stats['center_lon'],
            mode='markers',
            marker=dict(
                size=hex_stats['total_users'] / 2,
                color=hex_stats['avg_imd'],
                colorscale='RdYlGn',
                cmin=1, cmax=10,
                opacity=0.8,
                symbol='hexagon'
            ),
            text=hex_stats['hex_id'],
            hovertemplate='<b>Hexagon</b><br>Avg IMD: %{marker.color:.1f}<br>Users: %{marker.size:.0f}<extra></extra>',
            name='Hexagons'
        ),
        row=1, col=2
    )
    
    center_lat = df['lat'].mean()
    center_lon = df['lon'].mean()
    
    fig.update_layout(
        mapbox=dict(style="carto-positron", center=dict(lat=center_lat, lon=center_lon), zoom=5),
        mapbox2=dict(style="carto-positron", center=dict(lat=center_lat, lon=center_lon), zoom=5),
        height=600,
        margin={"r": 0, "t": 50, "l": 0, "b": 0},
        showlegend=False
    )
    
    return fig


# ============================================
# DASH APPLICATION
# ============================================

app = Dash(__name__)
server = app.server  # For production deployment (gunicorn/Render/Railway)

app.layout = html.Div([
    html.H1("Hexagonal Heatmap Demo - H3 + Plotly", 
            style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '20px'}),
    
    html.Div([
        html.P([
            "This demo shows hexagonal heatmapping using Uber's H3 library. ",
            "Hexagons provide uniform area representation, eliminating visual bias ",
            "from irregular administrative boundaries."
        ], style={'textAlign': 'center', 'color': '#7f8c8d', 'marginBottom': '20px'}),
    ]),
    
    html.Div([
        html.Div([
            html.Label("H3 Resolution:", style={'fontWeight': 'bold'}),
            dcc.Slider(
                id='resolution-slider',
                min=4,
                max=9,
                step=1,
                value=7,
                marks={i: f'Res {i}' for i in range(4, 10)},
                tooltip={"placement": "bottom", "always_visible": True}
            ),
            html.Small("Higher resolution = smaller hexagons", style={'color': '#95a5a6'})
        ], style={'width': '30%', 'display': 'inline-block', 'marginRight': '3%'}),
        
        html.Div([
            html.Label("IMD Statistic:", style={'fontWeight': 'bold'}),
            dcc.RadioItems(
                id='stat-type-radio',
                options=[
                    {'label': ' Mean', 'value': 'mean'},
                    {'label': ' Median', 'value': 'median'},
                    {'label': ' Mode', 'value': 'mode'}
                ],
                value='mean',
                inline=True
            ),
            html.Small("Statistical measure for IMD aggregation", style={'color': '#95a5a6'})
        ], style={'width': '25%', 'display': 'inline-block', 'marginRight': '3%'}),
        
        html.Div([
            html.Label("Color By:", style={'fontWeight': 'bold'}),
            dcc.RadioItems(
                id='color-by-radio',
                options=[
                    {'label': ' IMD Decile', 'value': 'imd'},
                    {'label': ' Total Users', 'value': 'total_users'}
                ],
                value='imd',
                inline=True
            )
        ], style={'width': '20%', 'display': 'inline-block', 'marginRight': '3%'}),
        
        html.Div([
            html.Label("Show Labels:", style={'fontWeight': 'bold'}),
            dcc.Checklist(
                id='show-labels-check',
                options=[{'label': ' Display details in hexagons', 'value': 'show'}],
                value=['show'],
                inline=True
            )
        ], style={'width': '15%', 'display': 'inline-block'})
    ], style={'padding': '20px', 'backgroundColor': '#ecf0f1', 'borderRadius': '10px', 'marginBottom': '20px'}),
    
    html.Div([
        html.Label("Filter by Region:", style={'fontWeight': 'bold'}),
        dcc.Checklist(
            id='region-filter',
            options=[
                {'label': ' England', 'value': 'England'},
                {'label': ' Scotland', 'value': 'Scotland'},
                {'label': ' Wales', 'value': 'Wales'},
                {'label': ' Northern Ireland', 'value': 'Northern Ireland'}
            ],
            value=['England', 'Scotland', 'Wales', 'Northern Ireland'],
            inline=True
        )
    ], style={'padding': '15px', 'backgroundColor': '#fff', 'borderRadius': '10px', 'marginBottom': '20px', 'border': '1px solid #ddd'}),
    
    dcc.Loading(
        id="loading",
        type="circle",
        children=[dcc.Graph(id='hexagon-map')]
    ),
    
    html.Div([
        html.H3("Statistics", style={'color': '#2c3e50'}),
        html.Div(id='stats-display')
    ], style={'padding': '20px', 'backgroundColor': '#f8f9fa', 'borderRadius': '10px', 'marginTop': '20px'}),
    
    html.Hr(),
    
    html.Div([
        html.H3("Resolution Guide", style={'color': '#2c3e50'}),
        html.Table([
            html.Thead(html.Tr([
                html.Th("Resolution"), html.Th("Avg Hexagon Area"), html.Th("Avg Edge Length"), html.Th("Use Case")
            ])),
            html.Tbody([
                html.Tr([html.Td("4"), html.Td("~1,770 km²"), html.Td("~22 km"), html.Td("Country-level overview")]),
                html.Tr([html.Td("5"), html.Td("~252 km²"), html.Td("~8 km"), html.Td("Regional analysis")]),
                html.Tr([html.Td("6"), html.Td("~36 km²"), html.Td("~3.2 km"), html.Td("County/district level")]),
                html.Tr([html.Td("7"), html.Td("~5.16 km²"), html.Td("~1.2 km"), html.Td("City districts")]),
                html.Tr([html.Td("8"), html.Td("~0.74 km²"), html.Td("~460 m"), html.Td("Neighborhood level")]),
                html.Tr([html.Td("9"), html.Td("~0.11 km²"), html.Td("~174 m"), html.Td("Street level")]),
            ])
        ], style={'width': '100%', 'borderCollapse': 'collapse', 'marginTop': '10px'})
    ], style={'padding': '20px', 'backgroundColor': '#e8f6f3', 'borderRadius': '10px'}),
    
], style={'maxWidth': '1400px', 'margin': '0 auto', 'padding': '20px', 'fontFamily': 'Arial, sans-serif'})


@callback(
    [Output('hexagon-map', 'figure'),
     Output('stats-display', 'children')],
    [Input('resolution-slider', 'value'),
     Input('stat-type-radio', 'value'),
     Input('color-by-radio', 'value'),
     Input('show-labels-check', 'value'),
     Input('region-filter', 'value')]
)
def update_map(resolution, stat_type, color_by, show_labels, regions):
    # Create DataFrame
    df = pd.DataFrame(SAMPLE_POSTCODE_DATA)
    
    # Filter by regions
    if regions:
        df = df[df['region'].isin(regions)]
    
    if df.empty:
        return go.Figure(), html.P("No data to display. Select at least one region.")
    
    # Determine color column based on selection
    if color_by == 'imd':
        color_column = f'{stat_type}_imd'
    else:
        color_column = 'total_users'
    
    # Create map
    fig, hex_stats = create_hexagon_choropleth(
        df, 
        resolution=resolution,
        color_by=color_column,
        stat_type=stat_type,
        show_labels='show' in show_labels if show_labels else False,
        title=f"UK Postcode IMD Heatmap (H3 Res: {resolution}, Stat: {stat_type.capitalize()})"
    )
    
    # Calculate overall statistics
    weighted_mean = (df['imd_decile'] * df['users']).sum() / df['users'].sum()
    overall_median = df['imd_decile'].median()
    mode_result = scipy_stats.mode(df['imd_decile'], keepdims=True)
    overall_mode = mode_result.mode[0] if len(mode_result.mode) > 0 else df['imd_decile'].iloc[0]
    
    stats = html.Div([
        html.H4("Overall Statistics", style={'marginBottom': '10px', 'color': '#34495e'}),
        html.Div([
            html.Div([
                html.Span("Total Postcodes: ", style={'fontWeight': 'bold'}),
                html.Span(f"{len(df)}")
            ], style={'marginRight': '25px', 'display': 'inline-block'}),
            html.Div([
                html.Span("Unique Hexagons: ", style={'fontWeight': 'bold'}),
                html.Span(f"{len(hex_stats)}")
            ], style={'marginRight': '25px', 'display': 'inline-block'}),
            html.Div([
                html.Span("Total Users: ", style={'fontWeight': 'bold'}),
                html.Span(f"{df['users'].sum()}")
            ], style={'display': 'inline-block'}),
        ], style={'marginBottom': '10px'}),
        html.Div([
            html.Div([
                html.Span("Mean IMD: ", style={'fontWeight': 'bold', 'color': '#2980b9'}),
                html.Span(f"{weighted_mean:.2f}", style={'fontSize': '1.1em'})
            ], style={'marginRight': '25px', 'display': 'inline-block', 'padding': '5px', 'backgroundColor': '#ebf5fb', 'borderRadius': '5px'}),
            html.Div([
                html.Span("Median IMD: ", style={'fontWeight': 'bold', 'color': '#27ae60'}),
                html.Span(f"{overall_median:.1f}", style={'fontSize': '1.1em'})
            ], style={'marginRight': '25px', 'display': 'inline-block', 'padding': '5px', 'backgroundColor': '#eafaf1', 'borderRadius': '5px'}),
            html.Div([
                html.Span("Mode IMD: ", style={'fontWeight': 'bold', 'color': '#8e44ad'}),
                html.Span(f"{overall_mode}", style={'fontSize': '1.1em'})
            ], style={'marginRight': '25px', 'display': 'inline-block', 'padding': '5px', 'backgroundColor': '#f5eef8', 'borderRadius': '5px'}),
            html.Div([
                html.Span("IMD Range: ", style={'fontWeight': 'bold', 'color': '#e67e22'}),
                html.Span(f"{df['imd_decile'].min()} - {df['imd_decile'].max()}", style={'fontSize': '1.1em'})
            ], style={'display': 'inline-block', 'padding': '5px', 'backgroundColor': '#fef9e7', 'borderRadius': '5px'}),
        ]),
    ])
    
    return fig, stats


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8051))
    print("\n" + "="*60)
    print("HEXAGONAL HEATMAP DEMO")
    print("="*60)
    print(f"Starting server on http://localhost:{port}")
    print("Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=port)
