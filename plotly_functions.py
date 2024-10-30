import plotly.graph_objs as go
import plotly, plotly.express as px
import json
from translation_canvas.sql_queries import get_filename

def create_histogram(df, xaxis_title, yaxis_title, title, bar_width=None, ticks=''):
        # Create the bar chart using Plotly
        fig = px.bar(
            df,
            x=xaxis_title,
            y=yaxis_title,
            color='Run',
            barmode='group',
            title=title,
            labels={'Category': 'Category', 'Count': 'Count'}
        )
        
        if ticks != '':
            # Update the layout with specified colors
            fig.update_layout(
                plot_bgcolor='white',
                font=dict(color='black'),
                title_font=dict(color='black', size=24),
                xaxis=dict(
                    showgrid=False, 
                    linecolor='black', 
                    ticks=ticks,  # Hide tick marks
                    automargin=True
                ),
                yaxis=dict(
                    showgrid=False, 
                    gridcolor='#f4f4f9', 
                    linecolor='black', 
                    ticks='outside',
                    automargin=True
                ),
                legend_title_text='Runs',
            )
        else:
            # Update the layout with specified colors
            fig.update_layout(
                plot_bgcolor='white',
                font=dict(color='black'),
                title_font=dict(color='black', size=24),
                xaxis=dict(
                    showgrid=False, 
                    linecolor='black', 
                    ticks='',  # Hide tick marks
                    tickvals = [],  # Hide tick marks
                    ticktext=[],  # Hide tick text
                    automargin=True
                ),
                yaxis=dict(
                    showgrid=False, 
                    gridcolor='#f4f4f9', 
                    linecolor='black', 
                    ticks='outside',
                    automargin=True
                ),
                legend_title_text='Runs',
            )
        if bar_width:
            fig.update_traces(width=bar_width)

        
        # Convert the plot to JSON
        histogram = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return histogram


def create_radar_chart(df, normalized_df, categories):

        # Define colors for the radar chart
        
        contrast_colors = ['rgba(63, 81, 181, 0.3)', 'rgba(233, 30, 99, 0.3)', 'rgba(255, 152, 0, 0.3)', 'rgba(76, 175, 80, 0.3)', 'rgba(0, 188, 212, 0.3)', 'rgba(156, 39, 176, 0.3)', 'rgba(255, 235, 59, 0.3)']

        # Create radar chart
        fig = go.Figure()
        
        # Add traces for each run_id
        for index, row in normalized_df.iterrows():
            text = [f'{category}: {round(df[category][index], 2)}' for category in categories]
            text.append(f'{categories[0]}: {round(df[categories[0]][index], 2)}')  # close the loop
            fig.add_trace(go.Scatterpolar(
                r=[row[category] for category in categories] + [row[categories[0]]],  # close the loop
                theta=categories + [categories[0]],  # close the loop
                fill='toself',
                fillcolor=contrast_colors[index % len(contrast_colors)],
                line_color=contrast_colors[index % len(contrast_colors)],
                name=f'{get_filename(row["run_id"])}',
                text=text,
                textposition='top center',
                marker=dict(size=10)  # Adjust marker size here
            ))

        # Customize layout
        fig.update_layout(
            polar=dict(
                bgcolor='white',
                radialaxis=dict(
                    visible=False,
                    range=[0, 1]
                ),
                angularaxis=dict(
                    tickvals=[i for i in range(len(categories))],  # Add ticks for the categories
                    ticktext=categories,
                    linecolor='black',
                    linewidth=2
                )
            ),
            showlegend=True,
            plot_bgcolor='white',  # Set the plot background to white
            paper_bgcolor='white',  # Set the paper background to white
            title="Scores: "+', '.join([category for category in categories]),
            title_font=dict(color='black', size=24),
            legend_title_text='Runs'
        )

        radar_chart = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return radar_chart