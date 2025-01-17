from typing import Dict, Any, Optional
from anthropic import Anthropic
import os
import json
import logging

logger = logging.getLogger(__name__)

class SQLGenerator:
    def __init__(self):
        self.client = Anthropic()  # Will use ANTHROPIC_API_KEY env var by default
        self.db_structure = """
CREATE TABLE common_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_type TEXT,
    order_number TEXT,
    notification_number TEXT,
    breakdown TEXT,
    functional_location TEXT
);

CREATE TABLE IW38 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    common_id INTEGER,
    created_on TEXT,
    basic_start_date TEXT,
    equipment TEXT,
    description TEXT,
    plant_section TEXT,
    total_actual_costs TEXT,
    order_type TEXT,
    main_workcenter TEXT,
    maintenance_plan TEXT,
    actual_finish TEXT,
    cost_center TEXT,
    basic_finish_date TEXT,
    breakdown_duration TEXT,
    FOREIGN KEY (common_id) REFERENCES common_fields(id)
);

CREATE TABLE IW68 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    common_id INTEGER,
    code_group TEXT,
    problem_group_text TEXT,
    damage_code TEXT,
    problem_code_text TEXT,
    item_text TEXT,
    cause_code TEXT,
    cause_group_text TEXT,
    cause_text TEXT,
    effect TEXT,
    reported_by TEXT,
    FOREIGN KEY (common_id) REFERENCES common_fields(id)
);

CREATE TABLE IW47 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    common_id INTEGER,
    created_on TEXT,
    created_by TEXT,
    actual_finish_date TEXT,
    confirmation_number TEXT,
    employees TEXT,
    personnel_number TEXT,
    confirmation_text TEXT,
    planned_work TEXT,
    actual_work TEXT,
    system_status TEXT,
    work_center TEXT,
    actual_start_time TEXT,
    FOREIGN KEY (common_id) REFERENCES common_fields(id)
);"""

    def generate_sql(self, prompt: str, is_followup: bool = False, previous_context: Optional[str] = None, max_attempts: int = 5) -> Dict[str, Any]:
        """
        Generate SQL query from natural language prompt with retry logic.
        
        Args:
            prompt (str): The user's input prompt
            is_followup (bool): Whether this is a follow-up question
            previous_context (Optional[str]): Previous query context for follow-ups
            max_attempts (int): Maximum number of attempts to generate valid SQL
            
        Returns:
            Dict containing:
            - success: boolean indicating if generation was successful
            - query: the generated SQL query if successful
            - error: error message if unsuccessful
            - visualization_type: detected visualization type if any
        """
        system_prompt = f"""Using this database structure:

{self.db_structure}

Convert this message to a SQL query. Return ONLY the raw SQL query without any explanations, comments, or markdown formatting. Requirements:
1. Join tables when needed using common_id
2. Cast numeric columns to FLOAT when used in calculations:
   - total_actual_costs as CAST(total_actual_costs AS FLOAT)
   - breakdown_duration as CAST(breakdown_duration AS FLOAT)
   - Explicit COUNT, SUM, AVG operations
3. Use appropriate aliases for computed columns
4. Handle visualization markers (@pie, @bar, etc.)"""

        if is_followup and previous_context:
            system_prompt += f"\n\nThis is a follow-up to: {previous_context}"

        attempts = 0
        last_error = None
        
        while attempts < max_attempts:
            try:
                logger.info({
                    "agent": "SQLGenerator",
                    "action": "generating_sql",
                    "attempt": attempts + 1,
                    "prompt": prompt,
                    "is_followup": is_followup,
                    "has_previous_context": previous_context is not None
                })
                
                message = self.client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=1000,
                    system=system_prompt,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                
                response_text = message.content[0].text
                
                # Extract visualization type if present
                viz_type = None
                if '@pie' in prompt:
                    viz_type = 'pie'
                elif '@bar' in prompt:
                    viz_type = 'bar'
                elif '@line' in prompt:
                    viz_type = 'line'
                
                # Validate SQL syntax
                if self._validate_sql(response_text):
                    logger.info({
                        "agent": "SQLGenerator",
                        "action": "sql_generation_success",
                        "attempt": attempts + 1,
                        "query": response_text,
                        "visualization_type": viz_type
                    })
                    return {
                        "success": True,
                        "query": response_text,
                        "visualization_type": viz_type
                    }
                
                attempts += 1
                last_error = f"Invalid SQL syntax. Claude response: {response_text}"
                logger.warning({
                    "agent": "SQLGenerator",
                    "action": "sql_validation_failed",
                    "attempt": attempts,
                    "error": last_error,
                    "response": response_text
                })
                
            except Exception as e:
                attempts += 1
                last_error = str(e)
                logger.error({
                    "agent": "SQLGenerator",
                    "action": "sql_generation_error",
                    "attempt": attempts,
                    "error": str(e)
                })
        
        logger.error({
            "agent": "SQLGenerator",
            "action": "sql_generation_failed",
            "max_attempts": max_attempts,
            "final_error": last_error
        })
        return {
            "success": False,
            "error": f"Failed after {max_attempts} attempts. Last error: {last_error}",
            "query": None,
            "visualization_type": None
        }

    def _validate_sql(self, query: str) -> bool:
        """
        Basic SQL syntax validation.
        
        Args:
            query (str): SQL query to validate
            
        Returns:
            bool: True if query appears valid
        """
        # Basic validation - check for required elements
        query = query.lower().strip()
        
        # Remove any markdown code block markers
        query = query.replace('```sql', '').replace('```', '')
        
        if not query.startswith('select'):
            return False
        
        # Check for basic SQL injection patterns
        dangerous_patterns = ['--', 'drop', 'delete', 'update', 'insert']
        if any(pattern in query for pattern in dangerous_patterns):
            return False
            
        # Check for balanced parentheses
        if query.count('(') != query.count(')'):
            return False
            
        return True

    def get_visualization_columns(self, query: str, viz_type: str) -> Dict[str, Any]:
        """
        Determine appropriate columns for visualization from SQL query.
        
        Args:
            query (str): The SQL query
            viz_type (str): Type of visualization (pie, bar, line)
            
        Returns:
            Dict containing x and y column names for visualization
        """
        system_prompt = f"""Given this SQL query:
{query}

Return ONLY a JSON object with x and y column names for visualization, no explanations or formatting. The x column should be categorical (text) and y should be numerical:
{{
    "x": "column_name",
    "y": "column_name"
}}"""

        try:
            logger.info({
                "agent": "SQLGenerator",
                "action": "detecting_visualization_columns",
                "query": query,
                "visualization_type": viz_type
            })
            
            message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                system="Analyze the SQL query and determine appropriate columns for visualization. The x column should be categorical (text) and y should be numerical. Return only a JSON object with x and y column names.",
                messages=[
                    {
                        "role": "user",
                        "content": f"""Given this SQL query:
{query}

Please identify the most appropriate columns for a {viz_type} visualization."""
                    }
                ]
            )
            
            result = json.loads(message.content[0].text)
            logger.info({
                "agent": "SQLGenerator",
                "action": "visualization_columns_detected",
                "columns": result
            })
            return result
            
        except Exception as e:
            error_msg = f"Failed to determine visualization columns: {str(e)}"
            logger.error({
                "agent": "SQLGenerator",
                "action": "visualization_columns_error",
                "error": error_msg
            })
            return {
                "error": f"Failed to determine visualization columns: {str(e)}",
                "x": None,
                "y": None
            }
