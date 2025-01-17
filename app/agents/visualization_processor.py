from typing import Dict, Any, List
import plotly.graph_objects as go
import json
import logging

logger = logging.getLogger(__name__)

class VisualizationProcessor:
    def generate_visualization(self, data: List[Dict[str, Any]], viz_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate visualization HTML using Plotly based on data and configuration.
        
        Args:
            data: List of dictionaries containing query results
            viz_config: Dictionary containing:
                - type: visualization type (pie, bar, line, table)
                - columns: dict with x and y column names
                
        Returns:
            Dict containing:
            - success: boolean indicating if visualization was generated
            - html: the generated HTML if successful
            - error: error message if unsuccessful
        """
        # Get chart-specific query suggestions from Claude if visualization type is specified
        if viz_config.get('type') in ['pie', 'bar', 'line']:
            chart_query = self._get_chart_query(data, viz_config['type'])
            if chart_query.get('error'):
                logger.error({
                    "agent": "VisualizationProcessor",
                    "action": "chart_query_failed",
                    "error": chart_query['error']
                })
                return {
                    "success": False,
                    "error": chart_query['error'],
                    "html": self._generate_error_html(list(data[0].keys()) if data else [])
                }
            
            # Use the optimized data and columns for visualization
            if chart_query.get('success'):
                logger.info({
                    "agent": "VisualizationProcessor",
                    "action": "using_optimized_chart_data",
                    "columns": chart_query['columns']
                })
                data = chart_query['data']
                viz_config['columns'] = chart_query['columns']
        logger.info({
            "agent": "VisualizationProcessor",
            "action": "starting_visualization",
            "config": viz_config,
            "data_rows": len(data) if data else 0
        })

        if not data:
            logger.warning({
                "agent": "VisualizationProcessor",
                "action": "visualization_failed",
                "error": "No data available"
            })
            return {
                "success": False,
                "error": "No data available for visualization",
                "html": "<p>No data available for visualization</p>"
            }
            
        columns = list(data[0].keys())
        if len(columns) < 2:
            return {
                "success": False,
                "error": "Need at least two columns for visualization",
                "html": "<p>Need at least two columns for visualization</p>"
            }
        
        try:
            # Get x and y columns from visualization config
            x_column = viz_config.get('columns', {}).get('x', columns[0])
            y_column = viz_config.get('columns', {}).get('y', columns[1])
            
            logger.info({
                "agent": "VisualizationProcessor",
                "action": "column_selection",
                "x_column": x_column,
                "y_column": y_column
            })
            
            # Find matching columns using helper functions
            x_col_match = self._find_matching_column(x_column, columns)
            y_col_match = self._find_matching_column(y_column, columns)
            
            if not x_col_match or not y_col_match:
                logger.warning({
                    "agent": "VisualizationProcessor",
                    "action": "column_match_failed",
                    "requested_x": x_column,
                    "requested_y": y_column,
                    "available_columns": columns
                })
                # Try to find alternative columns
                numeric_cols, categorical_cols = self._analyze_column_types(data[0])
                
                if categorical_cols and numeric_cols:
                    x_col_match = categorical_cols[0]
                    y_col_match = numeric_cols[0]
                else:
                    return {
                        "success": False,
                        "error": "Could not find appropriate columns for visualization",
                        "html": self._generate_error_html(columns)
                    }
            
            # Extract and format data
            x_data, y_data = self._extract_data(data, x_col_match, y_col_match)
            
            # Create figure based on visualization type
            chart_type = viz_config.get('type', 'bar')
            logger.info({
                "agent": "VisualizationProcessor",
                "action": "creating_figure",
                "chart_type": chart_type,
                "x_column_final": x_col_match,
                "y_column_final": y_col_match
            })
            
            fig = self._create_figure(chart_type, x_data, y_data, x_col_match, y_col_match)
            
            # Generate HTML
            html = self._generate_html(fig)
            
            logger.info({
                "agent": "VisualizationProcessor",
                "action": "visualization_complete",
                "chart_type": chart_type
            })
            
            return {
                "success": True,
                "html": html
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error({
                "agent": "VisualizationProcessor",
                "action": "visualization_error",
                "error": error_msg
            })
            return {
                "success": False,
                "error": str(e),
                "html": f"<p>Error generating visualization: {str(e)}</p>"
            }

    def _normalize_column_name(self, col: str) -> str:
        """Normalize column name for comparison."""
        col = col.split('.')[-1] if '.' in col else col
        col = col.strip('"\'`[]')
        return col.lower()

    def _find_matching_column(self, target: str, available_columns: List[str]) -> str:
        """Find matching column name in available columns."""
        target_norm = self._normalize_column_name(target)
        
        # Direct match
        if target in available_columns:
            return target
            
        # Normalized match
        for col in available_columns:
            if self._normalize_column_name(col) == target_norm:
                return col
                
        # Match aggregated columns
        if any(op in target_norm for op in ['count', 'sum', 'avg']):
            for col in available_columns:
                col_norm = self._normalize_column_name(col)
                if col_norm == target_norm.split('as')[-1].strip():
                    return col
        
        return None

    def _analyze_column_types(self, first_row: Dict[str, Any]) -> tuple:
        """Analyze columns to find numeric and categorical ones."""
        numeric_columns = []
        categorical_columns = []
        
        for col, value in first_row.items():
            try:
                if value is not None:
                    float(str(value).replace(',', ''))
                    numeric_columns.append(col)
            except ValueError:
                categorical_columns.append(col)
                
        return numeric_columns, categorical_columns

    def _extract_data(self, data: List[Dict[str, Any]], x_column: str, y_column: str) -> tuple:
        """Extract and format x and y data from results."""
        x_data = []
        y_data = []
        
        for row in data:
            # Handle x-axis data (categorical)
            x_value = str(row[x_column]) if row[x_column] is not None else ''
            x_data.append(x_value)
            
            # Handle y-axis data (numeric)
            try:
                y_value = str(row[y_column]).replace(',', '') if row[y_column] is not None else '0'
                y_data.append(float(y_value))
            except (ValueError, TypeError):
                y_data.append(0)
                
        return x_data, y_data

    def _create_figure(self, chart_type: str, x_data: List, y_data: List, x_label: str, y_label: str) -> go.Figure:
        """Create Plotly figure based on chart type."""
        # Define color palette
        colors = ['#095B9D', '#06526e', '#15259d', '#099d39', '#066e28']
        
        if chart_type == 'pie':
            fig = go.Figure(data=[go.Pie(
                labels=x_data,
                values=y_data,
                marker=dict(colors=colors)
            )])
        elif chart_type == 'bar':
            fig = go.Figure(data=[go.Bar(
                x=x_data,
                y=y_data,
                marker=dict(color=colors[0])
            )])
        elif chart_type == 'line':
            fig = go.Figure(data=[go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines+markers',
                line=dict(color=colors[0]),
                marker=dict(color=colors[1])
            )])
        elif chart_type == 'table':
            fig = go.Figure(data=[go.Table(
                header=dict(
                    values=[x_label, y_label],
                    fill_color=colors[0],
                    align='left',
                    font=dict(color='white')
                ),
                cells=dict(
                    values=[x_data, y_data],
                    fill_color=colors[1],
                    align='left',
                    font=dict(color='white')
                )
            )])
            # Adjust layout for table
            fig.update_layout(
                margin=dict(t=0, l=0, r=0, b=0),
                height=min(400, len(x_data) * 30 + 40)
            )
        else:
            raise ValueError(f"Unsupported visualization type: {chart_type}")
        
        # Update layout for non-table visualizations
        if chart_type != 'table':
            # Use the first color with transparency for background
            bg_color = f'rgba(9, 91, 157, 0.1)'  # #095B9D with 0.1 opacity
            
            fig.update_layout(
                margin=dict(t=30, l=30, r=30, b=30),
                paper_bgcolor=bg_color,
                plot_bgcolor=bg_color,
                font=dict(color='#FFFFFF'),
                showlegend=True,
                height=400
            )
            
            # Update axes for better visibility
            fig.update_xaxes(
                gridcolor='#095B9D',
                zerolinecolor='#095B9D'
            )
            fig.update_yaxes(
                gridcolor='#095B9D',
                zerolinecolor='#095B9D'
            )
            
        return fig

    def _generate_html(self, fig: go.Figure) -> str:
        """Generate HTML with required headers and configuration."""
        html = fig.to_html(
            full_html=True,
            include_plotlyjs='https://cdn.plot.ly/plotly-latest.min.js',
            config={'responsive': True, 'displayModeBar': True}
        )
        
        # Add required meta tags and viewport settings
        html = html.replace('<head>', '''<head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        ''')
        
        return html

    def _get_chart_query(self, data: List[Dict[str, Any]], chart_type: str) -> Dict[str, Any]:
        """
        Get chart-specific query suggestions from Claude.
        
        Args:
            data: List of dictionaries containing query results
            chart_type: Type of chart (pie, bar, line)
            
        Returns:
            Dict containing:
            - success: boolean indicating if query was generated
            - data: processed data if successful
            - columns: suggested x and y columns
            - error: error message if unsuccessful
        """
        try:
            from anthropic import Anthropic
            client = Anthropic()
            
            # Get database structure from SQLGenerator
            from ..agents.sql_generator import SQLGenerator
            db_structure = SQLGenerator().db_structure
            
            # Create prompt for Claude
            columns = list(data[0].keys()) if data else []
            sample_data = json.dumps(data[:3], indent=2) if data else "No data available"
            
            # First prompt to get initial query
            initial_prompt = f"""Using this database structure:

{db_structure}

And this sample data with columns {columns}:
{sample_data}

Generate a SQL query to analyze this data. Return ONLY the raw SQL query, no explanations or formatting."""

            # Get initial query
            message = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                system="You are a SQL expert. Return ONLY the raw SQL query without any explanations or formatting.",
                messages=[{"role": "user", "content": initial_prompt}]
            )
            
            initial_query = message.content[0].text.strip()
            
            # Second prompt to optimize for visualization
            viz_prompt = f"""Given this SQL query:
{initial_query}

How would you modify it for a {chart_type} chart? Requirements:
- For pie charts: Need a category column and a numeric sum, like: SELECT category, SUM(CAST(number AS FLOAT)) as value
- For bar charts: Need a category column and a numeric sum, like: SELECT category, SUM(CAST(number AS FLOAT)) as value
- For line charts: Need a time-based column and a numeric sum, like: SELECT date, SUM(CAST(number AS FLOAT)) as value
- Keep any existing WHERE conditions and table joins
- Use proper table names from the schema

Return ONLY the modified SQL query, no explanations or formatting."""

            # Get visualization-optimized query
            message = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                system="You are a SQL expert. Return ONLY the modified SQL query without any explanations or formatting.",
                messages=[{"role": "user", "content": viz_prompt}]
            )
            
            final_query = message.content[0].text.strip()
            
            # Log both queries
            logger.info({
                "agent": "VisualizationProcessor",
                "action": "generated_queries",
                "initial_query": initial_query,
                "visualization_query": final_query
            })

            # Execute the visualization query
            import os
            from ..services.database_service import DatabaseService
            db_path = os.path.join('datalake', 'datalake.db')
            db_service = DatabaseService(db_path)
            result = db_service.execute_query(final_query)
            
            if result['success']:
                columns = []
                if result.get('results'):
                    first_row = result['results'][0]
                    columns = list(first_row.keys())
                
                logger.info({
                    "agent": "VisualizationProcessor",
                    "action": "query_execution_success",
                    "columns": columns
                })
                
                return {
                    "success": True,
                    "data": result.get('results', []),
                    "columns": {
                        "x": columns[0] if columns else None,
                        "y": columns[1] if len(columns) >= 2 else None
                    },
                    "optimized_query": final_query
                }
            
            return {
                "success": False,
                "error": "Failed to execute visualization query"
            }
            
        except Exception as e:
            logger.error({
                "agent": "VisualizationProcessor",
                "action": "get_chart_query",
                "error": str(e)
            })
            return {
                "success": False,
                "error": f"Failed to get chart query: {str(e)}"
            }

    def _generate_error_html(self, columns: List[str]) -> str:
        """Generate error HTML with available columns information."""
        return f"""
        <div class="visualization-error">
            <h4>Column Selection Error</h4>
            <p>Could not find appropriate columns for visualization.</p>
            <p>Available columns in results:</p>
            <ul>
                {' '.join(f'<li>{col}</li>' for col in columns)}
            </ul>
            <p>Please modify the query to include both categorical and numeric columns.</p>
        </div>
        """
