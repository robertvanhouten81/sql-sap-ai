from typing import Dict, Any, List
from anthropic import Anthropic
import os
import json
import logging

logger = logging.getLogger(__name__)

class SummaryGenerator:
    def __init__(self):
        self.client = Anthropic()  # Will use ANTHROPIC_API_KEY env var by default
        logger.info("SummaryGenerator initialized")

    def generate_summaries(self, data: List[Dict[str, Any]], query: str, viz_type: str = None) -> Dict[str, Any]:
        """
        Generate both management and comprehensive summaries of query results.
        
        Args:
            data: List of dictionaries containing query results
            query: The SQL query that generated the results
            viz_type: Optional visualization type that was used
            
        Returns:
            Dict containing:
            - management_summary: Brief executive summary
            - comprehensive_summary: Detailed analysis
            - error: Error message if generation failed
        """
        try:
            logger.info({
                "agent": "SummaryGenerator",
                "action": "starting_summary_generation",
                "data_rows": len(data) if data else 0,
                "has_visualization": viz_type is not None
            })
            
            # Convert data to a more readable format for Claude
            data_str = json.dumps(data, indent=2)
            
            logger.info({
                "agent": "SummaryGenerator",
                "action": "generating_management_summary"
            })
            
            # Generate management summary
            mgmt_message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                system="Generate a brief management summary that highlights key findings, focuses on business impact, uses non-technical language, and includes relevant metrics/numbers. Return only the summary text, no additional formatting or explanation.",
                messages=[
                    {
                        "role": "user",
                        "content": f"""Given these SQL query results:
{data_str}

From query:
{query}

Please provide a management summary (2-3 sentences)."""
                    }
                ]
            )
            
            management_summary = mgmt_message.content[0].text
            
            logger.info({
                "agent": "SummaryGenerator",
                "action": "management_summary_complete",
                "summary_length": len(management_summary),
                "summary": management_summary
            })

            logger.info({
                "agent": "SummaryGenerator",
                "action": "generating_comprehensive_summary"
            })
            
            # Generate comprehensive summary
            comp_message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2000,
                system="Generate a comprehensive analysis that includes: detailed breakdown of the data, trends and patterns, notable outliers or exceptions, potential business implications, and supporting metrics and calculations. Return only the analysis text, no additional formatting or explanation.",
                messages=[
                    {
                        "role": "user",
                        "content": f"""Given these SQL query results:
{data_str}

From query:
{query}
{f'Please include analysis of the {viz_type} visualization.' if viz_type else ''}

Please provide a comprehensive analysis."""
                    }
                ]
            )
            
            comprehensive_summary = comp_message.content[0].text
            
            logger.info({
                "agent": "SummaryGenerator",
                "action": "comprehensive_summary_complete",
                "summary_length": len(comprehensive_summary),
                "summary": comprehensive_summary
            })

            return {
                "success": True,
                "management_summary": management_summary,
                "comprehensive_summary": comprehensive_summary
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error({
                "agent": "SummaryGenerator",
                "action": "summary_generation_error",
                "error": error_msg
            })
            return {
                "success": False,
                "error": f"Failed to generate summaries: {str(e)}",
                "management_summary": None,
                "comprehensive_summary": None
            }

    def format_summaries_html(self, summaries: Dict[str, str]) -> str:
        """
        Format summaries as HTML for display.
        
        Args:
            summaries: Dict containing management and comprehensive summaries
            
        Returns:
            Formatted HTML string
        """
        if not summaries.get("success", False):
            logger.warning({
                "agent": "SummaryGenerator",
                "action": "summary_formatting_error",
                "error": summaries.get('error', 'Unknown error')
            })
            return f"""
            <div class="summaries-error">
                <p>Error generating summaries: {summaries.get('error', 'Unknown error')}</p>
            </div>
            """
            
        return f"""
        <div class="summaries-container">
            <div class="management-summary">
                <h3>Management Summary</h3>
                <p>{summaries['management_summary']}</p>
            </div>
            <div class="comprehensive-summary">
                <h3>Comprehensive Analysis</h3>
                <p>{summaries['comprehensive_summary']}</p>
            </div>
        </div>
        """
