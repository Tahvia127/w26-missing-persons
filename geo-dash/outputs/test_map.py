import plotly.express as px
import pandas as pd

# Sample data - replace with real data later
df = pd.DataFrame({
    'state': ['California', 'Texas', 'Florida', 'New York'],
    'cases': [150, 120, 90, 85]
})

fig = px.choropleth(
    df,
    locations='state',
    locationmode='USA-states',
    color='cases',
    scope='usa',
    color_continuous_scale='Reds',
    title='Missing Persons Cases by State'
)
fig.show()