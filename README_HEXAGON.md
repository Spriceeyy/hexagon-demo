# Hexagonal Heatmap Demo

Interactive hexagonal heatmap visualization using **Uber's H3** library and **Plotly Dash**.

## Features

- **H3 Hexagonal Grid** - Uniform area representation eliminates visual bias from irregular boundaries
- **Mean / Median / Mode** - Choose statistical measure for IMD aggregation
- **Interactive Controls** - Resolution slider, color options, region filters
- **Details in Hexagons** - Shows IMD value, user count, and postcode count
- **UK Coverage** - Sample data across England, Scotland, Wales, and Northern Ireland

## Live Demo

[View Demo on Render](https://your-app-name.onrender.com) *(update after deployment)*

## Local Development

```bash
# Install dependencies
pip install -r requirements_hexagon.txt

# Run locally
python hexagon_heatmap_demo.py
```

Then open http://localhost:8051

## Deployment

### Render.com (Recommended for Dash apps)

1. Push to GitHub
2. Go to [render.com](https://render.com) and create a new Web Service
3. Connect your GitHub repo
4. Settings:
   - **Build Command**: `pip install -r requirements_hexagon.txt`
   - **Start Command**: `gunicorn hexagon_heatmap_demo:server`
5. Deploy!

### Railway.app

1. Push to GitHub
2. Go to [railway.app](https://railway.app) and create new project
3. Deploy from GitHub repo
4. Add start command: `gunicorn hexagon_heatmap_demo:server`

## H3 Resolution Guide

| Resolution | Avg Hexagon Area | Avg Edge Length | Use Case |
|------------|------------------|-----------------|----------|
| 4 | ~1,770 km² | ~22 km | Country overview |
| 5 | ~252 km² | ~8 km | Regional analysis |
| 6 | ~36 km² | ~3.2 km | County/district |
| 7 | ~5.16 km² | ~1.2 km | City districts |
| 8 | ~0.74 km² | ~460 m | Neighborhood |
| 9 | ~0.11 km² | ~174 m | Street level |

## Color Guide

- 🔴 **Red** = Most deprived (IMD 1-2)
- 🟡 **Yellow** = Medium deprivation (IMD 5-6)
- 🟢 **Green** = Least deprived (IMD 9-10)

## Technology Stack

- [H3](https://h3geo.org/) - Uber's hexagonal hierarchical spatial index
- [Plotly Dash](https://dash.plotly.com/) - Python framework for interactive web apps
- [GeoPandas](https://geopandas.org/) - Geospatial data handling
- [SciPy](https://scipy.org/) - Statistical calculations

## License

MIT
