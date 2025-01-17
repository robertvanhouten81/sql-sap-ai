import logging
from .prompt_classifier import PromptClassifier
from .sql_generator import SQLGenerator
from .visualization_processor import VisualizationProcessor
from .summary_generator import SummaryGenerator

class AgentCoordinator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.classifier = PromptClassifier()
        self.sql_generator = SQLGenerator()
        self.viz_processor = VisualizationProcessor()
        self.summary_generator = SummaryGenerator()
        self.previous_context = None

    def generate_sql_query(self, prompt: str) -> dict:
        """
        First phase: Generate SQL query from the prompt.
        
        Args:
            prompt: The user's input prompt
            
        Returns:
            Dict containing:
            - success: boolean indicating if generation was successful
            - query: Generated SQL query if successful
            - visualization_type: Type of visualization if specified
            - error: Error message if any step fails
        """
        try:
            # 1. Classify the prompt
            self.logger.info({
                "agent": "PromptClassifier",
                "action": "starting_classification",
                "prompt": prompt
            })
            classification = self.classifier.classify_prompt(prompt)
            self.logger.info({
                "agent": "PromptClassifier",
                "action": "classification_complete",
                "result": classification
            })
            
            # Handle errors in classification
            if "error" in classification:
                return {"error": classification["error"]}
                
            # If this is a general question, not a SQL query
            if classification["type"] == "general":
                return {
                    "type": "general",
                    "message": "This appears to be a general question, not a SQL query request."
                }
            
            # 2. Generate SQL query
            self.logger.info({
                "agent": "SQLGenerator",
                "action": "starting_sql_generation",
                "prompt": prompt,
                "is_followup": classification["is_followup"]
            })
            sql_result = self.sql_generator.generate_sql(
                prompt=prompt,
                is_followup=classification["is_followup"],
                previous_context=self.previous_context
            )
            self.logger.info({
                "agent": "SQLGenerator",
                "action": "sql_generation_complete",
                "success": sql_result["success"],
                "query": sql_result.get("query", None)
            })
            
            if not sql_result["success"]:
                return {"error": sql_result["error"]}
                
            # Store query for context
            self.previous_context = sql_result["query"]
            
            # Store query for context
            self.previous_context = sql_result["query"]
            
            return {
                "success": True,
                "query": sql_result["query"],
                "visualization_type": sql_result.get("visualization_type")
            }
            
        except Exception as e:
            return {"error": f"Error generating SQL query: {str(e)}"}
            
    def process_query_results(self, query: str, query_results: dict, visualization_type: str = None, skip_column_detection: bool = False) -> dict:
        """
        Second phase: Process query results after user approval.
        
        Args:
            query: The executed SQL query
            query_results: Results from executing the query
            visualization_type: Type of visualization if specified
            skip_column_detection: Whether to skip SQLGenerator's column detection
            
        Returns:
            Dict containing:
            - success: boolean indicating if processing was successful
            - visualization_html: Generated visualization if applicable
            - summaries_html: Generated summaries
            - error: Error message if any step fails
        """
        try:
            # 1. Generate visualization if type specified
            viz_html = None
            if visualization_type:
                self.logger.info({
                    "agent": "VisualizationProcessor",
                    "action": "starting_visualization",
                    "type": visualization_type
                })

                if skip_column_detection:
                    # Let VisualizationProcessor handle column selection
                    viz_result = self.viz_processor.generate_visualization(
                        query_results["results"],
                        {"type": visualization_type}
                    )
                    if viz_result["success"]:
                        viz_html = viz_result["html"]
                        # Pass the optimized query to the frontend
                        if "optimized_query" in viz_result:
                            viz_result["visualization_query"] = viz_result["optimized_query"]
                else:
                    # Use SQLGenerator's column detection
                    viz_config = self.sql_generator.get_visualization_columns(
                        query,
                        visualization_type
                    )
                    if "error" not in viz_config:
                        viz_result = self.viz_processor.generate_visualization(
                            query_results["results"],
                            {
                                "type": visualization_type,
                                "columns": viz_config
                            }
                        )
                        if viz_result["success"]:
                            viz_html = viz_result["html"]
            
            # 2. Generate summaries
            self.logger.info({
                "agent": "SummaryGenerator",
                "action": "starting_summary_generation"
            })
            summaries = self.summary_generator.generate_summaries(
                query_results["results"],
                query,
                visualization_type
            )
            
            summaries_html = self.summary_generator.format_summaries_html(summaries)
            
            response = {
                "success": True,
                "visualization_html": viz_html,
                "summaries_html": summaries_html
            }
            
            # Add visualization query if available
            if viz_result and viz_result.get("visualization_query"):
                response["visualization_query"] = viz_result["visualization_query"]
                
            return response
            
        except Exception as e:
            return {"error": f"Error processing query results: {str(e)}"}
