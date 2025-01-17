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
        if chart_type == 'pie':
            fig = go.Figure(data=[go.Pie(
                labels=x_data,
                values=y_data
            )])
        elif chart_type == 'bar':
            fig = go.Figure(data=[go.Bar(
                x=x_data,
                y=y_data
            )])
        elif chart_type == 'line':
            fig = go.Figure(data=[go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines+markers'
            )])
        elif chart_type == 'table':
            fig = go.Figure(data=[go.Table(
                header=dict(
                    values=[x_label, y_label],
                    fill_color='rgba(102, 153, 204, 0.5)',
                    align='left',
                    font=dict(color='white')
                ),
                cells=dict(
                    values=[x_data, y_data],
                    fill_color='rgba(102, 153, 204, 0.1)',
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
            fig.update_layout(
                margin=dict(t=30, l=30, r=30, b=30),
                paper_bgcolor='rgba(102, 153, 204, 0.1)',
                plot_bgcolor='rgba(102, 153, 204, 0.1)',
                font=dict(color='#FFFFFF'),
                showlegend=True,
                height=400
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
